#!/usr/bin/env bash
# =============================================================================
# Demo 1: Repo Health Dashboard (DailyOps)
# Customer: Generic (reusable)
# Topic: GitHub Agentic Workflows
# Level: L200
# Duration: ~10 minutes
# Pattern: DailyOps (Report) - scheduled AI-generated issue reports
# =============================================================================
# USAGE: bash demo-1-daily-repo-health.sh
# PREREQUISITES: See demos/generic-github-agentic-workflows-demos.md
#   - gh CLI v2.40+ authenticated
#   - gh-aw extension v0.51.0+ installed
#   - COPILOT_GITHUB_TOKEN secret set in the repo
#   - DEMO_OWNER and DEMO_REPO exported or set below
# =============================================================================

set -euo pipefail

# --- Configuration ---
# Edit these two values to match your demo environment
DEMO_OWNER="${DEMO_OWNER:-your-github-org-or-username}"
DEMO_REPO="${DEMO_REPO:-your-demo-repo-name}"

REPO_FULL="${DEMO_OWNER}/${DEMO_REPO}"

# Derived: path to the local clone (assumes you cloned next to this script)
# Override REPO_LOCAL_PATH if your clone is elsewhere
REPO_LOCAL_PATH="${REPO_LOCAL_PATH:-$(pwd)/${DEMO_REPO}}"

# Color codes for cleaner terminal output during the demo
BOLD='\033[1m'
RESET='\033[0m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'

step() { echo -e "\n${BOLD}${CYAN}=== $* ===${RESET}"; }
ok()   { echo -e "${GREEN}  ok: $*${RESET}"; }

# =============================================================================
# PRE-FLIGHT CHECK
# =============================================================================

step "Pre-flight: Checking tools"

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

# Move into the local repository for all subsequent commands
cd "${REPO_LOCAL_PATH}"

# =============================================================================
# STEP 1 - Show the Empty Repository
# Presenter: "Here's our demo repo. No agentic workflows yet."
# =============================================================================

step "Step 1 - Show the current state of the repository (should be empty)"

echo ""
echo "Repository: https://github.com/${REPO_FULL}"
echo ""

# Show what (if anything) exists in .github/workflows/
if [ -d ".github/workflows" ]; then
  echo "Contents of .github/workflows/:"
  ls -la .github/workflows/ || true
else
  echo "No .github/workflows/ directory yet. Clean slate."
fi

# Open the repo homepage in the browser so the audience can see it
gh repo view "${REPO_FULL}" --web &>/dev/null &
echo "  (browser opened to repo homepage)"

# =============================================================================
# STEP 2 - Initialize the Agentic Workflows Runtime
# Presenter: "One command sets up the runtime."
# =============================================================================

step "Step 2 - Initialize the Agentic Workflows runtime"

# gh aw init is idempotent - safe to re-run if .github/aw/ already exists
gh aw init

echo ""
echo "Created:"
echo "  .github/aw/           - runtime configuration directory"
echo "  .github/agents/       - agent definition directory"
echo "  .gitattributes        - marks .lock.yml files as generated (hides from PR diffs)"
echo "  .vscode/              - editor integration settings"

# =============================================================================
# STEP 3 - Install the Daily Repo Status Workflow from the Catalog
# Presenter: "Install the pre-built daily-repo-status workflow. One command."
# =============================================================================

step "Step 3 - Install daily-repo-status from the githubnext/agentics catalog"

# The add-wizard command is interactive:
#   Prompt 1: Which AI engine? -> choose Copilot
#   Prompt 2: Set up secret?   -> skip if already set
#   Prompt 3: Push and run now? -> choose No (we push manually in step 6)
echo ""
echo "Running: gh aw add-wizard githubnext/agentics/daily-repo-status"
echo "(Interactive wizard - select Copilot engine, skip secret if already set, do NOT push yet)"
echo ""
gh aw add-wizard githubnext/agentics/daily-repo-status

# =============================================================================
# STEP 4 - Inspect the Workflow Definition (.md source file)
# Presenter: "This is what the team owns - five lines of frontmatter + plain English."
# =============================================================================

step "Step 4 - Inspect the Markdown workflow definition"

WORKFLOW_MD=".github/workflows/daily-repo-status.md"

if [ -f "${WORKFLOW_MD}" ]; then
  echo ""
  echo "-------------- ${WORKFLOW_MD} --------------"
  cat "${WORKFLOW_MD}"
  echo "----------------------------------------------"
  echo ""
  echo "Key points to highlight to the audience:"
  echo "  schedule: daily on weekdays  -> plain English cron"
  echo "  permissions: read-only       -> AI agent has NO write access"
  echo "  safe-outputs: create-issue   -> the ONLY allowed write operation"
  echo "  title-prefix                 -> every issue MUST start with this prefix"
else
  echo "WARNING: ${WORKFLOW_MD} not found. Check add-wizard output above."
fi

# =============================================================================
# STEP 5 - Show the Compiled Lock File
# Presenter: "You never edit this. The framework generates it. 200 lines of security hardening."
# =============================================================================

step "Step 5 - Show the compiled lock file (generated, do not edit)"

WORKFLOW_LOCK=".github/workflows/daily-repo-status.lock.yml"

if [ -f "${WORKFLOW_LOCK}" ]; then
  echo ""
  echo "First 60 lines of ${WORKFLOW_LOCK}:"
  echo "---"
  head -60 "${WORKFLOW_LOCK}"
  echo "---"
  echo ""
  echo "Total lines: $(wc -l < "${WORKFLOW_LOCK}")"
  echo ""
  echo "Key security features inside the lock file (no need to read all):"
  echo "  - Agent job runs in Docker with Squid proxy (network isolation)"
  echo "  - Separate threat-detection job inspects AI output before writes"
  echo "  - Write jobs are structurally separate from agent job"
else
  echo "WARNING: ${WORKFLOW_LOCK} not found. Run: gh aw compile"
fi

# =============================================================================
# STEP 6 - Push and Trigger the Workflow
# Presenter: "Let's push and run it now."
# =============================================================================

step "Step 6 - Push workflow files to GitHub and trigger a run"

# --push: commits all workflow files, pushes to origin, then dispatches
gh aw run daily-repo-status --push

echo ""
echo "Workflow dispatched. Monitoring status..."

# =============================================================================
# STEP 7 - Monitor Execution
# Presenter: "I can watch it from here. Usually takes 1-2 minutes."
# =============================================================================

step "Step 7 - Monitor workflow execution"

echo ""
echo "Current workflow status:"
gh aw status

echo ""
echo "For deeper monitoring: open the Actions tab in the browser"
echo "  https://github.com/${REPO_FULL}/actions"
echo ""
echo "TIP: Watch for three jobs in sequence:"
echo "  1. agent          - AI reads repo data and produces output"
echo "  2. threat-detect  - Security gate inspects agent output"
echo "  3. write          - Creates the GitHub Issue (only if gate passes)"

# Poll until the workflow job completes (max 3 minutes)
echo ""
echo "Polling for completion (timeout: 3 min)..."
TIMEOUT=180
ELAPSED=0
INTERVAL=15
while [ $ELAPSED -lt $TIMEOUT ]; do
  sleep $INTERVAL
  ELAPSED=$((ELAPSED + INTERVAL))
  STATE=$(gh aw status 2>/dev/null | awk '/daily-repo-status/ {print $2}' || echo "unknown")
  echo "  [${ELAPSED}s] state: ${STATE}"
  if [[ "${STATE}" == "completed" || "${STATE}" == "success" ]]; then
    ok "Workflow completed successfully"
    break
  fi
done

# =============================================================================
# STEP 8 - WOW MOMENT: Show the Resulting Issue
# Presenter: "There it is. A formatted AI health report, as a GitHub Issue."
# =============================================================================

step "Step 8 (WOW) - Show the AI-generated repo health issue"

echo ""
echo "Issues with the 'report' label:"
gh issue list --repo "${REPO_FULL}" --label "report"

echo ""
echo "Opening the latest report issue in the browser..."
ISSUE_NUMBER=$(gh issue list --repo "${REPO_FULL}" --label "report" --json number --jq '.[0].number' 2>/dev/null || echo "")
if [ -n "${ISSUE_NUMBER}" ]; then
  gh issue view "${ISSUE_NUMBER}" --repo "${REPO_FULL}" --web
  echo "  Issue #${ISSUE_NUMBER} opened in browser"
else
  echo "  No issue found yet. Workflow may still be running. Check: https://github.com/${REPO_FULL}/issues"
fi

echo ""
echo "=========================================="
echo "Demo 1 complete."
echo ""
echo "Key takeaways:"
echo "  - Zero code written: one CLI command installed a pre-built workflow"
echo "  - The .md frontmatter is the policy; the .lock.yml is the engine"
echo "  - AI agent is read-only; writes go through a threat-detection gate"
echo "  - Result: a formatted, AI-generated Issue in the repository"
echo "=========================================="

# =============================================================================
# CLEANUP (commented out - run manually after the session)
# =============================================================================

# Uncomment to reset the repository for the next demo session:
#
# git rm -f .github/workflows/daily-repo-status.md .github/workflows/daily-repo-status.lock.yml
# git commit -m "chore: remove demo-1 workflow"
# git push
# gh issue list --repo "${REPO_FULL}" --label "report" --json number --jq '.[].number' \
#   | xargs -I{} gh issue close {} --repo "${REPO_FULL}"
