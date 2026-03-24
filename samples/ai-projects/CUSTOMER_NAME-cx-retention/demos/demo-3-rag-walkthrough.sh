#!/usr/bin/env bash
# =============================================================================
# demo-3-rag-walkthrough.sh
#
# Purpose  : Demo 3 companion script - queries AI Search REST API directly,
#            dumps Cosmos DB session + messages, and tails Container Apps logs.
#            Demonstrates that all data plane access works via Azure AD tokens
#            (managed identity / CLI credentials). Zero access keys used.
#
# Where    : Run from the jump box terminal (Git Bash, WSL, or Azure Cloud Shell
#            on CUSTOMER_NAME-bill-jumpbox-dev). The jump box must be on the VNet
#            with private DNS resolving *.search.windows.net and *.documents.azure.com.
#
# Prerequisites:
#   - Azure CLI logged in: az account show
#   - jq installed: jq --version
#   - Python 3 with azure-cosmos and azure-identity packages installed
#       pip install azure-cosmos azure-identity --quiet
#   - Sufficient RBAC roles:
#       Search Index Data Reader  on CUSTOMER_NAME-bill-search-dev
#       Cosmos DB Built-in Data Reader  on CUSTOMER_NAME-bill-cosmos-dev
#       Reader  on the Resource Group
#
# Environment variables (all have defaults - override as needed):
#   RESOURCE_GROUP   - Resource group containing all resources
#   RESOURCE_PREFIX  - Naming prefix used in Bicep (default: CUSTOMER_NAME-bill)
#   ENVIRONMENT      - Environment suffix (default: dev)
#   INDEX_NAME       - AI Search index name (default: CUSTOMER_NAME-knowledge)
#   SEARCH_QUERY     - Query text to send to AI Search (default: oneri di sistema)
#   SESSION_ID       - Cosmos DB session ID to inspect (optional, skipped if empty)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-CUSTOMER_NAME-bill-dev}"
RESOURCE_PREFIX="${RESOURCE_PREFIX:-CUSTOMER_NAME-bill}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
INDEX_NAME="${INDEX_NAME:-CUSTOMER_NAME-knowledge}"
SEARCH_QUERY="${SEARCH_QUERY:-oneri di sistema}"
SESSION_ID="${SESSION_ID:-}"

SEARCH_SERVICE_NAME="${RESOURCE_PREFIX}-search-${ENVIRONMENT}"
COSMOS_ACCOUNT_NAME="${RESOURCE_PREFIX}-cosmos-${ENVIRONMENT}"
COSMOS_DATABASE="billexplainer"
OPENAI_ACCOUNT_NAME="${RESOURCE_PREFIX}-oai-${ENVIRONMENT}"

SEARCH_API_VERSION="2024-07-01"
SEARCH_ENDPOINT="https://${SEARCH_SERVICE_NAME}.search.windows.net"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
section() {
    echo ""
    echo "============================================================"
    echo "  $1"
    echo "============================================================"
}

check_prereqs() {
    section "Checking prerequisites"

    echo "[1/4] Verifying Azure CLI login..."
    az account show --query "user.name" -o tsv --only-show-errors \
        || { echo "ERROR: Not logged in. Run: az login"; exit 1; }

    echo "[2/4] Verifying jq is installed..."
    jq --version --only-show-errors 2>/dev/null \
        || { echo "ERROR: jq not found. Install: apt-get install jq  or  choco install jq"; exit 1; }

    echo "[3/4] Verifying Python 3 is available..."
    python3 --version 2>/dev/null \
        || { echo "ERROR: python3 not found"; exit 1; }

    echo "[4/4] Verifying azure-cosmos Python package..."
    python3 -c "import azure.cosmos" 2>/dev/null \
        || { echo "Installing azure-cosmos and azure-identity..."; pip install azure-cosmos azure-identity --quiet; }

    echo "All prerequisites met."
}

# ---------------------------------------------------------------------------
# Discover resources (avoids hardcoded names at runtime)
# ---------------------------------------------------------------------------
discover_resources() {
    section "Discovering resources in ${RESOURCE_GROUP}"

    echo "Listing Container Apps in resource group..."
    CA_NAME=$(az containerapp list \
        --resource-group "$RESOURCE_GROUP" \
        --query "[?contains(name, '${RESOURCE_PREFIX}')].name | [0]" \
        -o tsv --only-show-errors 2>/dev/null || echo "")

    if [ -z "$CA_NAME" ]; then
        echo "WARNING: No Container App found matching prefix '${RESOURCE_PREFIX}' in ${RESOURCE_GROUP}"
        echo "         Container Apps log step will be skipped."
    else
        echo "  Found Container App : ${CA_NAME}"
    fi

    echo "Resolving AI Search endpoint..."
    if ! nslookup "${SEARCH_SERVICE_NAME}.search.windows.net" > /dev/null 2>&1; then
        echo "WARNING: DNS lookup for ${SEARCH_SERVICE_NAME}.search.windows.net failed."
        echo "         Confirm the jump box is on the VNet with correct private DNS zones."
    else
        echo "  AI Search DNS resolves : ${SEARCH_ENDPOINT}"
    fi

    echo "Resolving Cosmos DB endpoint..."
    COSMOS_ENDPOINT="https://${COSMOS_ACCOUNT_NAME}.documents.azure.com:443/"
    if ! nslookup "${COSMOS_ACCOUNT_NAME}.documents.azure.com" > /dev/null 2>&1; then
        echo "WARNING: DNS lookup for ${COSMOS_ACCOUNT_NAME}.documents.azure.com failed."
        echo "         Confirm private DNS zone privatelink.documents.azure.com is linked to VNet."
    else
        echo "  Cosmos DB DNS resolves  : ${COSMOS_ENDPOINT}"
    fi
}

# ---------------------------------------------------------------------------
# STEP 1 - AI Search: hybrid query via REST API with bearer token
# ---------------------------------------------------------------------------
run_ai_search_query() {
    section "Step 1 - AI Search hybrid query (REST API, bearer token auth)"

    echo "Acquiring bearer token for AI Search data plane..."
    SEARCH_TOKEN=$(az account get-access-token \
        --resource "https://search.azure.com" \
        --query "accessToken" \
        -o tsv --only-show-errors)

    echo "Token acquired. Scope: https://search.azure.com"
    echo ""
    echo "Query  : ${SEARCH_QUERY}"
    echo "Index  : ${INDEX_NAME}"
    echo "Top    : 3"
    echo "Mode   : semantic + hybrid (BM25 + vector + semantic reranker)"
    echo ""

    SEARCH_RESPONSE=$(curl -s -X POST \
        "${SEARCH_ENDPOINT}/indexes/${INDEX_NAME}/docs/search?api-version=${SEARCH_API_VERSION}" \
        -H "Authorization: Bearer ${SEARCH_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{
              \"search\": \"${SEARCH_QUERY}\",
              \"queryType\": \"semantic\",
              \"semanticConfiguration\": \"default\",
              \"top\": 3,
              \"select\": \"content,sourceDocument,category,title\",
              \"vectorQueries\": [
                {
                  \"kind\": \"text\",
                  \"text\": \"${SEARCH_QUERY}\",
                  \"fields\": \"contentVector\",
                  \"k\": 3
                }
              ]
            }")

    echo "--- Raw response (pretty-printed) ---"
    echo "$SEARCH_RESPONSE" | jq '.' 2>/dev/null || echo "$SEARCH_RESPONSE"

    echo ""
    echo "--- Reranker scores summary ---"
    echo "$SEARCH_RESPONSE" | jq -r '
        .value[] |
        "  reranker_score: \(.["@search.reranker_score"] // "n/a") | category: \(.category // "n/a") | source: \(.sourceDocument // "n/a")"
    ' 2>/dev/null || echo "  (jq parse failed - check raw response above)"

    echo ""
    echo "--- Top result content preview (first 300 chars) ---"
    echo "$SEARCH_RESPONSE" | jq -r '.value[0].content // "no content"' 2>/dev/null \
        | cut -c1-300
    echo "..."
}

# ---------------------------------------------------------------------------
# STEP 2 - Cosmos DB: list sessions and messages via Python + DefaultAzureCredential
# ---------------------------------------------------------------------------
run_cosmos_query() {
    section "Step 2 - Cosmos DB: sessions and messages (DefaultAzureCredential, no keys)"

    echo "Cosmos DB endpoint : ${COSMOS_ENDPOINT}"
    echo "Database           : ${COSMOS_DATABASE}"
    echo ""

    if [ -n "$SESSION_ID" ]; then
        echo "Querying session ID: ${SESSION_ID}"
    else
        echo "SESSION_ID not set - will show the 3 most recent sessions instead."
        echo "To inspect a specific session, export SESSION_ID=<uuid> and re-run."
    fi
    echo ""

    python3 - << PYEOF
import sys
import json

try:
    from azure.cosmos import CosmosClient
    from azure.identity import DefaultAzureCredential
except ImportError:
    print("ERROR: Missing packages. Run: pip install azure-cosmos azure-identity")
    sys.exit(1)

COSMOS_ENDPOINT = "${COSMOS_ENDPOINT}"
DATABASE_NAME   = "${COSMOS_DATABASE}"
SESSION_ID      = "${SESSION_ID}"

print("Authenticating with DefaultAzureCredential (uses Azure CLI token on jump box)...")
credential  = DefaultAzureCredential()
client      = CosmosClient(url=COSMOS_ENDPOINT, credential=credential)
database    = client.get_database_client(DATABASE_NAME)
sessions_c  = database.get_container_client("sessions")
messages_c  = database.get_container_client("messages")

# ----- Sessions -----
print("")
print("--- Sessions container ---")
if SESSION_ID:
    query = "SELECT * FROM c WHERE c.id = @sid"
    params = [{"name": "@sid", "value": SESSION_ID}]
else:
    query = "SELECT TOP 3 c.id, c.sessionId, c.createdAt, c.lastActive, c.billRef, c.messageCount FROM c ORDER BY c._ts DESC"
    params = []

sessions = list(sessions_c.query_items(
    query=query,
    parameters=params,
    enable_cross_partition_query=True,
))

if not sessions:
    print("  No sessions found. Check SESSION_ID or run Demo 2 first.")
else:
    for s in sessions:
        print(json.dumps({
            "id":           s.get("id"),
            "createdAt":    s.get("createdAt"),
            "lastActive":   s.get("lastActive"),
            "billRef":      s.get("billRef"),
            "messageCount": s.get("messageCount"),
        }, indent=2))

# ----- Messages -----
print("")
print("--- Messages container (most recent 5) ---")
if SESSION_ID:
    msg_query = (
        "SELECT TOP 5 c.id, c.role, c.timestamp, c.modelUsed, "
        "c.promptTokens, c.completionTokens, "
        "SUBSTRING(c.content, 0, 120) AS contentPreview "
        "FROM c WHERE c.sessionId = @sid ORDER BY c.timestamp DESC"
    )
    msg_params = [{"name": "@sid", "value": SESSION_ID}]
    messages = list(messages_c.query_items(
        query=msg_query,
        parameters=msg_params,
        partition_key=SESSION_ID,
    ))
else:
    print("  (Set SESSION_ID to inspect messages for a specific session)")
    messages = []

if messages:
    for m in messages:
        print(json.dumps(m, indent=2))
else:
    if SESSION_ID:
        print("  No messages found for session:", SESSION_ID)

print("")
print("TTL reminder:")
print("  sessions  container defaultTtl = 86400   (24 hours)")
print("  messages  container defaultTtl = 2592000 (30 days)")
print("  feedback  container defaultTtl = 2592000 (30 days)")
print("  disableLocalAuth = true on the Cosmos account: no connection strings exist.")
PYEOF
}

# ---------------------------------------------------------------------------
# STEP 3 - Container Apps: tail recent log lines
# ---------------------------------------------------------------------------
run_container_logs() {
    section "Step 3 - Container Apps log stream (last 20 lines)"

    if [ -z "${CA_NAME:-}" ]; then
        echo "SKIPPED: No Container App name discovered. Check RESOURCE_GROUP and RESOURCE_PREFIX."
        return
    fi

    echo "Container App : ${CA_NAME}"
    echo "Resource Group: ${RESOURCE_GROUP}"
    echo ""
    echo "Fetching last 20 log lines (look for 'Pipeline:' and 'Hybrid search returned')..."
    echo ""

    az containerapp logs show \
        --name "$CA_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --tail 20 \
        --only-show-errors 2>/dev/null \
    || echo "  Could not retrieve logs. The Container App may be scaled to zero."
    echo ""
    echo "Key log lines to point out during the demo:"
    echo "  'Pipeline: session=<uuid> model=gpt-4o-mini needs_billing=False'"
    echo "      -> rag_pipeline.py:72 - fires before any OpenAI call"
    echo "  'Hybrid search returned 5 results for query=...'"
    echo "      -> search_service.py:103 - confirms 5 chunks entered the prompt context"
}

# ---------------------------------------------------------------------------
# STEP 4 - Azure OpenAI: list model deployments
# ---------------------------------------------------------------------------
show_openai_deployments() {
    section "Step 4 - Azure OpenAI model deployments"

    echo "OpenAI account: ${OPENAI_ACCOUNT_NAME}"
    echo ""

    az cognitiveservices account deployment list \
        --name "$OPENAI_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "[].{name:name, model:properties.model.name, sku:sku.name, capacity:sku.capacity}" \
        -o table \
        --only-show-errors 2>/dev/null \
    || echo "  Could not retrieve deployments - check Reader role on the resource group."

    echo ""
    echo "All three deployments use SKU 'DataZoneStandard' (EU data boundary - GDPR compliant)."
    echo "  gpt-4o              -> complex queries (bill_ref present, >200 chars, comparison keywords, turn>5)"
    echo "  gpt-4o-mini         -> simple FAQ queries (~80% of traffic)"
    echo "  text-embedding-3-small -> 1536-dim vectors for hybrid search (contentVector field)"
}

# ---------------------------------------------------------------------------
# Cleanup reference (commented out - do not run during demo)
# ---------------------------------------------------------------------------
# cleanup_demo_session() {
#     # Deletes the demo session and all messages/feedback via the API.
#     # Triggers the GDPR erasure path in conversation_manager.py:delete_session()
#     # Only run after the demo to reset state.
#     #
#     # CA_FQDN=$(az containerapp show \
#     #     --name "$CA_NAME" \
#     #     --resource-group "$RESOURCE_GROUP" \
#     #     --query "properties.configuration.ingress.fqdn" -o tsv --only-show-errors)
#     # curl -s -X DELETE "https://${CA_FQDN}/sessions/${SESSION_ID}" \
#     #     -H "Authorization: Bearer $(az account get-access-token \
#     #         --query accessToken -o tsv --only-show-errors)"
# }

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    echo ""
    echo "CUSTOMER_NAME Intelligent Bill Explainer - Demo 3 Companion Script"
    echo "================================================================"
    echo "Resource Group  : ${RESOURCE_GROUP}"
    echo "Resource Prefix : ${RESOURCE_PREFIX}"
    echo "Environment     : ${ENVIRONMENT}"
    echo "Index Name      : ${INDEX_NAME}"
    echo "Search Query    : ${SEARCH_QUERY}"
    echo "Session ID      : ${SESSION_ID:-<not set - will show recent sessions>}"
    echo ""

    check_prereqs
    discover_resources
    run_ai_search_query
    run_cosmos_query
    run_container_logs
    show_openai_deployments

    echo ""
    section "Demo 3 complete"
    echo "Next: Demo 4 - Application Insights, APIM rate limiting, and security posture."
    echo ""
}

main "$@"
