"""
demo-5-deploy.py
=================
Microsoft Fabric - Trustworthy Data Demo Series
Demo 5: fabric-cicd GitHub Actions Automation

PURPOSE
-------
Deploys ALL Fabric workspace items in the fabric-workspace/ folder to the
PRODUCTION Fabric workspace using the fabric-cicd library and a Service
Principal identity. This script is invoked by the GitHub Actions workflow
(.github/workflows/deploy-fabric.yml) on every push to the main branch.

REPO STRUCTURE (expected)
--------------------------
/
  fabric-workspace/
    MyLakehouse.Lakehouse/
    IngestNotebook.Notebook/
      notebook-content.py
    IngestPipeline.DataPipeline/
      pipeline-content.json
    parameter.yml          <- find_replace rules for GUID substitution
  .deploy/
    deploy.py              <- THIS FILE
  .github/
    workflows/
      deploy-fabric.yml

GITHUB ACTIONS SECRETS REQUIRED
---------------------------------
  FABRIC_PROD_WORKSPACE_ID  - GUID of the PROD Fabric workspace
  FABRIC_TENANT_ID          - Entra tenant ID
  FABRIC_CLIENT_ID          - SPN (app registration) client ID
  FABRIC_CLIENT_SECRET      - SPN client secret

SPN REQUIREMENTS
-----------------
  - Created in Entra ID with a client secret
  - Granted workspace Admin or Contributor role in the PROD workspace via:
      Fabric portal -> PROD workspace -> Settings -> Manage access -> Add SPN
  - Service principals must be enabled in Fabric tenant admin settings:
      Admin portal -> Tenant settings -> Developer settings ->
      "Service principals can use Fabric APIs" = Enabled

REFERENCES
----------
https://microsoft.github.io/fabric-cicd/latest/
https://github.com/microsoft/fabric-cicd
https://learn.microsoft.com/en-us/fabric/cicd/best-practices-cicd
"""

import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Validate required environment variables before importing heavy dependencies
# ---------------------------------------------------------------------------
REQUIRED_ENV_VARS = [
    "FABRIC_PROD_WORKSPACE_ID",
    "FABRIC_TENANT_ID",
    "FABRIC_CLIENT_ID",
    "FABRIC_CLIENT_SECRET",
]

missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
if missing:
    print(f"ERROR: Missing required environment variables: {', '.join(missing)}", file=sys.stderr)
    print("Set these as GitHub Actions secrets and map them under 'env:' in the workflow.", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Read configuration from environment
# ---------------------------------------------------------------------------
workspace_id = os.environ["FABRIC_PROD_WORKSPACE_ID"]
tenant_id    = os.environ["FABRIC_TENANT_ID"]
client_id    = os.environ["FABRIC_CLIENT_ID"]
client_secret = os.environ["FABRIC_CLIENT_SECRET"]

# Environment tag used by parameter.yml find_replace rules (must match key in replace_value)
environment = "PROD"

# Path to the folder that contains the Fabric workspace items
# This script lives in .deploy/, fabric-workspace/ is one level up at repo root
repository_directory = str(Path(__file__).resolve().parent.parent / "fabric-workspace")

# Item types to deploy - keep narrow to avoid unintended side effects
# Add or remove types based on what your workspace contains
item_type_in_scope = [
    "Notebook",
    "DataPipeline",
    "Environment",
    "Lakehouse",
]

# ---------------------------------------------------------------------------
# Imports (after env-var validation to give clear error messages first)
# ---------------------------------------------------------------------------
try:
    from azure.identity import ClientSecretCredential
    from fabric_cicd import FabricWorkspace, publish_all_items, unpublish_all_orphan_items
except ImportError as exc:
    print(f"ERROR: Required package not installed: {exc}", file=sys.stderr)
    print("Run: pip install fabric-cicd azure-identity", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Authenticate using SPN
# ---------------------------------------------------------------------------
print(f"Authenticating with SPN (client_id={client_id[:8]}...)")

token_credential = ClientSecretCredential(
    tenant_id=tenant_id,
    client_id=client_id,
    client_secret=client_secret,
)

# ---------------------------------------------------------------------------
# Initialise FabricWorkspace pointing at PROD
# ---------------------------------------------------------------------------
print(f"Connecting to PROD workspace: {workspace_id}")
print(f"Repository directory        : {repository_directory}")
print(f"Item types in scope         : {item_type_in_scope}")

target_workspace = FabricWorkspace(
    workspace_id=workspace_id,
    environment=environment,
    repository_directory=repository_directory,
    item_type_in_scope=item_type_in_scope,
    token_credential=token_credential,
)

# ---------------------------------------------------------------------------
# Deploy all items in scope
# parameter.yml find_replace rules are applied automatically by fabric-cicd
# before each item is pushed to the workspace
# ---------------------------------------------------------------------------
print("\n--- Publishing items ---")
publish_all_items(target_workspace)

# ---------------------------------------------------------------------------
# Remove items that exist in PROD but no longer exist in the repo
# This keeps PROD clean when items are deleted from fabric-workspace/
# ---------------------------------------------------------------------------
print("\n--- Removing orphan items ---")
unpublish_all_orphan_items(target_workspace)

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
print(f"\nDeployment to PROD workspace {workspace_id} complete.")
print("Verify the deployment in Fabric portal -> workspace -> item list.")
print("Check audit trail: Fabric Admin portal -> Activity log -> filter by SPN client_id.")
