#!/usr/bin/env bash
# =============================================================================
# billing-stub-setup.sh
# Purpose  : Create and manage a minimal billing API stub server on the jump box.
#            This is a DEMO-ONLY tool. It serves canned JSON responses to let
#            the CUSTOMER_NAME Bill Explainer demo run end-to-end without a live
#            billing backend.
#
# NEVER use this in production. It accepts all requests without authentication
# and returns static fixture data.
#
# Usage:
#   bash billing-stub-setup.sh start   - Write stub_server.py and start it
#   bash billing-stub-setup.sh stop    - Terminate the process on port 8080
#   bash billing-stub-setup.sh status  - Check if stub is responding
#   bash billing-stub-setup.sh test    - Fetch the demo bill and pretty-print it
#
# Requirements: Python 3.11+ available as python3 (pre-installed on jump box)
# =============================================================================

set -euo pipefail

STUB_DIR="${HOME}/billing-stub"
STUB_PY="${STUB_DIR}/stub_server.py"
STUB_LOG="${STUB_DIR}/stub.log"
PORT=8080

write_stub_server() {
  mkdir -p "${STUB_DIR}"

  cat > "${STUB_PY}" << 'PYTHON'
"""
billing-stub stub_server.py
Demo-only billing API stub. No auth. Static fixture data. Not for production.
"""
import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

DEMO_BILL = {
    "bill_ref": "IT001-2024-DEMO",
    "customer_name": "Mario Rossi",
    "customer_address": "Via Roma 42, 20121 Milano MI",
    "billing_period_start": "2024-01-01",
    "billing_period_end": "2024-01-31",
    "total_amount": 187.43,
    "currency": "EUR",
    "consumption_kwh": 420,
    "previous_month_kwh": 280,
    "tariff_code": "D2",
    "tariff_name": "Tariffa Domestica Standard",
    "payment_status": "unpaid",
    "due_date": "2024-02-20",
    "line_items": [
        {"description": "Quota Energia F1 (ore di punta)",    "amount": 62.16, "unit": "EUR", "quantity": 168.0},
        {"description": "Quota Energia F2 (ore intermedie)",  "amount": 28.56, "unit": "EUR", "quantity": 105.0},
        {"description": "Quota Energia F3 (ore fuori punta)", "amount": 19.74, "unit": "EUR", "quantity": 147.0},
        {"description": "Quota Potenza",                      "amount": 18.20, "unit": "EUR", "quantity": None},
        {"description": "Oneri di Sistema (ARERA)",           "amount": 22.15, "unit": "EUR", "quantity": None},
        {"description": "Accise",                             "amount":  6.13, "unit": "EUR", "quantity": None},
        {"description": "IVA 22%",                            "amount": 30.49, "unit": "EUR", "quantity": None}
    ]
}

FAKE_TOKEN = {
    "access_token": "demo-stub-token-not-real",
    "expires_in": 3600,
    "token_type": "Bearer"
}


def log(method, path, status):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {method} {path} -> {status}", flush=True)


class BillingStubHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"status": "ok"})
            log("GET", self.path, 200)
        elif self.path == "/api/v1/bills/IT001-2024-DEMO":
            self.send_json(200, DEMO_BILL)
            log("GET", self.path, 200)
        elif self.path.startswith("/api/v1/bills/"):
            self.send_json(404, {"error": "bill not found"})
            log("GET", self.path, 404)
        else:
            self.send_json(404, {"error": "not found"})
            log("GET", self.path, 404)

    def do_POST(self):
        if self.path == "/oauth2/v2.0/token":
            self.send_json(200, FAKE_TOKEN)
            log("POST", self.path, 200)
        else:
            self.send_json(404, {"error": "not found"})
            log("POST", self.path, 404)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = HTTPServer(("0.0.0.0", port), BillingStubHandler)
    print(f"Billing stub listening on port {port} (demo-only, not for production)", flush=True)
    server.serve_forever()
PYTHON
}

case "${1:-}" in

  start)
    write_stub_server
    echo "Starting billing stub on port ${PORT}..."
    nohup python3 "${STUB_PY}" > "${STUB_LOG}" 2>&1 &
    echo "PID: $!"
    sleep 2
    if curl --silent --fail "http://localhost:${PORT}/health" > /dev/null; then
      echo "Billing stub is running on port ${PORT}"
    else
      echo "ERROR: stub did not respond on port ${PORT}. Check ${STUB_LOG} for details."
      exit 1
    fi
    ;;

  stop)
    echo "Stopping billing stub on port ${PORT}..."
    # Windows alternative (PowerShell without lsof):
    #   netstat -ano | findstr :${PORT}   then   taskkill /PID <pid> /F
    PIDS=$(lsof -ti:"${PORT}" 2>/dev/null || true)
    if [ -z "${PIDS}" ]; then
      echo "No process found on port ${PORT}."
    else
      echo "${PIDS}" | xargs -r kill -9
      echo "Stopped PID(s): ${PIDS}"
    fi
    ;;

  status)
    echo "Checking billing stub health..."
    curl --silent "http://localhost:${PORT}/health" || echo "No response from port ${PORT}"
    echo
    ;;

  test)
    echo "Fetching demo bill IT001-2024-DEMO..."
    curl --silent "http://localhost:${PORT}/api/v1/bills/IT001-2024-DEMO" | python3 -m json.tool
    ;;

  *)
    echo "Usage: bash billing-stub-setup.sh {start|stop|status|test}"
    echo ""
    echo "  start   Write stub_server.py (if needed) and start it in the background"
    echo "  stop    Terminate the process on port ${PORT}"
    echo "  status  Ping /health and print the response"
    echo "  test    Fetch the IT001-2024-DEMO bill JSON and pretty-print it"
    echo ""
    echo "Log file: ${STUB_LOG}"
    ;;

esac
