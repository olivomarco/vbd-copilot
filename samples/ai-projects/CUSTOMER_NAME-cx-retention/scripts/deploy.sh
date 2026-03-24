#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# CUSTOMER_NAME Intelligent Bill Explainer - Deployment Script
# ---------------------------------------------------------------------------
# Idempotent script that provisions Azure infrastructure via Bicep and
# deploys the application container to Azure Container Apps.
#
# Usage:
#   ./deploy.sh --resource-group rg-CUSTOMER_NAME-dev --environment dev
#   ./deploy.sh --resource-group rg-CUSTOMER_NAME-prod --environment prod --infra-only
#   ./deploy.sh --resource-group rg-CUSTOMER_NAME-dev --app-only
#   ./deploy.sh --help
# ---------------------------------------------------------------------------
set -euo pipefail

# ---------------------------------------------------------------------------
# Constants and defaults
# ---------------------------------------------------------------------------
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
readonly INFRA_DIR="${PROJECT_DIR}/infra"
readonly SRC_DIR="${PROJECT_DIR}/src"
readonly DEPLOYMENT_NAME="CUSTOMER_NAME-bill-$(date +%Y%m%d-%H%M%S)"

LOCATION="swedencentral"
ENVIRONMENT="dev"
RESOURCE_GROUP=""
INFRA_ONLY=false
APP_ONLY=false

# Resource naming convention (must match Bicep resourcePrefix)
readonly RESOURCE_PREFIX="CUSTOMER_NAME-bill"

# ---------------------------------------------------------------------------
# Color codes for terminal output
# ---------------------------------------------------------------------------
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
log_info() {
    echo -e "${GREEN}[INFO]${NC}  $(date '+%Y-%m-%dT%H:%M:%S') $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC}  $(date '+%Y-%m-%dT%H:%M:%S') $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%dT%H:%M:%S') $*"
}

log_step() {
    echo ""
    echo -e "${BLUE}=== $* ===${NC}"
    echo ""
}

# ---------------------------------------------------------------------------
# show_help - Print usage instructions
# ---------------------------------------------------------------------------
show_help() {
    cat <<EOF
CUSTOMER_NAME Intelligent Bill Explainer - Deployment Script

USAGE:
    $(basename "$0") [OPTIONS]

OPTIONS:
    --resource-group, -g    Azure resource group name (required)
    --location, -l          Azure region (default: swedencentral)
    --environment, -e       Target environment: dev or prod (default: dev)
    --infra-only            Deploy infrastructure only (skip app deployment)
    --app-only              Deploy application only (skip infrastructure)
    --help, -h              Show this help message

EXAMPLES:
    # Full deployment to dev
    $(basename "$0") -g rg-CUSTOMER_NAME-dev -e dev

    # Infrastructure only to prod in swedencentral
    $(basename "$0") -g rg-CUSTOMER_NAME-prod -e prod --infra-only

    # Update application image only
    $(basename "$0") -g rg-CUSTOMER_NAME-dev -e dev --app-only

ENVIRONMENT VARIABLES:
    AZURE_SUBSCRIPTION_ID   Override the active subscription
    ACR_NAME                Override auto-detected ACR name
    IMAGE_TAG               Override the Docker image tag (default: git SHA or 'latest')

EOF
    exit 0
}

# ---------------------------------------------------------------------------
# parse_args - Parse command-line arguments
# ---------------------------------------------------------------------------
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --resource-group|-g)
                RESOURCE_GROUP="$2"
                shift 2
                ;;
            --location|-l)
                LOCATION="$2"
                shift 2
                ;;
            --environment|-e)
                ENVIRONMENT="$2"
                shift 2
                ;;
            --infra-only)
                INFRA_ONLY=true
                shift
                ;;
            --app-only)
                APP_ONLY=true
                shift
                ;;
            --help|-h)
                show_help
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Run '$(basename "$0") --help' for usage."
                exit 1
                ;;
        esac
    done

    # Validate required arguments
    if [[ -z "$RESOURCE_GROUP" ]]; then
        log_error "Missing required argument: --resource-group"
        echo "Run '$(basename "$0") --help' for usage."
        exit 1
    fi

    if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
        log_error "Environment must be 'dev' or 'prod'. Got: $ENVIRONMENT"
        exit 1
    fi

    if [[ "$INFRA_ONLY" == true && "$APP_ONLY" == true ]]; then
        log_error "Cannot specify both --infra-only and --app-only"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# validate_prerequisites - Ensure required tools are installed and configured
# ---------------------------------------------------------------------------
validate_prerequisites() {
    log_step "Validating prerequisites"

    # Check az CLI
    if ! command -v az &>/dev/null; then
        log_error "Azure CLI (az) is not installed. Install from https://aka.ms/install-az-cli"
        exit 1
    fi
    log_info "Azure CLI found: $(az version --query '"azure-cli"' -o tsv 2>/dev/null || echo 'unknown')"

    # Check az login status
    if ! az account show &>/dev/null; then
        log_error "Not logged in to Azure. Run 'az login' first."
        exit 1
    fi
    log_info "Logged in as: $(az account show --query user.name -o tsv)"

    # Display active subscription
    local current_sub
    current_sub="$(az account show --query '{name:name, id:id}' -o tsv)"
    log_info "Active subscription: ${current_sub}"

    # Override subscription if requested
    if [[ -n "${AZURE_SUBSCRIPTION_ID:-}" ]]; then
        log_info "Setting subscription to: ${AZURE_SUBSCRIPTION_ID}"
        az account set --subscription "$AZURE_SUBSCRIPTION_ID"
    fi

    # Check Docker (only if we need to build the app)
    if [[ "$INFRA_ONLY" != true ]]; then
        if ! command -v docker &>/dev/null; then
            log_error "Docker is not installed. Required for building the application image."
            exit 1
        fi
        log_info "Docker found: $(docker --version 2>/dev/null | head -1)"
    fi

    # Verify Bicep is available (only if we need infra)
    if [[ "$APP_ONLY" != true ]]; then
        if ! az bicep version &>/dev/null; then
            log_warn "Bicep CLI not found. Installing via az CLI..."
            az bicep install
        fi
        log_info "Bicep found: $(az bicep version 2>/dev/null | head -1)"
    fi

    # Ensure resource group exists (create if it does not)
    if az group show --name "$RESOURCE_GROUP" &>/dev/null; then
        log_info "Resource group '$RESOURCE_GROUP' exists"
    else
        log_info "Creating resource group '$RESOURCE_GROUP' in '$LOCATION'..."
        az group create \
            --name "$RESOURCE_GROUP" \
            --location "$LOCATION" \
            --tags "project=CUSTOMER_NAME-bill-explainer" "environment=$ENVIRONMENT" \
            --output none
        log_info "Resource group created"
    fi

    log_info "Prerequisites validated successfully"
}

# ---------------------------------------------------------------------------
# deploy_infra - Deploy Azure infrastructure using Bicep
# ---------------------------------------------------------------------------
deploy_infra() {
    log_step "Deploying infrastructure (${ENVIRONMENT})"

    local param_file="${INFRA_DIR}/parameters/${ENVIRONMENT}.bicepparam"
    if [[ ! -f "$param_file" ]]; then
        log_error "Parameter file not found: $param_file"
        exit 1
    fi

    log_info "Template:   ${INFRA_DIR}/main.bicep"
    log_info "Parameters: ${param_file}"
    log_info "Deployment: ${DEPLOYMENT_NAME}"

    # Validate the template first
    log_info "Validating Bicep template..."
    az deployment group validate \
        --resource-group "$RESOURCE_GROUP" \
        --template-file "${INFRA_DIR}/main.bicep" \
        --parameters "$param_file" \
        --output none

    log_info "Validation passed. Starting deployment..."

    # Deploy with incremental mode (idempotent)
    az deployment group create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$DEPLOYMENT_NAME" \
        --template-file "${INFRA_DIR}/main.bicep" \
        --parameters "$param_file" \
        --mode Incremental \
        --output none \
        --no-wait false

    log_info "Infrastructure deployment completed"

    # Display key outputs
    log_info "Deployment outputs:"
    az deployment group show \
        --resource-group "$RESOURCE_GROUP" \
        --name "$DEPLOYMENT_NAME" \
        --query "properties.outputs.{FrontDoor:frontDoorHostname.value, APIM:apimGatewayUrl.value, ContainerApp:containerAppFqdn.value}" \
        --output table
}

# ---------------------------------------------------------------------------
# get_acr_name - Resolve the ACR name from env var or resource group
# ---------------------------------------------------------------------------
get_acr_name() {
    if [[ -n "${ACR_NAME:-}" ]]; then
        echo "$ACR_NAME"
        return
    fi

    # Discover ACR in the resource group
    local acr_name
    acr_name="$(az acr list \
        --resource-group "$RESOURCE_GROUP" \
        --query "[0].name" \
        -o tsv 2>/dev/null || true)"

    if [[ -z "$acr_name" || "$acr_name" == "None" ]]; then
        # Create ACR if none exists - use sanitized name (alphanumeric only, max 50 chars)
        acr_name="$(echo "${RESOURCE_PREFIX}acr${ENVIRONMENT}" | tr -d '-')"
        log_warn "No ACR found in resource group. Creating '${acr_name}'..."
        az acr create \
            --resource-group "$RESOURCE_GROUP" \
            --name "$acr_name" \
            --sku Basic \
            --admin-enabled true \
            --output none
        log_info "ACR '${acr_name}' created"
    fi

    echo "$acr_name"
}

# ---------------------------------------------------------------------------
# get_image_tag - Determine the Docker image tag
# ---------------------------------------------------------------------------
get_image_tag() {
    if [[ -n "${IMAGE_TAG:-}" ]]; then
        echo "$IMAGE_TAG"
        return
    fi

    # Use git short SHA if available, otherwise 'latest'
    if command -v git &>/dev/null && git -C "$PROJECT_DIR" rev-parse --short HEAD &>/dev/null; then
        git -C "$PROJECT_DIR" rev-parse --short HEAD
    else
        echo "latest"
    fi
}

# ---------------------------------------------------------------------------
# build_and_push_image - Build Docker image and push to ACR
# ---------------------------------------------------------------------------
build_and_push_image() {
    local acr_name="$1"
    local image_tag="$2"

    log_step "Building and pushing container image"

    local login_server
    login_server="$(az acr show --name "$acr_name" --query loginServer -o tsv)"
    local full_image="${login_server}/CUSTOMER_NAME-bill-explainer:${image_tag}"

    log_info "ACR:       ${acr_name}"
    log_info "Image:     ${full_image}"
    log_info "Context:   ${SRC_DIR}"

    # Login to ACR
    log_info "Authenticating to ACR..."
    az acr login --name "$acr_name"

    # Build the Docker image
    log_info "Building Docker image..."
    docker build \
        --tag "$full_image" \
        --tag "${login_server}/CUSTOMER_NAME-bill-explainer:latest" \
        --file "${SRC_DIR}/Dockerfile" \
        "$SRC_DIR"

    # Push both tags
    log_info "Pushing image to ACR..."
    docker push "$full_image"
    docker push "${login_server}/CUSTOMER_NAME-bill-explainer:latest"

    log_info "Image pushed successfully: ${full_image}"

    # Return the full image reference
    echo "$full_image"
}

# ---------------------------------------------------------------------------
# deploy_app - Update the Container App with the new image
# ---------------------------------------------------------------------------
deploy_app() {
    log_step "Deploying application"

    local acr_name
    acr_name="$(get_acr_name)"

    local image_tag
    image_tag="$(get_image_tag)"

    # Build and push returns the full image name
    local full_image
    full_image="$(build_and_push_image "$acr_name" "$image_tag")"

    # Determine the Container App name
    local container_app_name="${RESOURCE_PREFIX}-ca-${ENVIRONMENT}"

    # Check if the Container App exists
    if ! az containerapp show --name "$container_app_name" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
        log_error "Container App '${container_app_name}' not found in resource group '${RESOURCE_GROUP}'."
        log_error "Run with --infra-only first or without --app-only to deploy infrastructure."
        exit 1
    fi

    local login_server
    login_server="$(az acr show --name "$acr_name" --query loginServer -o tsv)"

    # Configure ACR credentials on the Container App
    log_info "Configuring ACR registry on Container App..."
    az containerapp registry set \
        --name "$container_app_name" \
        --resource-group "$RESOURCE_GROUP" \
        --server "$login_server" \
        --identity system \
        --output none 2>/dev/null || {
            # Fallback: use admin credentials if managed identity registry access is not set up
            log_warn "System identity registry access failed. Falling back to admin credentials..."
            local acr_password
            acr_password="$(az acr credential show --name "$acr_name" --query "passwords[0].value" -o tsv)"
            az containerapp registry set \
                --name "$container_app_name" \
                --resource-group "$RESOURCE_GROUP" \
                --server "$login_server" \
                --username "$acr_name" \
                --password "$acr_password" \
                --output none
        }

    # Update the Container App with the new image
    log_info "Updating Container App '${container_app_name}' with image '${full_image}'..."
    az containerapp update \
        --name "$container_app_name" \
        --resource-group "$RESOURCE_GROUP" \
        --image "$full_image" \
        --output none

    log_info "Application deployed successfully"

    # Show the Container App FQDN
    local fqdn
    fqdn="$(az containerapp show \
        --name "$container_app_name" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.configuration.ingress.fqdn" \
        -o tsv 2>/dev/null || echo 'N/A')"
    log_info "Container App FQDN: ${fqdn}"
}

# ---------------------------------------------------------------------------
# main - Orchestrate the deployment
# ---------------------------------------------------------------------------
main() {
    parse_args "$@"

    echo ""
    echo -e "${BLUE}CUSTOMER_NAME Intelligent Bill Explainer - Deployment${NC}"
    echo -e "${BLUE}=================================================${NC}"
    echo ""
    log_info "Environment:    ${ENVIRONMENT}"
    log_info "Resource Group: ${RESOURCE_GROUP}"
    log_info "Location:       ${LOCATION}"
    log_info "Infra Only:     ${INFRA_ONLY}"
    log_info "App Only:       ${APP_ONLY}"

    validate_prerequisites

    if [[ "$APP_ONLY" != true ]]; then
        deploy_infra
    fi

    if [[ "$INFRA_ONLY" != true ]]; then
        deploy_app
    fi

    log_step "Deployment complete"
    log_info "Environment '${ENVIRONMENT}' deployment finished successfully."
    log_info "Run 'tests/validate.sh --live' to verify the deployment."
}

main "$@"
