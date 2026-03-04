#!/usr/bin/env bash
# =============================================================================
# Demo 2: Auto-Triage Issues (IssueOps)
# Customer: Generic (reusable)
# Topic: GitHub Agentic Workflows
# Level: L200
# Duration: ~10 minutes
# Pattern: IssueOps (React) - event-driven AI triage on every new issue
# =============================================================================
# USAGE: bash demo-2-issue-triage.sh
# PREREQUISITES: See demos/generic-github-agentic-workflows-demos.md
#   - Demo 1 already completed (gh aw init already ran)
#   - gh CLI v2.40+ authenticated
#   - gh-aw extension v0.51.0+ installed
#   - COPILOT_GITHUB_TOKEN secret set in the repo
#   - Labels: bug, enhancement, question, documentation (created during setup)
#   - DEMO_OWNER and DEMO_REPO exported or set below
# =============================================================================

set -euo pipefail

# --- Configuration ---
# Edit these two values to match your demo environment
DEMO_OWNER="${DEMO_OWNER:-your-github-org-or-username}"
DEMO_REPO="${DEMO_REPO:-your-demo-repo-name}"

REPO_FULL="${DEMO_OWNER}/${DEMO_REPO}"
REPO_LOCAL_PATH="${REPO_LOCAL_PATH:-$(pwd)/${DEMO_REPO}}"

# The test issue content - a realistic bug report used for the live triage demo
DEMO_ISSUE_TITLE="Login page returns 500 error when using SSO authentication"
DEMO_ISSUE_BODY="When using SSO login via Azure AD, the /auth/callback endpoint returns HTTP 500.
This started after the last deploy (commit abc123). Happens consistently on Chrome 121 and Edge 121.
Does not occur with username/password login. Network tab shows a CORS error immediately before the 500.

Steps to reproduce:
1. Navigate to /login
2. Click 'Sign in with Azure AD'
3. Complete Azure AD authentication
4. Observe redirect back to /auth/callback -> returns 500

Expected: Successful redirect to the dashboard
Actual: HTTP 500 Internal Server Error"

# Color codes for terminal output
BOLD='\033[1m'
RESET='\033[0m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'

step()   { echo -e "\n${BOLD}${CYAN}=== $* ===${RESET}"; }
ok()     { echo -e "${GREEN}  ok: $*${RESET}"; }
note()   { echo -e "${YELLOW}  note: $*${RESET}"; }

# =============================================================================
# PRE-FLIGHT CHECK
# =============================================================================

step "Pre-flight: Checking tools and labels"

if ! command -v gh &>/dev/null; then
  echo "ERROR: gh CLI not found. Install from https://cli.github.com"
  exit 1
fi
ok "gh CLI found: $(gh --version | head -1)"

if ! gh aw --version &>/dev/null; then
  echo "ERROR: gh-aw extension not found. Run: gh extension install github/gh-aw"
  exit 1
fi
ok "gh-aw found: $(gh aw --version)"

if [ ! -d "${REPO_LOCAL_PATH}" ]; then
  echo "ERROR: Local clone not found at ${REPO_LOCAL_PATH}"
  echo "       Run: git clone https://github.com/${REPO_FULL}.git"
  exit 1
fi
ok "Local clone found at ${REPO_LOCAL_PATH}"

cd "${REPO_LOCAL_PATH}"

# Verify the required labels exist (critical for the guardrail demo)
echo ""
echo "Checking required labels..."
MISSING_LABELS=0
for LABEL in "bug" "enhancement" "question" "documentation"; do
  if gh label list --repo "${REPO_FULL}" | grep -q "^${LABEL}"; then
    ok "Label '${LABEL}' exists"
  else
    echo "  MISSING: label '${LABEL}' - creating it now..."
    case "${LABEL}" in
      bug)           COLOR="d73a4a" ;;
      enhancement)   COLOR="a2eeef" ;;
      question)      COLOR="d876e3" ;;
      documentation) COLOR="0075ca" ;;
    esac
    gh label create "${LABEL}" --color "${COLOR}" --repo "${REPO_FULL}"
    ok "Label '${LABEL}' created"
    MISSING_LABELS=$((MISSING_LABELS + 1))
  fi
done
if [ $MISSING_LABELS -gt 0 ]; then
  note "${MISSING_LABELS} label(s) were just created. Their names must EXACTLY match the 'allowed:' list in the workflow."
fi

# =============================================================================
# STEP 1 - Transition from Demo 1
# Presenter: "We already have the runtime set up. Now we add a second workflow."
# =============================================================================

step "Step 1 - Show current workflow state (after Demo 1)"

echo ""
echo "Current workflows in this repository:"
gh aw status 2>/dev/null || echo "  (no workflows running)"

echo ""
note "The runtime is already initialized from Demo 1. We just add a second workflow."

# =============================================================================
# STEP 2 - Install the Issue Triage Workflow from the Catalog
# Presenter: "Same model: one command from the catalog."
# =============================================================================

step "Step 2 - Install issue-triage from the githubnext/agentics catalog"

echo ""
echo "Running: gh aw add-wizard githubnext/agentics/issue-triage"
echo "(Interactive wizard - select Copilot engine, do NOT push yet)"
echo ""
gh aw add-wizard githubnext/agentics/issue-triage

# =============================================================================
# STEP 3 - Inspect the Workflow Definition
# Presenter: "Here's where the guardrails live. This is the key bit."
# =============================================================================

step "Step 3 - Inspect the issue-triage workflow definition"

WORKFLOW_MD=".github/workflows/issue-triage.md"

if [ -f "${WORKFLOW_MD}" ]; then
  echo ""
  echo "-------------- ${WORKFLOW_MD} --------------"
  cat "${WORKFLOW_MD}"
  echo "----------------------------------------------"
  echo ""
  echo "*** KEY POINT FOR AUDIENCE ***"
  echo ""
  echo "  safe-outputs:"
  echo "    add-labels:"
  echo "      allowed: [bug, enhancement, question, documentation]"
  echo "      max: 2"
  echo ""
  echo "  This 'allowed' list is a COMPILE-TIME constraint."
  echo "  The compiled .lock.yml hardcodes these four values."
  echo "  The AI cannot invent a new label. It cannot apply a label outside this list."
  echo "  Even prompt injection cannot bypass this - it is enforced structurally."
else
  echo "WARNING: ${WORKFLOW_MD} not found. Check add-wizard output above."
fi

# =============================================================================
# STEP 4 - Show the 'allowed' Constraint in the Compiled Lock File
# Presenter: "Let's prove the guardrail is in the compiled YAML, not just the prompt."
# =============================================================================

step "Step 4 - Verify the guardrail is enforced in the compiled lock file"

WORKFLOW_LOCK=".github/workflows/issue-triage.lock.yml"

if [ -f "${WORKFLOW_LOCK}" ]; then
  echo ""
  echo "Searching for 'allowed' labels in the compiled YAML:"
  grep -A 5 "allowed" "${WORKFLOW_LOCK}" || echo "  (grep found no 'allowed' block - check lock file structure)"
  echo ""
  note "The allowed list appears in the job definition as a structural constraint, not just a prompt instruction."
else
  echo "WARNING: ${WORKFLOW_LOCK} not found. Running gh aw compile..."
  gh aw compile issue-triage
fi

# =============================================================================
# STEP 5 - Push the Workflow
# Presenter: "Let's push this so it's live before we create the test issue."
# =============================================================================

step "Step 5 - Push the issue-triage workflow to GitHub"

# IMPORTANT: We push first, then create the issue.
# If the issue is created before the workflow is deployed, it will not trigger.
gh aw run issue-triage --push

echo ""
ok "issue-triage workflow pushed and deployed"
echo ""
echo "Important: The workflow is now live. The NEXT issue opened in this repo will trigger it."
echo ""
note "Wait 5 seconds for GitHub to register the workflow before creating the test issue."
sleep 5

# =============================================================================
# STEP 6 - Live: Create a Test Issue
# Presenter: "Now I'll open a realistic bug report. Watch the Actions tab."
# =============================================================================

step "Step 6 (WOW setup) - Open the Actions tab, then create the test issue live"

echo ""
echo "Opening the Actions tab in the browser so the audience can watch the trigger..."
open "https://github.com/${REPO_FULL}/actions" 2>/dev/null \
  || xdg-open "https://github.com/${REPO_FULL}/actions" 2>/dev/null \
  || echo "  (manually open: https://github.com/${REPO_FULL}/actions)"

echo ""
echo "Creating test issue: '${DEMO_ISSUE_TITLE}'"
echo ""
ISSUE_URL=$(gh issue create \
  --title "${DEMO_ISSUE_TITLE}" \
  --body  "${DEMO_ISSUE_BODY}" \
  --repo  "${REPO_FULL}")

ok "Issue created: ${ISSUE_URL}"
echo ""
echo "The issue-triage workflow should now be triggering. Monitor the Actions tab."

# =============================================================================
# STEP 7 - Watch the Workflow Trigger
# Presenter: "The workflow triggered the moment the issue was opened."
# =============================================================================

step "Step 7 - Monitor workflow execution"

echo ""
echo "Polling workflow status (timeout: 4 min)..."
TIMEOUT=240
ELAPSED=0
INTERVAL=15

while [ $ELAPSED -lt $TIMEOUT ]; do
  sleep $INTERVAL
  ELAPSED=$((ELAPSED + INTERVAL))
  STATE=$(gh aw status 2>/dev/null | awk '/issue-triage/ {print $2}' || echo "unknown")
  echo "  [${ELAPSED}s] issue-triage state: ${STATE}"
  if [[ "${STATE}" == "completed" || "${STATE}" == "success" ]]; then
    ok "Workflow completed"
    break
  fi
done

# =============================================================================
# STEP 8 - WOW MOMENT: Show the Auto-Labeled, Auto-Commented Issue
# Presenter: "Look at that. Label applied. Triage comment posted."
# =============================================================================

step "Step 8 (WOW) - Show the triaged issue"

ISSUE_NUMBER=$(gh issue list --repo "${REPO_FULL}" --search "${DEMO_ISSUE_TITLE}" --json number --jq '.[0].number' 2>/dev/null || echo "")

if [ -n "${ISSUE_NUMBER}" ]; then
  echo ""
  echo "Issue #${ISSUE_NUMBER} after triage:"
  gh issue view "${ISSUE_NUMBER}" --repo "${REPO_FULL}" --comments
  echo ""
  echo "Opening in browser..."
  gh issue view "${ISSUE_NUMBER}" --repo "${REPO_FULL}" --web
else
  echo "  Issue not found by search. Opening issues list..."
  open "https://github.com/${REPO_FULL}/issues" 2>/dev/null \
    || xdg-open "https://github.com/${REPO_FULL}/issues" 2>/dev/null \
    || echo "  (manually open: https://github.com/${REPO_FULL}/issues)"
fi

echo ""
echo "=========================================="
echo "Demo 2 complete."
echo ""
echo "Key takeaways:"
echo "  - Event-driven: workflow triggered the instant the issue was opened"
echo "  - 'bug' label applied automatically based on AI classification"
echo "  - Initial triage comment posted - relevant to the issue content"
echo "  - Compile-time guardrail: AI cannot apply any label outside the allowed list"
echo "=========================================="

# =============================================================================
# CLEANUP (commented out - run manually after the session)
# =============================================================================

# Uncomment to reset for the next demo session:
#
# ISSUE_NUMBER=$(gh issue list --repo "${REPO_FULL}" --search "${DEMO_ISSUE_TITLE}" \
#   --json number --jq '.[0].number')
# gh issue close "${ISSUE_NUMBER}" --repo "${REPO_FULL}"
# git rm -f .github/workflows/issue-triage.md .github/workflows/issue-triage.lock.yml
# git commit -m "chore: remove demo-2 workflow"
# git push
