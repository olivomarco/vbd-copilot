#!/usr/bin/env bash
# =============================================================================
# demo-4-git-pipeline-setup.sh
# =============================================================================
# Microsoft Fabric - Trustworthy Data Demo Series
# Demo 4: Git Integration + 3-Stage Deployment Pipeline
#
# PURPOSE
# -------
# Helper script run from the *presenter's local machine* (not inside Fabric).
# It:
#   1. Creates a GitHub repository and initialises it with a placeholder
#      fabric-workspace/ directory structure that Fabric Git integration expects.
#   2. Creates and pushes three branches (dev, test, main) so each Fabric
#      workspace stage has an appropriate branch to map to.
#   3. Prints a step-by-step reminder for the live manual demo in the Fabric UI.
#
# PREREQUISITES
# -------------
#   - git CLI installed and configured with your GitHub identity
#   - GitHub CLI (gh) installed and authenticated: gh auth login
#   - Fabric tenant admin settings enabled:
#       "Users can synchronise workspace items with their Git repositories"
#       "Users can synchronise workspace items with GitHub repositories"
#   - Three Fabric workspaces pre-created (or let pipeline create Test/Prod):
#       DataEng-Dev     (must have at least one Notebook item)
#       DataEng-Pipeline [Test]     (auto-created by pipeline if not present)
#       DataEng-Pipeline [Production] (auto-created by pipeline if not present)
#
# USAGE
# -----
#   chmod +x demo-4-git-pipeline-setup.sh
#   GITHUB_ORG=my-org REPO_NAME=fabric-demo-workspace ./demo-4-git-pipeline-setup.sh
#
# ENVIRONMENT VARIABLES
# ----------------------
#   GITHUB_ORG   - GitHub org or username to create the repo under (default: current gh user)
#   REPO_NAME    - Repository name to create (default: fabric-demo-workspace)
#
# REFERENCES
# ----------
# https://learn.microsoft.com/en-us/fabric/cicd/git-integration/intro-to-git-integration
# https://learn.microsoft.com/en-us/fabric/cicd/git-integration/git-get-started
# https://learn.microsoft.com/en-us/fabric/cicd/deployment-pipelines/get-started-with-deployment-pipelines
# https://learn.microsoft.com/en-us/fabric/cicd/deployment-pipelines/create-rules
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GITHUB_ORG="${GITHUB_ORG:-$(gh api user --jq '.login' 2>/dev/null || echo 'my-org')}"
REPO_NAME="${REPO_NAME:-fabric-demo-workspace}"
GIT_FOLDER="fabric-workspace"
BRANCHES=("dev" "test" "main")

echo "=== Demo 4 - Git Repo Initialisation ==="
echo "GitHub org/user : ${GITHUB_ORG}"
echo "Repository name : ${REPO_NAME}"
echo "Git folder      : ${GIT_FOLDER}"
echo ""

# ---------------------------------------------------------------------------
# Step 1 - Check dependencies
# ---------------------------------------------------------------------------
echo "[1/6] Checking dependencies..."

if ! command -v git &>/dev/null; then
    echo "ERROR: git is not installed. Install it from https://git-scm.com/" >&2
    exit 1
fi

if ! command -v gh &>/dev/null; then
    echo "ERROR: GitHub CLI (gh) is not installed. Install from https://cli.github.com/" >&2
    exit 1
fi

gh auth status >/dev/null 2>&1 || {
    echo "ERROR: gh is not authenticated. Run: gh auth login" >&2
    exit 1
}

echo "  [OK] git and gh CLI available"

# ---------------------------------------------------------------------------
# Step 2 - Create GitHub repository
# ---------------------------------------------------------------------------
echo "[2/6] Creating GitHub repository ${GITHUB_ORG}/${REPO_NAME}..."

if gh repo view "${GITHUB_ORG}/${REPO_NAME}" &>/dev/null; then
    echo "  [INFO] Repository already exists - skipping creation"
else
    gh repo create "${GITHUB_ORG}/${REPO_NAME}" \
        --private \
        --description "Fabric workspace items for demo - trustworthy data session" \
        --confirm 2>/dev/null || \
    gh repo create "${GITHUB_ORG}/${REPO_NAME}" \
        --private \
        --description "Fabric workspace items for demo - trustworthy data session"
    echo "  [OK] Repository created"
fi

REPO_URL="https://github.com/${GITHUB_ORG}/${REPO_NAME}.git"
echo "  URL: ${REPO_URL}"

# ---------------------------------------------------------------------------
# Step 3 - Initialise local folder structure
# ---------------------------------------------------------------------------
echo "[3/6] Initialising local workspace folder..."

WORK_DIR=$(mktemp -d)
cd "${WORK_DIR}"
git init
git remote add origin "${REPO_URL}"

# Create the fabric-workspace/ folder with a README so the folder exists
mkdir -p "${GIT_FOLDER}"
cat > "${GIT_FOLDER}/README.md" <<'FABRIC_README'
# fabric-workspace

This folder is managed by Microsoft Fabric Git integration.
Do not manually edit files in this folder - changes should flow through
the Fabric workspace Source Control UI or via fabric-cicd automation.

Folder structure (populated automatically by Fabric after Git connection):
  MyLakehouse.Lakehouse/
  IngestNotebook.Notebook/
    notebook-content.py
  IngestPipeline.DataPipeline/
    pipeline-content.json
  parameter.yml
FABRIC_README

cat > .gitignore <<'GITIGNORE'
# Python
__pycache__/
*.pyc
*.pyo
.env
.venv/
*.egg-info/

# Temp files
*.tmp
.DS_Store
GITIGNORE

git add .
git commit -m "chore: initialise repository with fabric-workspace folder structure"

# ---------------------------------------------------------------------------
# Step 4 - Create and push all three branches
# ---------------------------------------------------------------------------
echo "[4/6] Creating branches: ${BRANCHES[*]}..."

# Create main first (safe on git 2.28+ where the initial branch defaults to main)
# then branch test and dev from it to avoid name collision.
git checkout -b main 2>/dev/null || git checkout main
git push -u origin main --quiet
echo "  [OK] Branch 'main' pushed"

git checkout -b test main
git push -u origin test --quiet
echo "  [OK] Branch 'test' pushed"

git checkout -b dev main
git push -u origin dev --quiet
echo "  [OK] Branch 'dev' pushed"

git checkout dev

echo ""
echo "=== Repository ready ==="
echo "URL: https://github.com/${GITHUB_ORG}/${REPO_NAME}"
echo "Branches created: main, test, dev"
echo ""

# ---------------------------------------------------------------------------
# Step 5 - Print live demo walkthrough reminders
# ---------------------------------------------------------------------------
cat <<'DEMO_STEPS'
=============================================================================
LIVE DEMO WALKTHROUGH - Fabric UI steps (manual, run during the session)
=============================================================================

STEP 1 - Connect DataEng-Dev workspace to GitHub
-------------------------------------------------
1. Open DataEng-Dev workspace in Fabric portal
2. Workspace settings (gear icon) -> Git integration
3. Git provider: GitHub -> Add account (OAuth flow)
4. Repository: [REPO_NAME]
5. Branch: dev
6. Git folder: fabric-workspace
7. Click Connect and sync
8. The Source Control icon (branching arrows) appears at top of workspace nav
   -> TELL AUDIENCE: "Every change I make in this workspace can now be tracked
      just like application code."

STEP 2 - Modify a Notebook and commit to GitHub
------------------------------------------------
1. Open the Notebook in DataEng-Dev
2. Add a new line comment: # Updated: adding region filter logic
3. Click the Source Control icon - it shows "1 uncommitted change"
4. Changes tab -> enter commit message: feat: add region filter comment
5. Click Commit
6. Switch browser tab to GitHub -> show the commit in the repo history
   -> TELL AUDIENCE: "The author, timestamp, and diff are right here in GitHub.
      Full auditability. No custom tooling required."

STEP 3 - Create 3-stage Deployment Pipeline
--------------------------------------------
1. Workspace left nav -> Deployment pipelines -> + New pipeline
2. Name: DataEng-Pipeline
3. Stages: 3 (Development / Test / Production) - keep defaults
4. Click Create and continue

STEP 4 - Assign and deploy stages
-----------------------------------
1. Development stage -> Assign workspace -> select DataEng-Dev
2. Click the Deploy arrow (Dev -> Test) -> Full deployment -> Confirm
   -> Fabric auto-creates DataEng-Pipeline [Test] workspace
3. Click the Deploy arrow (Test -> Production) -> Full deployment -> Confirm
   -> Fabric auto-creates DataEng-Pipeline [Production] workspace

STEP 5 - Set deployment rule on Production
-------------------------------------------
1. Production stage -> Deployment rules icon (wrench)
2. Select the Notebook item
3. Default lakehouse rule -> Add rule
4. Select the Production Lakehouse from the dropdown -> Save
5. Re-deploy Test -> Production (rule only applies to future deployments)
6. Open the Notebook in the Production workspace
   -> TELL AUDIENCE: "The notebook is now pointing at the PRODUCTION Lakehouse,
      not Dev. One rule, automatically applied on every future deploy."

STEP 6 - Show Compare
----------------------
1. Click Compare button between Dev and Test stages
2. Show item-level diff highlighting what changed
   -> TELL AUDIENCE: "This is your release manifest. Before you approve prod,
      you can see exactly what items changed and review diffs."

=============================================================================
RECOVERY: If deployment fails
=============================================================================
- If "Add rule" button is greyed out: Transfer Notebook item ownership to your
  admin account (Notebook menu -> Transfer ownership).
- If deploy arrow is disabled: Ensure both source and destination workspaces
  have at least one item in common by item name.
- If workspace assignment fails: Confirm the workspace is not already assigned
  to another pipeline stage.
=============================================================================
DEMO_STEPS

# ---------------------------------------------------------------------------
# Step 6 - Cleanup instructions
# ---------------------------------------------------------------------------
cat <<'CLEANUP'
=============================================================================
POST-DEMO CLEANUP (optional)
=============================================================================
To remove the GitHub repository after the session:
  gh repo delete ${GITHUB_ORG}/${REPO_NAME} --confirm

To remove the Fabric deployment pipeline:
  -> Fabric portal -> Deployment pipelines -> DataEng-Pipeline -> Settings -> Delete

To remove auto-created Test/Prod workspaces:
  -> Workspace settings -> Other settings -> Delete workspace
=============================================================================
CLEANUP

cd - >/dev/null
rm -rf "${WORK_DIR}"

echo ""
echo "Script complete."
