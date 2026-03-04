#!/usr/bin/env bash
# =============================================================================
# Demo 3: On-Demand Code Review (ChatOps)
# Customer: Generic (reusable)
# Topic: GitHub Agentic Workflows
# Level: L200
# Duration: ~10 minutes
# Pattern: ChatOps (Request) - /review slash command triggers inline PR annotations
# =============================================================================
# USAGE: bash demo-3-code-review.sh
# PREREQUISITES: See demos/generic-github-agentic-workflows-demos.md
#   - Demo 1 and Demo 2 already completed (runtime initialized, two workflows deployed)
#   - gh CLI v2.40+ authenticated
#   - gh-aw extension v0.51.0+ installed
#   - COPILOT_GITHUB_TOKEN secret set in the repo
#   - A PR exists on branch demo/flawed-auth targeting main (created during pre-session setup)
#   - DEMO_OWNER and DEMO_REPO exported or set below
# =============================================================================

set -euo pipefail

# --- Configuration ---
# Edit these two values to match your demo environment
DEMO_OWNER="${DEMO_OWNER:-your-github-org-or-username}"
DEMO_REPO="${DEMO_REPO:-your-demo-repo-name}"

REPO_FULL="${DEMO_OWNER}/${DEMO_REPO}"
REPO_LOCAL_PATH="${REPO_LOCAL_PATH:-$(pwd)/${DEMO_REPO}}"

# The name of the branch carrying the flawed code for the demo PR
FLAWED_BRANCH="demo/flawed-auth"

# Color codes
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

step "Pre-flight: Checking tools and demo PR"

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

# Check that a demo PR exists (required for the /review trigger)
PR_NUMBER=$(gh pr list --repo "${REPO_FULL}" --head "${FLAWED_BRANCH}" --json number --jq '.[0].number' 2>/dev/null || echo "")
if [ -z "${PR_NUMBER}" ]; then
  echo ""
  echo "WARNING: No open PR found for branch '${FLAWED_BRANCH}'."
  echo "Creating it now..."
  echo ""

  # Check if the branch exists remotely
  if ! git ls-remote --heads origin "${FLAWED_BRANCH}" | grep -q "${FLAWED_BRANCH}"; then
    echo "Branch '${FLAWED_BRANCH}' not found on origin. Creating it with demo content..."

    git checkout -b "${FLAWED_BRANCH}" 2>/dev/null || git checkout "${FLAWED_BRANCH}"

    cat > auth_helper.py << 'PYEOF'
import requests

# TODO: move this to env vars before prod
API_KEY = "sk-prod-a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"

def get_user_profile(user_id):
    # Missing error handling
    resp = requests.get(f"https://api.example.com/users/{user_id}",
                        headers={"Authorization": f"Bearer {API_KEY}"})
    return resp.json()
PYEOF

    git add auth_helper.py
    git commit -m "feat: add user auth helper with API integration"
    git push -u origin "${FLAWED_BRANCH}"
    git checkout main 2>/dev/null || git checkout -
  fi

  PR_URL=$(gh pr create \
    --title "feat: add user auth helper" \
    --body "Adds a helper function to fetch user profiles from the internal users API." \
    --base main \
    --head "${FLAWED_BRANCH}" \
    --repo "${REPO_FULL}")
  PR_NUMBER=$(gh pr list --repo "${REPO_FULL}" --head "${FLAWED_BRANCH}" --json number --jq '.[0].number')
  ok "PR #${PR_NUMBER} created: ${PR_URL}"
else
  ok "Demo PR #${PR_NUMBER} found on branch ${FLAWED_BRANCH}"
fi

# =============================================================================
# STEP 1 - Walk Through the Flawed PR Diff
# Presenter: "Here's the PR. Can you spot the issues?"
# =============================================================================

step "Step 1 - Show the demo PR and its diff"

echo ""
echo "Opening PR #${PR_NUMBER} in the browser..."
gh pr view "${PR_NUMBER}" --repo "${REPO_FULL}" --web &>/dev/null &
echo ""
echo "PR diff (terminal view):"
echo "---"
gh pr diff "${PR_NUMBER}" --repo "${REPO_FULL}" 2>/dev/null || echo "(diff not available - see browser)"
echo "---"
echo ""
echo "Two deliberate flaws in this diff:"
echo "  1. Hardcoded API key: API_KEY = 'sk-prod-...' - should be in environment variables"
echo "  2. Missing error handling: resp.json() is called without checking resp.status_code"

# =============================================================================
# STEP 2 - Install the Grumpy Reviewer Workflow
# Presenter: "Let's install the review-bot based on the Grumpy Reviewer pattern."
# =============================================================================

step "Step 2 - Install the grumpy-reviewer workflow from the catalog"

echo ""
echo "Running: gh aw add-wizard githubnext/agentics/grumpy-reviewer"
echo "(Interactive wizard - select Copilot engine, do NOT push yet)"
echo ""
gh aw add-wizard githubnext/agentics/grumpy-reviewer

# =============================================================================
# STEP 3 - Inspect the Workflow Definition
# Presenter: "The ChatOps pattern uses a slash_command trigger."
# =============================================================================

step "Step 3 - Inspect the grumpy-reviewer workflow definition"

WORKFLOW_MD=".github/workflows/grumpy-reviewer.md"

if [ -f "${WORKFLOW_MD}" ]; then
  echo ""
  echo "-------------- ${WORKFLOW_MD} --------------"
  cat "${WORKFLOW_MD}"
  echo "----------------------------------------------"
  echo ""
  echo "Key things to highlight:"
  echo ""
  echo "  on:"
  echo "    slash_command:"
  echo "      name: review"
  echo "      events: [pull_request_comment]"
  echo ""
  echo "  -> Trigger: a /review comment on any PR"
  echo ""
  echo "  roles: [write]"
  echo ""
  echo "  -> Access control: only users with WRITE access can trigger this"
  echo "     External contributors CANNOT trigger it"
  echo ""
  echo "  safe-outputs:"
  echo "    create-pull-request-review-comment:"
  echo "      max: 5"
  echo ""
  echo "  -> The AI can post at most 5 inline review comments per run"
  echo "     Structural limit enforced in the compiled YAML"
else
  echo "WARNING: ${WORKFLOW_MD} not found. Check add-wizard output above."
fi

# =============================================================================
# STEP 4 - Explain the Access Control
# Presenter: "roles: [write] - this is not a runtime check. It's structural."
# =============================================================================

step "Step 4 - Verify access control is encoded in the lock file"

WORKFLOW_LOCK=".github/workflows/grumpy-reviewer.lock.yml"

if [ -f "${WORKFLOW_LOCK}" ]; then
  echo ""
  echo "Searching for role/permission checks in compiled YAML:"
  grep -A 3 "roles\|slash_command\|write" "${WORKFLOW_LOCK}" | head -30 || true
  echo ""
  note "Any user who comments /review but lacks write access will get a 'Permission denied' response from the framework - the AI agent never starts."
else
  echo "WARNING: ${WORKFLOW_LOCK} not found. Running gh aw compile..."
  gh aw compile grumpy-reviewer
fi

# =============================================================================
# STEP 5 - Push the Workflow
# Presenter: "Deploying. One command."
# =============================================================================

step "Step 5 - Push the grumpy-reviewer workflow to GitHub"

gh aw run grumpy-reviewer --push

echo ""
ok "grumpy-reviewer workflow pushed and deployed"
echo ""
note "The /review command is now active on all pull requests in this repository."

# Give GitHub a few seconds to register the new workflow
sleep 5

# =============================================================================
# STEP 6 - WOW MOMENT: Post /review on the Demo PR
# Presenter: "Now for the moment of truth. I'll type /review."
# =============================================================================

step "Step 6 (WOW) - Post /review on the demo PR"

echo ""
echo "Opening PR #${PR_NUMBER} in the browser for the audience to watch..."
gh pr view "${PR_NUMBER}" --repo "${REPO_FULL}" --web &>/dev/null &
sleep 2

echo ""
echo "Options for triggering /review:"
echo "  Option A (preferred for live demo): Type '/review' manually in the browser PR comment box"
echo "  Option B (CLI): This script will post it via gh pr comment"
echo ""
read -r -p "Press ENTER to trigger /review via CLI, or Ctrl-C to do it manually in the browser: "

echo ""
gh pr comment "${PR_NUMBER}" \
  --body "/review" \
  --repo "${REPO_FULL}"

ok "/review comment posted on PR #${PR_NUMBER}"
echo ""
echo "The grumpy-reviewer workflow is now running."
echo "Watch the Actions tab: https://github.com/${REPO_FULL}/actions"

# =============================================================================
# STEP 7 - Monitor and Show the Results
# Presenter: "The agent is reading the diff. It will post inline comments."
# =============================================================================

step "Step 7 - Monitor workflow and show results"

echo ""
echo "Polling workflow status (timeout: 4 min)..."
TIMEOUT=240
ELAPSED=0
INTERVAL=15

while [ $ELAPSED -lt $TIMEOUT ]; do
  sleep $INTERVAL
  ELAPSED=$((ELAPSED + INTERVAL))
  STATE=$(gh aw status 2>/dev/null | awk '/grumpy-reviewer/ {print $2}' || echo "unknown")
  echo "  [${ELAPSED}s] grumpy-reviewer state: ${STATE}"
  if [[ "${STATE}" == "completed" || "${STATE}" == "success" ]]; then
    ok "Workflow completed"
    break
  fi
done

echo ""
echo "PR review comments (terminal view):"
echo "---"
gh pr view "${PR_NUMBER}" --repo "${REPO_FULL}" --comments 2>/dev/null | tail -60
echo "---"
echo ""
echo "Opening the PR in the browser to show inline annotations..."
gh pr view "${PR_NUMBER}" --repo "${REPO_FULL}" --web

echo ""
echo "=========================================="
echo "Demo 3 complete."
echo ""
echo "Key takeaways:"
echo "  - /review slash command: AI on-demand, triggered from GitHub UI"
echo "  - Inline annotations: findings reference exact file and line"
echo "  - Access control: only write-access users can trigger; structural, not advisory"
echo "  - Safe outputs: max 5 inline comments enforced at compile time, not runtime"
echo "  - Verdict posted in the summary comment: APPROVE / REQUEST_CHANGES / COMMENT"
echo ""
echo "Connecting narrative recap:"
echo "  Demo 1 (Report)  - repo proactively reports its own health on a schedule"
echo "  Demo 2 (React)   - repo reacts to every new issue automatically"
echo "  Demo 3 (Request) - maintainer commands AI on-demand via /review"
echo "  All three: zero code written; policy defined in .md, security hardened by the framework"
echo "=========================================="

# =============================================================================
# OPTIONAL POST-DEMO: Show the full workflow status dashboard
# =============================================================================

step "Optional: Show all three workflows together"

echo ""
echo "All agentic workflows currently deployed in ${REPO_FULL}:"
gh aw status

# =============================================================================
# CLEANUP (commented out - run manually after the session)
# =============================================================================

# Uncomment to reset the repository for the next demo session:
#
# git rm -f \
#   .github/workflows/grumpy-reviewer.md \
#   .github/workflows/grumpy-reviewer.lock.yml \
#   .github/workflows/issue-triage.md \
#   .github/workflows/issue-triage.lock.yml \
#   .github/workflows/daily-repo-status.md \
#   .github/workflows/daily-repo-status.lock.yml
# git commit -m "chore: remove all demo workflows"
# git push
#
# # Close the demo PR and delete the flawed branch
# gh pr close "${PR_NUMBER}" --repo "${REPO_FULL}" --delete-branch
#
# # Close any open report issues
# gh issue list --repo "${REPO_FULL}" --label "report" --json number --jq '.[].number' \
#   | xargs -I{} gh issue close {} --repo "${REPO_FULL}"
