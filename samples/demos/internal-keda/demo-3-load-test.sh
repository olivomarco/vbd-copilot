#!/usr/bin/env bash
# =============================================================================
# demo-3-load-test.sh
# KEDA HTTP Add-on Demo - Parameterized HTTP Load Generator
# =============================================================================
#
# USAGE:
#   ./demo-3-load-test.sh [requests] [concurrency] [host] [interceptor_url]
#
#   Argument 1 - REQUESTS       : total requests to send       (default: 2000)
#   Argument 2 - CONCURRENCY    : parallel workers             (default: 50)
#   Argument 3 - HOST           : Host header value            (default: myapp.demo.com)
#   Argument 4 - INTERCEPTOR_URL: interceptor proxy base URL   (default: http://localhost:8080)
#
# EXAMPLES:
#   # Minimal - use all defaults
#   ./demo-3-load-test.sh
#
#   # 5000 requests at concurrency 100 against default host
#   ./demo-3-load-test.sh 5000 100
#
#   # Custom host
#   ./demo-3-load-test.sh 2000 50 myapp.demo.com
#
#   # Full override including interceptor URL
#   ./demo-3-load-test.sh 2000 50 myapp.demo.com http://localhost:8080
#
# PREREQUISITES:
#   - kubectl port-forward active:
#       kubectl port-forward svc/keda-add-ons-http-interceptor-proxy \
#         -n keda-http-demo 8080:8080 &
#   - HTTPScaledObject applied: kubectl apply -f demo-3-httpscaledobject.yaml
#   - hey installed (recommended): https://github.com/rakyll/hey
#       go install github.com/rakyll/hey@latest
#     OR via Homebrew: brew install hey
#     OR use the curl fallback (built in, no extra install needed)
#
# WHAT TO WATCH IN A SEPARATE TERMINAL:
#   watch -n 1 kubectl get pods -n keda-http-demo
#   watch -n 2 kubectl get hpa  -n keda-http-demo
#
# ENV VAR OVERRIDES (alternative to positional arguments):
#   export KEDA_REQUESTS=5000
#   export KEDA_CONCURRENCY=100
#   export KEDA_HOST=myapp.demo.com
#   export KEDA_INTERCEPTOR_URL=http://localhost:8080
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration - positional args take precedence over env vars, then defaults
# ---------------------------------------------------------------------------
REQUESTS="${1:-${KEDA_REQUESTS:-2000}}"
CONCURRENCY="${2:-${KEDA_CONCURRENCY:-50}}"
HOST="${3:-${KEDA_HOST:-myapp.demo.com}}"
INTERCEPTOR_URL="${4:-${KEDA_INTERCEPTOR_URL:-http://localhost:8080}}"
TARGET_URL="${INTERCEPTOR_URL}/"

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  KEDA HTTP Add-on - Load Generator"
echo "============================================================"
echo "  Requests      : ${REQUESTS}"
echo "  Concurrency   : ${CONCURRENCY}"
echo "  Host header   : ${HOST}"
echo "  Target URL    : ${TARGET_URL}"
echo "============================================================"
echo ""

# ---------------------------------------------------------------------------
# Verify port-forward is reachable before sending load
# ---------------------------------------------------------------------------
echo "[INFO] Checking interceptor reachability at ${INTERCEPTOR_URL} ..."
if ! curl -sf --max-time 5 -H "Host: ${HOST}" "${TARGET_URL}" -o /dev/null; then
  echo ""
  echo "[WARN] Interceptor did not return HTTP 200 on the pre-flight check."
  echo "       This is EXPECTED when replicas=0 - the first request will be"
  echo "       queued by the interceptor while KEDA scales up from zero."
  echo "       Proceeding with load test anyway."
  echo ""
fi

# ---------------------------------------------------------------------------
# Scaling math reminder (visible at font size 18+)
# ---------------------------------------------------------------------------
echo "[INFO] Scaling math (requestRate variant):"
echo "       targetValue = 10 req/s per pod"
echo "       Expected pods = ceil(actual_rps / 10), capped at max=10"
echo ""

# ---------------------------------------------------------------------------
# Run load test - prefer hey, fall back to curl loop
# ---------------------------------------------------------------------------
if command -v hey &>/dev/null; then
  echo "[INFO] Using 'hey' for load generation ..."
  echo ""
  hey -n "${REQUESTS}" \
      -c "${CONCURRENCY}" \
      -H "Host: ${HOST}" \
      "${TARGET_URL}"

else
  echo "[WARN] 'hey' not found. Falling back to parallel curl loop."
  echo "       Install hey for accurate throughput stats:"
  echo "       go install github.com/rakyll/hey@latest"
  echo ""
  echo "[INFO] Sending ${CONCURRENCY} parallel curl requests (${REQUESTS} total) ..."

  SENT=0
  BATCH=${CONCURRENCY}

  while [ "${SENT}" -lt "${REQUESTS}" ]; do
    # Calculate how many to fire in this batch (do not overshoot REQUESTS)
    REMAINING=$(( REQUESTS - SENT ))
    if [ "${REMAINING}" -lt "${BATCH}" ]; then
      BATCH="${REMAINING}"
    fi

    for i in $(seq 1 "${BATCH}"); do
      curl -sf \
           --max-time 30 \
           -H "Host: ${HOST}" \
           "${TARGET_URL}" \
           -o /dev/null \
           -w "HTTP %{http_code}\n" &
    done
    wait

    SENT=$(( SENT + BATCH ))
    echo "[INFO] Sent ${SENT} / ${REQUESTS} requests ..."
  done

  echo ""
  echo "[INFO] curl loop complete. ${REQUESTS} requests fired at concurrency ${CONCURRENCY}."
fi

# ---------------------------------------------------------------------------
# Post-test: show current pod count
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  Current pod state (post-load):"
echo "============================================================"
kubectl get pods -n keda-http-demo --no-headers 2>/dev/null || \
  echo "[WARN] kubectl not found or namespace unreachable."

echo ""
echo "[INFO] Watch scale-down (pods -> 0 after scaledownPeriod=60s):"
echo "       watch -n 1 kubectl get pods -n keda-http-demo"
echo ""

# ---------------------------------------------------------------------------
# CLEANUP (commented out - run manually when finished)
# ---------------------------------------------------------------------------
# kubectl delete -f demo-3-httpscaledobject.yaml
# kubectl delete -f demo-3-demo-app.yaml
# helm uninstall http-add-on -n keda-http-demo
# kubectl delete namespace keda-http-demo
