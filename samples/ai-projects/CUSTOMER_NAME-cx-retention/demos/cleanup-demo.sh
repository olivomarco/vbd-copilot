#!/usr/bin/env bash
# =============================================================================
# cleanup-demo.sh
# Purpose      : Removes ONLY the demo-overlay resources created by
#                demo-access.bicep for the CUSTOMER_NAME Intelligent Bill Explainer.
#                Core project infrastructure (VNet, APIM, Container Apps,
#                OpenAI, AI Search, Cosmos DB, Storage, Key Vault, App Insights)
#                is NEVER touched by this script.
# Usage        : RESOURCE_GROUP=<rg> ./cleanup-demo.sh [--dry-run]
# Prerequisites: az CLI (logged in), bash >= 4
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RESOURCE_GROUP="${RESOURCE_GROUP:-}"
RESOURCE_PREFIX="${RESOURCE_PREFIX:-CUSTOMER_NAME-bill}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
DRY_RUN=false
REMOVE_SEED_DATA=false

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

show_help() {
  cat <<EOF
Usage: RESOURCE_GROUP=<rg> $0 [OPTIONS]

Environment variables (required):
  RESOURCE_GROUP    Azure resource group containing the deployment

Environment variables (optional):
  RESOURCE_PREFIX   Name prefix shared by all project resources (default: CUSTOMER_NAME-bill)
  ENVIRONMENT       Deployment environment suffix (default: dev)

Options:
  --dry-run         Print what would be deleted without actually deleting anything
  --seed-data       Also remove seeded demo data (calls seed-demo-data.sh --cleanup)
  --help            Show this help message
EOF
}

for arg in "$@"; do
  case "$arg" in
    --dry-run)    DRY_RUN=true ;;
    --seed-data)  REMOVE_SEED_DATA=true ;;
    --help)       show_help; exit 0 ;;
    *)            echo "ERROR: Unknown argument: $arg"; show_help; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log() {
  echo "[$(date '+%H:%M:%S')] $*"
}

dry_log() {
  echo "[DRY-RUN] Would execute: $*"
}

# Execute a command or print it in dry-run mode
maybe_run() {
  if [[ "$DRY_RUN" == "true" ]]; then
    dry_log "$*"
  else
    eval "$*"
  fi
}

resource_exists() {
  local resource_type="$1"
  local resource_name="$2"
  local count
  count=$(az resource list \
    --resource-group "$RESOURCE_GROUP" \
    --resource-type "$resource_type" \
    --query "[?name=='${resource_name}'] | length(@)" \
    -o tsv 2>/dev/null || echo "0")
  [[ "$count" -gt "0" ]]
}

# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------

check_prerequisites() {
  log "Checking prerequisites..."

  if [[ -z "$RESOURCE_GROUP" ]]; then
    echo "ERROR: RESOURCE_GROUP environment variable is required."
    exit 1
  fi

  if ! command -v az &>/dev/null; then
    echo "ERROR: az CLI is not installed or not on PATH."
    exit 1
  fi

  if ! az account show &>/dev/null; then
    echo "ERROR: az CLI is not logged in. Run 'az login' first."
    exit 1
  fi

  log "Active subscription: $(az account show --query name -o tsv)"
  log "Target resource group: $RESOURCE_GROUP"
}

# ---------------------------------------------------------------------------
# Derive demo-overlay resource names (same pattern as demo-access.bicep)
# ---------------------------------------------------------------------------

derive_names() {
  VM_NAME="${RESOURCE_PREFIX}-jumpbox-${ENVIRONMENT}"
  NIC_NAME="${RESOURCE_PREFIX}-jumpbox-nic-${ENVIRONMENT}"
  NSG_NAME="${RESOURCE_PREFIX}-jumpbox-nsg-${ENVIRONMENT}"
  BASTION_NAME="${RESOURCE_PREFIX}-bastion-${ENVIRONMENT}"
  BASTION_PIP_NAME="${RESOURCE_PREFIX}-bastion-pip-${ENVIRONMENT}"

  log "Demo overlay resources targeted for removal:"
  log "  VM              : $VM_NAME"
  log "  NIC             : $NIC_NAME"
  log "  NSG             : $NSG_NAME"
  log "  Bastion         : $BASTION_NAME"
  log "  Bastion PIP     : $BASTION_PIP_NAME"
}

# ---------------------------------------------------------------------------
# Confirmation prompt (skipped in dry-run)
# ---------------------------------------------------------------------------

confirm_deletion() {
  if [[ "$DRY_RUN" == "true" ]]; then
    log "Dry-run mode - skipping confirmation prompt."
    return
  fi

  echo ""
  echo "============================================================"
  echo " WARNING: This will permanently delete the demo resources"
  echo " listed above from resource group: $RESOURCE_GROUP"
  echo " Core project infrastructure will NOT be affected."
  echo "============================================================"
  echo ""
  read -r -p "Type YES to confirm deletion: " confirmation
  if [[ "$confirmation" != "YES" ]]; then
    echo "Aborted by user."
    exit 0
  fi
}

# ---------------------------------------------------------------------------
# Delete jump box VM and its OS disk
# ---------------------------------------------------------------------------

delete_jumpbox_vm() {
  log "--- Jump box VM ---"

  if resource_exists "Microsoft.Compute/virtualMachines" "$VM_NAME"; then
    # Capture OS disk name before deleting the VM
    local disk_name
    disk_name=$(az vm show \
      --resource-group "$RESOURCE_GROUP" \
      --name "$VM_NAME" \
      --query "storageProfile.osDisk.name" -o tsv 2>/dev/null || echo "")

    log "Deleting VM: $VM_NAME"
    maybe_run "az vm delete \
      --resource-group '$RESOURCE_GROUP' \
      --name '$VM_NAME' \
      --yes \
      --output none"
    log "VM deleted."

    if [[ -n "$disk_name" ]]; then
      log "Deleting OS disk: $disk_name"
      if [[ "$DRY_RUN" == "false" ]]; then
        # Wait briefly for the VM deletion to propagate before deleting the disk
        sleep 10
      fi
      if [[ "$DRY_RUN" == "true" ]] || az disk show \
          --resource-group "$RESOURCE_GROUP" \
          --name "$disk_name" &>/dev/null 2>&1; then
        maybe_run "az disk delete \
          --resource-group '$RESOURCE_GROUP' \
          --name '$disk_name' \
          --yes \
          --no-wait \
          --output none"
        log "OS disk deletion initiated: $disk_name"
      else
        log "OS disk not found (may have been auto-deleted): $disk_name"
      fi
    fi
  else
    log "[SKIP] VM not found: $VM_NAME"
  fi
}

# ---------------------------------------------------------------------------
# Delete NIC (may persist if VM deletion was interrupted)
# ---------------------------------------------------------------------------

delete_jumpbox_nic() {
  log "--- Jump box NIC ---"

  if resource_exists "Microsoft.Network/networkInterfaces" "$NIC_NAME"; then
    log "Deleting NIC: $NIC_NAME"
    maybe_run "az network nic delete \
      --resource-group '$RESOURCE_GROUP' \
      --name '$NIC_NAME' \
      --output none"
    log "NIC deleted."
  else
    log "[SKIP] NIC not found (already deleted or never created): $NIC_NAME"
  fi
}

# ---------------------------------------------------------------------------
# Delete Azure Bastion host
# ---------------------------------------------------------------------------

delete_bastion() {
  log "--- Azure Bastion ---"

  if resource_exists "Microsoft.Network/bastionHosts" "$BASTION_NAME"; then
    log "Deleting Bastion host: $BASTION_NAME (this takes 2-5 minutes)"
    maybe_run "az network bastion delete \
      --resource-group '$RESOURCE_GROUP' \
      --name '$BASTION_NAME' \
      --output none"
    log "Bastion host deleted."
  else
    log "[SKIP] Bastion not found: $BASTION_NAME"
  fi
}

# ---------------------------------------------------------------------------
# Delete Bastion public IP
# ---------------------------------------------------------------------------

delete_bastion_pip() {
  log "--- Bastion public IP ---"

  if resource_exists "Microsoft.Network/publicIPAddresses" "$BASTION_PIP_NAME"; then
    log "Deleting public IP: $BASTION_PIP_NAME"
    maybe_run "az network public-ip delete \
      --resource-group '$RESOURCE_GROUP' \
      --name '$BASTION_PIP_NAME' \
      --output none"
    log "Public IP deleted."
  else
    log "[SKIP] Public IP not found: $BASTION_PIP_NAME"
  fi
}

# ---------------------------------------------------------------------------
# Delete jump box NSG
# (Only safe to delete after the subnet association is removed)
# ---------------------------------------------------------------------------

delete_jumpbox_nsg() {
  log "--- Jump box NSG ---"

  if resource_exists "Microsoft.Network/networkSecurityGroups" "$NSG_NAME"; then
    log "Deleting NSG: $NSG_NAME"
    maybe_run "az network nsg delete \
      --resource-group '$RESOURCE_GROUP' \
      --name '$NSG_NAME' \
      --output none"
    log "NSG deleted."
  else
    log "[SKIP] NSG not found: $NSG_NAME"
  fi
}

# ---------------------------------------------------------------------------
# Optional: remove seeded demo data
# ---------------------------------------------------------------------------

remove_seed_data() {
  log "--- Removing seeded demo data ---"

  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local seed_script="${script_dir}/seed-demo-data.sh"

  if [[ ! -f "$seed_script" ]]; then
    log "WARNING: seed-demo-data.sh not found at $seed_script - skipping data cleanup."
    return
  fi

  if [[ "$DRY_RUN" == "true" ]]; then
    dry_log "RESOURCE_GROUP='$RESOURCE_GROUP' RESOURCE_PREFIX='$RESOURCE_PREFIX' ENVIRONMENT='$ENVIRONMENT' $seed_script --cleanup"
  else
    RESOURCE_GROUP="$RESOURCE_GROUP" \
    RESOURCE_PREFIX="$RESOURCE_PREFIX" \
    ENVIRONMENT="$ENVIRONMENT" \
    bash "$seed_script" --cleanup
  fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
  echo "============================================================"
  echo " CUSTOMER_NAME Bill Explainer - Demo Overlay Cleanup"
  echo " Resource group : ${RESOURCE_GROUP}"
  echo " Environment    : ${ENVIRONMENT}"
  if [[ "$DRY_RUN" == "true" ]]; then
    echo " Mode           : DRY-RUN (no changes will be made)"
  else
    echo " Mode           : LIVE (resources will be permanently deleted)"
  fi
  echo "============================================================"

  check_prerequisites
  derive_names
  confirm_deletion

  # Deletion order matters:
  # 1. VM first (releases NIC and disk attachments)
  # 2. NIC (in case VM deletion left it orphaned)
  # 3. Bastion (long operation; do before PIP to avoid dependency errors)
  # 4. Bastion PIP (Bastion must be gone first)
  # 5. NSG (subnet must be disassociated or subnet deleted first)

  delete_jumpbox_vm
  delete_jumpbox_nic
  delete_bastion
  delete_bastion_pip
  delete_jumpbox_nsg

  if [[ "$REMOVE_SEED_DATA" == "true" ]]; then
    remove_seed_data
  else
    log "Skipping seed data removal. Re-run with --seed-data to also clean Blob/Cosmos data."
  fi

  echo ""
  echo "============================================================"
  if [[ "$DRY_RUN" == "true" ]]; then
    echo " Dry-run complete. No resources were deleted."
  else
    echo " Demo overlay cleanup complete."
    echo " Core project infrastructure remains intact."
  fi
  echo "============================================================"
}

main
