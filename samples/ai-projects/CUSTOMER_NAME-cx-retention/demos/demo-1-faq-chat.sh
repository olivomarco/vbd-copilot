#!/usr/bin/env bash
# =============================================================================
# demo-1-faq-chat.sh
#
# Purpose    : Drive the CUSTOMER_NAME Intelligent Bill Explainer chat API through
#              three Italian FAQ questions, parse the SSE stream in real time,
#              and print per-request stats (tokens streamed, session ID, latency).
#              Provides an alternative to the browser widget for technical
#              audiences who want to see the raw API behaviour.
#
# Where to run: Presenter's laptop (or Azure Cloud Shell).
#               Direct HTTPS to Front Door - no VPN or Bastion required.
#               Requires: curl, jq, bash 4+
#
# Prerequisites:
#   1. FRONT_DOOR_HOSTNAME - the Azure Front Door endpoint hostname.
#      Discover with:
#        az afd endpoint list \
#          --resource-group "${RESOURCE_GROUP}" \
#          --profile-name "${AFD_PROFILE_NAME}" \
#          --query "[0].hostName" -o tsv
#   2. APIM_SUBSCRIPTION_KEY - the APIM subscription key sent as
#      Ocp-Apim-Subscription-Key. Retrieve from APIM portal or:
#        az apim show --resource-group "${RESOURCE_GROUP}" \
#          --name "${APIM_NAME}" --query "properties.subscriptionRequired"
#      Then copy a key from the APIM developer portal subscriptions page.
#
# Authentication: No Azure credentials needed from this script. All
#   backend services (OpenAI, AI Search, Cosmos DB) authenticate via
#   the Container Apps Managed Identity. The APIM subscription key is
#   the only credential this script handles.
#
# Usage:
#   export FRONT_DOOR_HOSTNAME="fd-CUSTOMER_NAME-xxx.z01.azurefd.net"
#   export APIM_SUBSCRIPTION_KEY="your-subscription-key"
#   bash demo-1-faq-chat.sh
#
# Cleanup: No Azure resources are created by this script.
#   To clear the Cosmos DB session created during the run:
#   (uncomment the az cosmosdb block at the bottom of this file)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Terminal colour helpers
# ---------------------------------------------------------------------------
BOLD=$(tput bold 2>/dev/null || echo "")
RESET=$(tput sgr0 2>/dev/null || echo "")
CYAN=$(tput setaf 6 2>/dev/null || echo "")
GREEN=$(tput setaf 2 2>/dev/null || echo "")
YELLOW=$(tput setaf 3 2>/dev/null || echo "")
RED=$(tput setaf 1 2>/dev/null || echo "")

# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------
for cmd in curl jq; do
  if ! command -v "${cmd}" &>/dev/null; then
    echo "${RED}ERROR: '${cmd}' is required but not installed.${RESET}" >&2
    exit 1
  fi
done

# ---------------------------------------------------------------------------
# Configuration - read from environment or prompt
# ---------------------------------------------------------------------------
if [[ -z "${FRONT_DOOR_HOSTNAME:-}" ]]; then
  echo ""
  echo "${YELLOW}FRONT_DOOR_HOSTNAME is not set.${RESET}"
  echo "Discover it with:"
  echo "  az afd endpoint list --resource-group \$RESOURCE_GROUP \\"
  echo "    --profile-name \$AFD_PROFILE_NAME --query \"[0].hostName\" -o tsv"
  echo ""
  read -rp "Enter Front Door hostname (e.g. fd-CUSTOMER_NAME-abc123.z01.azurefd.net): " FRONT_DOOR_HOSTNAME
fi

if [[ -z "${APIM_SUBSCRIPTION_KEY:-}" ]]; then
  echo ""
  echo "${YELLOW}APIM_SUBSCRIPTION_KEY is not set.${RESET}"
  read -rsp "Enter APIM subscription key (input hidden): " APIM_SUBSCRIPTION_KEY
  echo ""
fi

BASE_URL="https://${FRONT_DOOR_HOSTNAME}"
CHAT_ENDPOINT="${BASE_URL}/api/v1/chat"
HEALTH_ENDPOINT="${BASE_URL}/api/v1/health"

# ---------------------------------------------------------------------------
# Session state - shared across all three calls to simulate a conversation
# ---------------------------------------------------------------------------
SESSION_ID=""

# ---------------------------------------------------------------------------
# Print header
# ---------------------------------------------------------------------------
echo ""
echo "${BOLD}${CYAN}============================================================${RESET}"
echo "${BOLD}${CYAN}  CUSTOMER_NAME Bill Explainer - Demo 1: General FAQ${RESET}"
echo "${BOLD}${CYAN}  API endpoint: ${CHAT_ENDPOINT}${RESET}"
echo "${BOLD}${CYAN}============================================================${RESET}"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Health check
# ---------------------------------------------------------------------------
echo "${BOLD}[ Health Check ] GET ${HEALTH_ENDPOINT}${RESET}"
echo ""

HEALTH_RESPONSE=$(curl -s --max-time 10 "${HEALTH_ENDPOINT}" || echo "")

if [[ -z "${HEALTH_RESPONSE}" ]]; then
  echo "${RED}ERROR: Health check returned no response. Check that FRONT_DOOR_HOSTNAME is correct.${RESET}" >&2
  exit 1
fi

echo "${HEALTH_RESPONSE}" | jq . 2>/dev/null || echo "${HEALTH_RESPONSE}"
echo ""

SEARCH_OK=$(echo "${HEALTH_RESPONSE}" | jq -r '.services.search // "unknown"' 2>/dev/null)
COSMOS_OK=$(echo "${HEALTH_RESPONSE}" | jq -r '.services.cosmos // "unknown"' 2>/dev/null)
OPENAI_OK=$(echo "${HEALTH_RESPONSE}" | jq -r '.services.openai // "unknown"' 2>/dev/null)

if [[ "${SEARCH_OK}" != "true" ]] || [[ "${COSMOS_OK}" != "true" ]] || [[ "${OPENAI_OK}" != "true" ]]; then
  echo "${RED}WARNING: One or more services reported unhealthy.${RESET}"
  echo "  search=${SEARCH_OK}  cosmos=${COSMOS_OK}  openai=${OPENAI_OK}"
  echo "Check private endpoints and managed identity role assignments before continuing."
  echo ""
fi

# ---------------------------------------------------------------------------
# Function: stream_chat
#
# Sends one POST /api/v1/chat request, reads the SSE stream token by token,
# and prints each token to stdout as it arrives. Captures session_id and
# message_id from the final SSE event.
#
# Arguments:
#   $1 - question text (Italian)
#   $2 - human-readable label (e.g. "1 of 3")
# ---------------------------------------------------------------------------
stream_chat() {
  local question="$1"
  local label="$2"

  # Build JSON body - include session_id if we have one
  local body
  if [[ -n "${SESSION_ID}" ]]; then
    body=$(jq -n \
      --arg msg "${question}" \
      --arg sid "${SESSION_ID}" \
      '{"message": $msg, "session_id": $sid}')
  else
    body=$(jq -n --arg msg "${question}" '{"message": $msg}')
  fi

  echo "${BOLD}${CYAN}------------------------------------------------------------${RESET}"
  echo "${BOLD}  Question ${label}${RESET}"
  echo "${CYAN}  ${question}${RESET}"
  echo "${BOLD}${CYAN}------------------------------------------------------------${RESET}"
  echo ""
  echo "${YELLOW}  [Routing hint] No bill_ref, message <= 200 chars, no numerical"
  echo "  keywords (confronto/calcolo/differenza/...) -> ModelRouter will"
  echo "  select deployment: gpt-4o-mini (cost-efficient FAQ path)${RESET}"
  echo ""
  echo "${BOLD}  Streaming response:${RESET}"
  echo ""

  # Record start time (seconds)
  local start_ts
  start_ts=$(date +%s)

  # Capture SSE stream variables
  local token_count=0
  local captured_session_id=""
  local captured_message_id=""
  local received_done="false"

  # Stream: curl writes SSE to process substitution; while loop reads line by line.
  # Variable assignments inside this while loop ARE visible after the loop
  # because process substitution with < <() runs in the current shell context.
  while IFS= read -r sse_line; do
    # SSE lines we care about start with "data:"
    [[ "${sse_line}" == data:* ]] || continue

    local json_payload="${sse_line#data: }"

    # Skip empty payloads and the legacy [DONE] sentinel
    [[ -z "${json_payload}" ]] && continue
    [[ "${json_payload}" == "[DONE]" ]] && continue

    # Parse fields - fall back to empty string on any jq error
    local is_done token_val sid mid
    is_done=$(echo "${json_payload}" | jq -r '.done // false' 2>/dev/null || echo "false")
    token_val=$(echo "${json_payload}" | jq -r '.token // empty' 2>/dev/null || echo "")
    sid=$(echo "${json_payload}" | jq -r '.session_id // empty' 2>/dev/null || echo "")
    mid=$(echo "${json_payload}" | jq -r '.message_id // empty' 2>/dev/null || echo "")

    if [[ "${is_done}" == "true" ]]; then
      received_done="true"
      [[ -n "${sid}" ]] && captured_session_id="${sid}"
      [[ -n "${mid}" ]] && captured_message_id="${mid}"
    elif [[ -n "${token_val}" ]]; then
      printf '%s' "${token_val}"
      token_count=$((token_count + 1))
    fi

  done < <(curl -s -N \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Ocp-Apim-Subscription-Key: ${APIM_SUBSCRIPTION_KEY}" \
    --max-time 60 \
    -d "${body}" \
    "${CHAT_ENDPOINT}" 2>/dev/null)

  # End of streaming output - print a newline
  echo ""
  echo ""

  # Record end time
  local end_ts
  end_ts=$(date +%s)
  local elapsed_s=$(( end_ts - start_ts ))

  # Update shared session state
  if [[ -n "${captured_session_id}" ]]; then
    SESSION_ID="${captured_session_id}"
  fi

  # Print stats
  echo "${GREEN}  -- Stats --${RESET}"

  if [[ "${received_done}" != "true" ]]; then
    echo "${RED}  WARNING: Never received done=true event. The stream may have been"
    echo "  cut short. Check APIM timeout policy and Container Apps request timeout.${RESET}"
  fi

  printf "  %-22s %s\n" "Tokens streamed:" "${token_count}"
  printf "  %-22s %s s\n" "Wall-clock time:" "${elapsed_s}"
  printf "  %-22s %s\n" "Session ID:" "${SESSION_ID:-not captured}"
  printf "  %-22s %s\n" "Message ID:" "${captured_message_id:-not captured}"
  printf "  %-22s %s\n" "Model (routing hint):" "gpt-4o-mini"
  echo ""
  echo "  To verify in App Insights (run this Kusto query):"
  echo "  traces"
  echo "  | where timestamp > ago(5m)"
  echo "  | where message contains \"Query classified\""
  echo "  | project timestamp, message"
  echo "  | order by timestamp desc | take 10"
  echo ""
}

# ---------------------------------------------------------------------------
# The three demo questions
# All route to GPT-4o-mini because:
#   - bill_ref: null (not sent)
#   - message length: all under 200 chars
#   - no keywords from _COMPLEX_KEYWORDS set in model_router.py
# ---------------------------------------------------------------------------
QUESTION_1="Cosa sono gli oneri di sistema sulla mia bolletta?"
QUESTION_2="Come si calcola la quota potenza?"
QUESTION_3="Cosa significa il codice POD?"

stream_chat "${QUESTION_1}" "1 of 3 - oneri di sistema (main WOW moment)"
stream_chat "${QUESTION_2}" "2 of 3 - quota potenza (follow-up, same session)"
stream_chat "${QUESTION_3}" "3 of 3 - codice POD (quick close, same session)"

# ---------------------------------------------------------------------------
# Final summary
# ---------------------------------------------------------------------------
echo "${BOLD}${CYAN}============================================================${RESET}"
echo "${BOLD}  Demo 1 complete${RESET}"
echo "${BOLD}${CYAN}============================================================${RESET}"
echo ""
echo "  All three questions used the same Cosmos DB session:"
echo "  Session ID: ${SESSION_ID:-not captured}"
echo ""
echo "  To retrieve full conversation history from Cosmos DB via API:"
echo "  curl -s \\"
echo "    -H 'Ocp-Apim-Subscription-Key: \${APIM_SUBSCRIPTION_KEY}' \\"
echo "    '${BASE_URL}/api/v1/sessions/${SESSION_ID}' | jq ."
echo ""
echo "  Next: Demo 2 will add a bill reference (IT001-2024-DEMO) to this"
echo "  session. The ModelRouter will then select GPT-4o for personalised"
echo "  bill analysis. See demo-2-bill-lookup.sh."
echo ""

# ---------------------------------------------------------------------------
# Optional cleanup (uncomment to delete the session from Cosmos DB after demo)
# ---------------------------------------------------------------------------
# RESOURCE_GROUP="${RESOURCE_GROUP:-}"
# COSMOS_ACCOUNT="${COSMOS_ACCOUNT:-}"
# if [[ -n "${RESOURCE_GROUP}" ]] && [[ -n "${COSMOS_ACCOUNT}" ]] && [[ -n "${SESSION_ID}" ]]; then
#   echo "Cleaning up Cosmos DB session ${SESSION_ID} ..."
#   az cosmosdb sql document delete \
#     --resource-group "${RESOURCE_GROUP}" \
#     --account-name "${COSMOS_ACCOUNT}" \
#     --database-name "billexplainer" \
#     --container-name "sessions" \
#     --partition-key-value "${SESSION_ID}" \
#     --id "${SESSION_ID}" \
#     --yes
#   echo "Session deleted."
# fi
