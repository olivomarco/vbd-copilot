#!/usr/bin/env bash
# =============================================================================
# demo-2-bill-lookup.sh
#
# Purpose  : Drive the CUSTOMER_NAME Bill Explainer chat API for Demo 2.
#            Sends a personalised bill lookup request with bill_ref
#            IT001-2024-DEMO, streams the SSE response token-by-token,
#            then sends a follow-up question about the consumption spike.
#            Optionally submits thumbs-up feedback and runs the circuit
#            breaker test.
#
# Where to run : Presenter's laptop (macOS or Linux with curl and jq).
#                Requires outbound HTTPS to Azure Front Door.
#                Does NOT require jump box access.
#
# Prerequisites:
#   - curl >= 7.68 (supports --no-buffer with SSE)
#   - jq >= 1.6
#   - FRONT_DOOR_HOSTNAME env var set (no https://, no trailing slash)
#     Example: export FRONT_DOOR_HOSTNAME="CUSTOMER_NAME-bill-dev-ENDPOINT.z01.azurefd.net"
#   - SESSION_ID env var (optional) - pass the session_id from Demo 1 to
#     continue that conversation. Omit to start a new session.
#
# Flags:
#   --submit-feedback      Submit a thumbs-up rating for the last response.
#   --test-circuit-breaker Hit the billing API with an invalid bill ref 6
#                          times to trip the circuit breaker in billing_api.py
#                          (_CB_FAILURE_THRESHOLD = 5). Requires the billing
#                          API stub on the jump box to be STOPPED first.
#                          WARNING: each of the first 5 requests waits up to
#                          10.5 seconds (5s timeout + 0.5s retry backoff + 5s).
#                          Total time for this section: ~60-75 seconds.
#
# Usage:
#   bash demo-2-bill-lookup.sh
#   bash demo-2-bill-lookup.sh --submit-feedback
#   bash demo-2-bill-lookup.sh --test-circuit-breaker
#
# =============================================================================

set -euo pipefail

# =============================================================================
# Parse flags
# =============================================================================

SUBMIT_FEEDBACK=false
TEST_CIRCUIT_BREAKER=false

for arg in "$@"; do
  case "$arg" in
    --submit-feedback)
      SUBMIT_FEEDBACK=true
      ;;
    --test-circuit-breaker)
      TEST_CIRCUIT_BREAKER=true
      ;;
    *)
      echo "Unknown flag: $arg" >&2
      echo "Usage: $0 [--submit-feedback] [--test-circuit-breaker]" >&2
      exit 1
      ;;
  esac
done

# =============================================================================
# Validate required environment variables
# =============================================================================

if [[ -z "${FRONT_DOOR_HOSTNAME:-}" ]]; then
  echo ""
  echo "ERROR: FRONT_DOOR_HOSTNAME is not set."
  echo ""
  echo "  export FRONT_DOOR_HOSTNAME=\"CUSTOMER_NAME-bill-dev-ENDPOINT.z01.azurefd.net\""
  echo ""
  echo "Discover the hostname with:"
  echo "  az afd endpoint list \\"
  echo "    --profile-name \$(az afd profile list --query '[0].name' -o tsv) \\"
  echo "    --resource-group \$(az group list --query '[0].name' -o tsv) \\"
  echo "    --query '[0].hostName' -o tsv"
  echo ""
  exit 1
fi

BASE_URL="https://${FRONT_DOOR_HOSTNAME}"
CHAT_ENDPOINT="${BASE_URL}/api/v1/chat"
FEEDBACK_ENDPOINT="${BASE_URL}/api/v1/chat/feedback"

# Session ID from Demo 1 (optional - blank starts a new session)
SESSION_ID="${SESSION_ID:-}"

# Bill reference used throughout this demo
BILL_REF="IT001-2024-DEMO"

# =============================================================================
# Helper: stream an SSE response and extract session_id + message_id
# =============================================================================
# Reads SSE data lines from stdin (piped from curl).
# Prints each token to stdout without a newline.
# After the final event (done=true), sets SESSION_ID and LAST_MESSAGE_ID globals.
#
# Output variables (set after function returns via temp file):
#   SESSION_ID      - updated session UUID from final SSE event
#   LAST_MESSAGE_ID - message UUID from final SSE event

_SSE_TMPFILE=$(mktemp)

stream_sse() {
  local label="$1"

  echo ""
  echo "----------------------------------------------------------------------"
  echo "  $label"
  echo "----------------------------------------------------------------------"
  echo ""

  # Reset output capture file
  > "$_SSE_TMPFILE"

  while IFS= read -r line; do
    # SSE lines start with "data: "
    if [[ "$line" == data:* ]]; then
      local payload="${line#data: }"

      # Skip SSE keep-alive or empty data lines
      if [[ -z "$payload" ]]; then
        continue
      fi

      local token done_flag sid mid
      token=$(echo "$payload" | jq -r '.token // empty' 2>/dev/null || true)
      done_flag=$(echo "$payload" | jq -r '.done // "false"' 2>/dev/null || true)
      sid=$(echo "$payload" | jq -r '.session_id // empty' 2>/dev/null || true)
      mid=$(echo "$payload" | jq -r '.message_id // empty' 2>/dev/null || true)

      # Print token to stdout (no newline - builds up the response inline)
      if [[ -n "$token" ]]; then
        printf '%s' "$token"
      fi

      # On the final event, capture session and message IDs
      if [[ "$done_flag" == "true" ]]; then
        printf '\n'
        echo ""

        if [[ -n "$sid" ]]; then
          echo "$sid" > "$_SSE_TMPFILE"
          echo "$mid" >> "$_SSE_TMPFILE"
        fi
        break
      fi
    fi
  done

  # Read captured IDs back
  if [[ -s "$_SSE_TMPFILE" ]]; then
    SESSION_ID=$(sed -n '1p' "$_SSE_TMPFILE")
    LAST_MESSAGE_ID=$(sed -n '2p' "$_SSE_TMPFILE")
  fi
}

# =============================================================================
# Helper: build the JSON request body for a chat message
# =============================================================================

build_chat_body() {
  local message="$1"
  local bill_ref="${2:-}"
  local session_id="${3:-}"

  local body
  body=$(jq -n \
    --arg msg "$message" \
    --arg br "$bill_ref" \
    --arg sid "$session_id" \
    '{
      message: $msg,
      bill_ref: (if $br != "" then $br else null end),
      session_id: (if $sid != "" then $sid else null end)
    }')

  echo "$body"
}

# =============================================================================
# Helper: post a chat request and stream the SSE response
# =============================================================================

chat_request() {
  local label="$1"
  local message="$2"
  local bill_ref="${3:-}"
  local session_id="${4:-}"

  local body
  body=$(build_chat_body "$message" "$bill_ref" "$session_id")

  curl \
    --silent \
    --no-buffer \
    --request POST \
    --url "$CHAT_ENDPOINT" \
    --header "Content-Type: application/json" \
    --header "Accept: text/event-stream" \
    --data "$body" | stream_sse "$label"
}

# =============================================================================
# Helper: check curl and jq are available
# =============================================================================

check_dependencies() {
  local missing=false

  if ! command -v curl &>/dev/null; then
    echo "ERROR: curl is not installed or not in PATH." >&2
    missing=true
  fi

  if ! command -v jq &>/dev/null; then
    echo "ERROR: jq is not installed or not in PATH." >&2
    echo "  Install with: brew install jq  (macOS) or apt-get install jq (Linux)" >&2
    missing=true
  fi

  if [[ "$missing" == "true" ]]; then
    exit 1
  fi
}

# =============================================================================
# Main demo sequence
# =============================================================================

check_dependencies

echo ""
echo "======================================================================"
echo "  Demo 2 - Live Chat: Personalised Bill Lookup"
echo "  CUSTOMER_NAME Intelligent Bill Explainer"
echo "======================================================================"
echo ""
echo "  Front Door endpoint : $BASE_URL"
echo "  Bill reference      : $BILL_REF"
if [[ -n "$SESSION_ID" ]]; then
  echo "  Continuing session  : $SESSION_ID"
else
  echo "  Session             : new (will be created by first request)"
fi
echo ""

# =============================================================================
# STEP 1 - Initial bill lookup
# =============================================================================

echo "STEP 1 OF 3 - Sending bill lookup request"
echo ""
echo "  Request body:"
build_chat_body \
  "Ho la mia bolletta di gennaio, il numero e IT001-2024-DEMO" \
  "$BILL_REF" \
  "$SESSION_ID" | jq .
echo ""
echo "  Streaming response (token by token)..."

LAST_MESSAGE_ID=""

chat_request \
  "STEP 1 - AI response: bill line item breakdown" \
  "Ho la mia bolletta di gennaio, il numero e IT001-2024-DEMO" \
  "$BILL_REF" \
  "$SESSION_ID"

echo ""
echo "  Session ID  : ${SESSION_ID:-<not returned - check response above>}"
echo "  Message ID  : ${LAST_MESSAGE_ID:-<not returned>}"
echo ""

# =============================================================================
# STEP 2 - Follow-up question: consumption spike
# =============================================================================

echo "STEP 2 OF 3 - Follow-up question: consumption spike"
echo ""
echo "  This request uses the same session to test conversation continuity."
echo "  Expect GPT-4o to reference 420 kWh vs 280 kWh from the bill data."
echo ""

STEP1_MESSAGE_ID="$LAST_MESSAGE_ID"

chat_request \
  "STEP 2 - AI response: why is consumption higher?" \
  "Perche' la bolletta di gennaio e' cosi' alta rispetto al mese scorso?" \
  "$BILL_REF" \
  "$SESSION_ID"

echo ""
echo "  Session ID  : ${SESSION_ID:-<not returned>}"
echo "  Message ID  : ${LAST_MESSAGE_ID:-<not returned>}"
echo ""

FOLLOWUP_MESSAGE_ID="$LAST_MESSAGE_ID"

# =============================================================================
# STEP 3 - Submit feedback (optional, controlled by --submit-feedback flag)
# =============================================================================

if [[ "$SUBMIT_FEEDBACK" == "true" ]]; then
  echo "STEP 3 OF 3 - Submitting thumbs-up feedback for last response"
  echo ""

  if [[ -z "$SESSION_ID" || -z "$FOLLOWUP_MESSAGE_ID" ]]; then
    echo "  WARNING: Cannot submit feedback - session_id or message_id is missing."
    echo "  Skipping feedback step."
  else
    FEEDBACK_BODY=$(jq -n \
      --arg sid "$SESSION_ID" \
      --arg mid "$FOLLOWUP_MESSAGE_ID" \
      '{
        session_id: $sid,
        message_id: $mid,
        rating: "up",
        comment: "Demo 2 - response spiegazione bolletta molto chiara"
      }')

    echo "  Request body:"
    echo "$FEEDBACK_BODY" | jq .
    echo ""

    FEEDBACK_RESPONSE=$(curl \
      --silent \
      --request POST \
      --url "$FEEDBACK_ENDPOINT" \
      --header "Content-Type: application/json" \
      --data "$FEEDBACK_BODY")

    echo "  API response:"
    echo "$FEEDBACK_RESPONSE" | jq .
    echo ""
    echo "  Feedback record written to Cosmos DB 'feedback' container."
    echo "  Verify in Data Explorer: billexplainer -> feedback -> Items"
    echo ""
  fi
else
  echo "STEP 3 - Feedback skipped (run with --submit-feedback to include)"
  echo ""
fi

# =============================================================================
# Circuit breaker test (optional, controlled by --test-circuit-breaker flag)
# =============================================================================

if [[ "$TEST_CIRCUIT_BREAKER" == "true" ]]; then
  echo "======================================================================"
  echo "  CIRCUIT BREAKER TEST"
  echo "  Source: src/app/services/billing_api.py"
  echo "  _CB_FAILURE_THRESHOLD = 5"
  echo "  _CB_RECOVERY_TIMEOUT  = 30 seconds"
  echo "  _REQUEST_TIMEOUT      = 5.0 seconds per attempt"
  echo "  _MAX_RETRIES          = 1 (so 2 attempts per request = up to 10.5s each)"
  echo "======================================================================"
  echo ""
  echo "  IMPORTANT: Before running this test, stop the billing API stub"
  echo "  on the jump box so the billing API calls time out."
  echo ""
  echo "  To stop the stub from the jump box terminal:"
  echo "    pgrep -f stub_server   # find the PID"
  echo "    kill <PID>             # stop it"
  echo ""
  echo "  This test sends 6 requests with an invalid bill ref that passes"
  echo "  format validation (alphanumeric, 8-20 chars) but the billing API"
  echo "  will not respond (stub stopped). After 5 failures the circuit opens."
  echo "  Request 6 gets an instant circuit-open error - no timeout wait."
  echo ""
  echo "  WARNING: Requests 1-5 will each take up to 10.5 seconds."
  echo "  Total test duration: approximately 60-75 seconds."
  echo ""
  read -rp "  Billing stub stopped on jump box? Press Enter to continue, Ctrl-C to cancel... "
  echo ""

  # Use a valid-format ref that will fail when the stub is down
  CB_TEST_BILL_REF="CBTEST-2024-X1"

  # We need a fresh session for the circuit breaker test so we do not
  # corrupt the demo session used in Steps 1 and 2.
  CB_SESSION_ID=""

  for i in 1 2 3 4 5 6; do
    echo "----------------------------------------------------------------------"
    echo "  Circuit breaker request $i of 6"
    if [[ $i -le 5 ]]; then
      echo "  Expected: billing API timeout -> BillingAPIError -> failure counter +1"
    else
      echo "  Expected: instant circuit-open error (no timeout wait)"
    fi
    echo "----------------------------------------------------------------------"

    CB_BODY=$(jq -n \
      --arg msg "Mostrami la bolletta di test $i" \
      --arg br "$CB_TEST_BILL_REF" \
      --arg sid "$CB_SESSION_ID" \
      '{
        message: $msg,
        bill_ref: $br,
        session_id: (if $sid != "" then $sid else null end)
      }')

    START_TIME=$(date +%s)

    CB_RAW=$(curl \
      --silent \
      --no-buffer \
      --request POST \
      --url "$CHAT_ENDPOINT" \
      --header "Content-Type: application/json" \
      --header "Accept: text/event-stream" \
      --data "$CB_BODY" || true)

    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))

    echo ""
    echo "  Raw SSE output (first 300 chars):"
    echo "$CB_RAW" | head -c 300
    echo ""
    echo "  Request completed in ${ELAPSED}s"

    # Extract session_id for subsequent requests in this test
    if [[ -z "$CB_SESSION_ID" ]]; then
      CB_SID=$(echo "$CB_RAW" | grep '^data:' | tail -1 | sed 's/^data: //' \
        | jq -r '.session_id // empty' 2>/dev/null || true)
      if [[ -n "$CB_SID" ]]; then
        CB_SESSION_ID="$CB_SID"
      fi
    fi

    echo ""

    # After request 4, add a small pause to let the Container App log the failures
    if [[ $i -eq 4 ]]; then
      echo "  Pausing 1 second before request 5..."
      sleep 1
    fi
  done

  echo "======================================================================"
  echo "  Circuit breaker test complete."
  echo ""
  echo "  What to look for:"
  echo "  - Requests 1-5: each took 10-11 seconds (two 5s timeouts per request)"
  echo "  - Request 6: returned in under 1 second with circuit-open message"
  echo "  - The app gracefully continued - it did not crash"
  echo ""
  echo "  To reset the circuit, restart the Container App or wait 30 seconds"
  echo "  (the _CB_RECOVERY_TIMEOUT in billing_api.py)."
  echo ""
  echo "  To restart the billing stub on the jump box:"
  echo "    nohup python3 ~/billing-stub/stub_server.py > ~/billing-stub/stub.log 2>&1 &"
  echo "======================================================================"
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "======================================================================"
echo "  Demo 2 complete"
echo "======================================================================"
echo ""
echo "  Session used       : ${SESSION_ID:-<check output above>}"
echo "  Bill reference     : $BILL_REF"
echo "  Feedback submitted : $SUBMIT_FEEDBACK"
echo "  Circuit breaker    : $TEST_CIRCUIT_BREAKER"
echo ""
echo "  Next step: open Cosmos DB Data Explorer on the jump box."
echo "    Database    : billexplainer"
echo "    Containers  : sessions, messages, feedback"
echo "    Partition   : sessionId = ${SESSION_ID:-<session from above>}"
echo ""
echo "  Discover Cosmos DB account name:"
echo "    az cosmosdb list \\"
echo "      --resource-group \$(az group list --query '[0].name' -o tsv) \\"
echo "      --query '[0].name' -o tsv"
echo ""

# =============================================================================
# Cleanup note (commented out - do NOT run during demo)
# =============================================================================
# To delete the demo session and all associated messages and feedback
# from Cosmos DB after the demo (GDPR erasure test), call the sessions
# DELETE endpoint if implemented, or use the Azure Portal Data Explorer
# to delete the session document - the TTL will handle messages/feedback
# within 24-30 hours automatically.

# Uncomment to delete via Azure CLI (requires Cosmos DB Data Plane SDK):
# az cosmosdb sql container delete --account-name <cosmos-name> \
#   --database-name billexplainer --name sessions \
#   --resource-group <rg> --yes

rm -f "$_SSE_TMPFILE"
