#!/usr/bin/env bash
# =============================================================================
# demo-4-rate-limit-and-observability.sh
#
# Purpose:
#   Drive live traffic against the CUSTOMER_NAME Bill Explainer API to generate
#   observable telemetry in Application Insights Live Metrics, then trigger
#   the APIM rate limit (10 req/min/IP) and display the 429 Retry-After
#   response on screen.
#
# Where to run:
#   Jump box VM (accessed via Azure Bastion).
#   The jump box sits inside the VNet and resolves the Front Door hostname
#   correctly. All requests travel outbound through Front Door -> APIM ->
#   Container App.
#   Do NOT run from the presenter laptop; APIM rate limiting is keyed on the
#   calling IP address and will give different results from outside the VNet.
#
# Prerequisites:
#   - curl (installed on jump box by default)
#   - FRONT_DOOR_HOSTNAME env var set to the Front Door endpoint hostname
#     e.g. export FRONT_DOOR_HOSTNAME="CUSTOMER_NAME-bill-ep-dev.z01.azurefd.net"
#   - Optional: APIM_SUBSCRIPTION_KEY env var if the APIM product requires
#     a subscription key (set in Ocp-Apim-Subscription-Key header)
#   - Application Insights Live Metrics tab open in portal before running
#
# Usage:
#   bash demo-4-rate-limit-and-observability.sh [--dry-run] [--skip-warmup]
#
# Flags:
#   --dry-run      Print what the script would do without calling the API
#   --skip-warmup  Skip the 3-request concurrent warm-up phase and go
#                  straight to the rate-limit trigger phase
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Colour codes for terminal output at font size 18+
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# ---------------------------------------------------------------------------
# Parse flags
# ---------------------------------------------------------------------------
DRY_RUN=false
SKIP_WARMUP=false

for arg in "$@"; do
  case "$arg" in
    --dry-run)
      DRY_RUN=true
      ;;
    --skip-warmup)
      SKIP_WARMUP=true
      ;;
    *)
      echo "Unknown flag: $arg" >&2
      echo "Usage: $0 [--dry-run] [--skip-warmup]" >&2
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Validate required environment variables
# ---------------------------------------------------------------------------
if [[ -z "${FRONT_DOOR_HOSTNAME:-}" ]]; then
  echo -e "${RED}ERROR: FRONT_DOOR_HOSTNAME is not set.${RESET}"
  echo ""
  echo "Export the Front Door endpoint hostname before running:"
  echo "  export FRONT_DOOR_HOSTNAME=\"CUSTOMER_NAME-bill-ep-dev.z01.azurefd.net\""
  echo ""
  echo "To find it:"
  echo "  az afd endpoint list --profile-name CUSTOMER_NAME-bill-afd-dev \\"
  echo "    --resource-group \$(az group list --query \"[?contains(name,'CUSTOMER_NAME-bill')].name\" -o tsv | head -1) \\"
  echo "    --query \"[0].hostName\" -o tsv"
  exit 1
fi

BASE_URL="https://${FRONT_DOOR_HOSTNAME}/api/v1/chat"
SESSION_ID="demo-rate-limit-session"

# Optional subscription key header
SUBSCRIPTION_KEY_HEADER=""
if [[ -n "${APIM_SUBSCRIPTION_KEY:-}" ]]; then
  SUBSCRIPTION_KEY_HEADER="Ocp-Apim-Subscription-Key: ${APIM_SUBSCRIPTION_KEY}"
fi

# ---------------------------------------------------------------------------
# Helper: build curl arguments array
# ---------------------------------------------------------------------------
build_curl_args() {
  local message="$1"
  local args=(
    --silent
    --max-time 30
    --write-out "\n%{http_code} %{time_total}"
    --header "Content-Type: application/json"
    --header "X-Session-ID: ${SESSION_ID}"
    --data "{\"message\": \"${message}\", \"session_id\": \"${SESSION_ID}\"}"
    "${BASE_URL}"
  )
  if [[ -n "${SUBSCRIPTION_KEY_HEADER}" ]]; then
    args=(--header "${SUBSCRIPTION_KEY_HEADER}" "${args[@]}")
  fi
  echo "${args[@]}"
}

# ---------------------------------------------------------------------------
# Helper: fire a single request and return status + timing
# Returns: "<http_code> <time_total_s>" on stdout, Retry-After on FD3
# ---------------------------------------------------------------------------
fire_request() {
  local message="$1"
  local label="$2"

  local raw_response
  local http_code
  local time_total
  local retry_after=""

  # We use a temp file for headers so we can extract Retry-After
  local header_file
  header_file="$(mktemp)"

  if [[ "${DRY_RUN}" == "true" ]]; then
    echo -e "  ${CYAN}[DRY-RUN]${RESET} Would POST to ${BASE_URL}"
    echo -e "  ${CYAN}[DRY-RUN]${RESET} Body: {\"message\": \"${message}\", \"session_id\": \"${SESSION_ID}\"}"
    rm -f "${header_file}"
    echo "200 0.000"
    return 0
  fi

  # Fire request; capture response body + write-out on the last two lines
  raw_response=$(
    curl \
      --silent \
      --max-time 30 \
      --dump-header "${header_file}" \
      --write-out "\n%{http_code} %{time_total}" \
      --header "Content-Type: application/json" \
      --header "X-Session-ID: ${SESSION_ID}" \
      ${SUBSCRIPTION_KEY_HEADER:+--header "${SUBSCRIPTION_KEY_HEADER}"} \
      --data "{\"message\": \"${message}\", \"session_id\": \"${SESSION_ID}\"}" \
      "${BASE_URL}" 2>/dev/null || true
  )

  # Last line is the write-out: "<http_code> <time_total>"
  local write_out_line
  write_out_line="$(echo "${raw_response}" | tail -n1)"
  http_code="$(echo "${write_out_line}" | awk '{print $1}')"
  time_total="$(echo "${write_out_line}" | awk '{print $2}')"

  # Convert time to milliseconds for readability
  local time_ms
  time_ms="$(echo "${time_total}" | awk '{printf "%.0f", $1 * 1000}')"

  # Extract Retry-After from headers if present
  if grep -qi "retry-after" "${header_file}" 2>/dev/null; then
    retry_after="$(grep -i "retry-after" "${header_file}" | awk '{print $2}' | tr -d '\r')"
  fi

  rm -f "${header_file}"

  # Output line
  echo "${http_code} ${time_ms} ${retry_after}"
}

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}=================================================${RESET}"
echo -e "${BOLD}  CUSTOMER_NAME Bill Explainer - Demo 4 Script      ${RESET}"
echo -e "${BOLD}  Observability + Rate Limit Trigger            ${RESET}"
echo -e "${BOLD}=================================================${RESET}"
echo ""
echo -e "  Target:     ${CYAN}${BASE_URL}${RESET}"
echo -e "  Session ID: ${CYAN}${SESSION_ID}${RESET}"
if [[ "${DRY_RUN}" == "true" ]]; then
  echo -e "  Mode:       ${YELLOW}DRY RUN - no real API calls will be made${RESET}"
fi
echo ""

# ---------------------------------------------------------------------------
# Phase 1: Warm-up - 3 concurrent requests to generate Live Metrics traffic
# ---------------------------------------------------------------------------
if [[ "${SKIP_WARMUP}" == "false" ]]; then
  echo -e "${BOLD}--- PHASE 1: Warm-up (3 concurrent requests) ---${RESET}"
  echo "    Switch to Application Insights Live Metrics now."
  echo "    You should see the request rate and dependency spikes in ~10 seconds."
  echo ""

  WARMUP_MESSAGES=(
    "Cosa sono gli oneri di sistema sulla mia bolletta?"
    "Come si calcola la quota potenza?"
    "Cosa significa il codice POD?"
  )

  # Fire concurrently using background jobs
  WARMUP_PIDS=()
  WARMUP_TMPFILES=()

  for i in 0 1 2; do
    tmpfile="$(mktemp)"
    WARMUP_TMPFILES+=("${tmpfile}")
    (
      result="$(fire_request "${WARMUP_MESSAGES[$i]}" "warmup-$((i+1))")"
      echo "${result}" > "${tmpfile}"
    ) &
    WARMUP_PIDS+=($!)
  done

  # Wait for all three
  for pid in "${WARMUP_PIDS[@]}"; do
    wait "${pid}" || true
  done

  echo "  Results:"
  for i in 0 1 2; do
    tmpfile="${WARMUP_TMPFILES[$i]}"
    if [[ -f "${tmpfile}" ]]; then
      result="$(cat "${tmpfile}")"
      http_code="$(echo "${result}" | awk '{print $1}')"
      time_ms="$(echo "${result}" | awk '{print $2}')"
      rm -f "${tmpfile}"
      if [[ "${http_code}" == "200" ]]; then
        echo -e "  [warmup-$((i+1))] ${GREEN}HTTP ${http_code}${RESET}  time=${time_ms}ms"
      else
        echo -e "  [warmup-$((i+1))] ${YELLOW}HTTP ${http_code}${RESET}  time=${time_ms}ms"
      fi
    fi
  done

  echo ""
  echo "  Warm-up complete. Live Metrics should now show activity."
  echo "  Waiting 3 seconds before rate-limit phase..."
  if [[ "${DRY_RUN}" == "false" ]]; then
    sleep 3
  fi
  echo ""
fi

# ---------------------------------------------------------------------------
# Phase 2: Rate limit trigger - 12 sequential rapid requests
# ---------------------------------------------------------------------------
echo -e "${BOLD}--- PHASE 2: Rate Limit Trigger (12 sequential requests) ---${RESET}"
echo "    APIM policy: 10 requests per minute per IP."
echo "    Firing rapid sequential requests until a 429 is received."
echo ""

RATE_LIMIT_MESSAGE="Puoi spiegare come funziona la tariffa bioraria?"

SUCCESS_COUNT=0
FIRST_429_AT=0
RETRY_AFTER_VALUE=""

for i in $(seq 1 12); do
  result="$(fire_request "${RATE_LIMIT_MESSAGE}" "req-${i}")"
  http_code="$(echo "${result}" | awk '{print $1}')"
  time_ms="$(echo "${result}" | awk '{print $2}')"
  retry_after="$(echo "${result}" | awk '{print $3}')"

  if [[ "${http_code}" == "200" ]]; then
    echo -e "  [${i}] ${GREEN}HTTP ${http_code}${RESET}  time=${time_ms}ms"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
  elif [[ "${http_code}" == "429" ]]; then
    if [[ -n "${retry_after}" ]]; then
      echo -e "  [${i}] ${RED}HTTP ${http_code}${RESET}  time=${time_ms}ms  ${BOLD}Retry-After: ${retry_after}s${RESET}"
    else
      echo -e "  [${i}] ${RED}HTTP ${http_code}${RESET}  time=${time_ms}ms"
    fi
    FIRST_429_AT="${i}"
    RETRY_AFTER_VALUE="${retry_after}"
    echo ""
    echo -e "${BOLD}${RED}--- RATE LIMIT TRIGGERED at request ${i} ---${RESET}"
    break
  else
    echo -e "  [${i}] ${YELLOW}HTTP ${http_code}${RESET}  time=${time_ms}ms"
  fi

  # Small pause to allow curl connection teardown; keeps output readable
  sleep 0.1
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}=================================================${RESET}"
echo -e "${BOLD}  Summary                                        ${RESET}"
echo -e "${BOLD}=================================================${RESET}"
echo ""
echo -e "  Successful requests (HTTP 200): ${GREEN}${SUCCESS_COUNT}${RESET}"

if [[ "${FIRST_429_AT}" -gt 0 ]]; then
  echo -e "  First 429 at request:           ${RED}${FIRST_429_AT}${RESET}"
  if [[ -n "${RETRY_AFTER_VALUE}" ]]; then
    echo -e "  Retry-After:                    ${RED}${RETRY_AFTER_VALUE} seconds${RESET}"
  else
    echo -e "  Retry-After:                    ${YELLOW}(header not returned or not captured)${RESET}"
  fi
  echo ""
  echo -e "  APIM blocked the request at the gateway."
  echo -e "  The Container App was never called for request ${FIRST_429_AT}."
  echo -e "  Zero OpenAI tokens were consumed for the blocked request."
else
  echo -e "  No 429 received in 12 requests."
  echo ""
  echo -e "  ${YELLOW}Note: Rate limit may not have triggered.${RESET}"
  echo -e "  Possible reasons:"
  echo -e "    - Warm-up requests counted toward the window; try --skip-warmup"
  echo -e "      then wait 60s and re-run"
  echo -e "    - APIM rate-limit policy may not be attached to this API"
  echo -e "    - Requests are arriving from multiple IPs (e.g. NAT gateway)"
fi

echo ""

# ---------------------------------------------------------------------------
# Cleanup note (commented out - do not auto-clean during demo)
# ---------------------------------------------------------------------------
# To reset the rate limit window, wait 60 seconds (the per-minute window).
# There is no Azure CLI command to flush an APIM rate limit counter manually.
# If you need to demonstrate the 429 again immediately, change the SESSION_ID
# to a new value - but note the IP-based limit will still apply.
#
# To list APIM APIs and policies for verification:
#   RG=$(az group list --query "[?contains(name,'CUSTOMER_NAME-bill')].name" -o tsv | head -1)
#   APIM_NAME=$(az apim list --resource-group "$RG" --query "[0].name" -o tsv)
#   az apim api list --resource-group "$RG" --service-name "$APIM_NAME" -o table
