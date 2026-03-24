#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# CUSTOMER_NAME Intelligent Bill Explainer - Validation Harness
# ---------------------------------------------------------------------------
# Runs infrastructure validation, unit tests, and optionally smoke tests
# against a live deployment.
#
# Usage:
#   ./validate.sh              # Run infra validation + unit tests
#   ./validate.sh --live       # Also run smoke tests against deployed env
#   ./validate.sh --help       # Show help
# ---------------------------------------------------------------------------
set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
readonly INFRA_DIR="${PROJECT_DIR}/infra"
readonly SRC_DIR="${PROJECT_DIR}/src"
readonly TESTS_DIR="${PROJECT_DIR}/tests"

# ---------------------------------------------------------------------------
# Color codes
# ---------------------------------------------------------------------------
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

# ---------------------------------------------------------------------------
# State tracking
# ---------------------------------------------------------------------------
LIVE_MODE=false
TOTAL_PASS=0
TOTAL_FAIL=0
TOTAL_SKIP=0
declare -a RESULTS=()

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
log_info() {
    echo -e "${GREEN}[INFO]${NC}  $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC}  $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

log_step() {
    echo ""
    echo -e "${BLUE}--- $* ---${NC}"
    echo ""
}

# ---------------------------------------------------------------------------
# record_result - Track section pass/fail/skip
# ---------------------------------------------------------------------------
record_result() {
    local section="$1"
    local status="$2"  # PASS, FAIL, SKIP

    case "$status" in
        PASS)
            TOTAL_PASS=$((TOTAL_PASS + 1))
            RESULTS+=("${GREEN}PASS${NC}  ${section}")
            ;;
        FAIL)
            TOTAL_FAIL=$((TOTAL_FAIL + 1))
            RESULTS+=("${RED}FAIL${NC}  ${section}")
            ;;
        SKIP)
            TOTAL_SKIP=$((TOTAL_SKIP + 1))
            RESULTS+=("${YELLOW}SKIP${NC}  ${section}")
            ;;
    esac
}

# ---------------------------------------------------------------------------
# show_help
# ---------------------------------------------------------------------------
show_help() {
    cat <<EOF
CUSTOMER_NAME Intelligent Bill Explainer - Validation Harness

USAGE:
    $(basename "$0") [OPTIONS]

OPTIONS:
    --live      Run smoke tests against a live deployed environment.
                Requires API_BASE_URL or CONTAINER_APP_FQDN to be set.
    --help, -h  Show this help message.

SECTIONS:
    1. Prerequisites check  - Verify required tools are available
    2. Infrastructure        - Validate all Bicep files compile
    3. Unit tests            - Run pytest with coverage threshold
    4. Smoke tests (--live)  - Hit deployed endpoints for health checks

ENVIRONMENT VARIABLES (for --live mode):
    API_BASE_URL          Full base URL of the deployed API (e.g. https://myapp.azurecontainerapps.io)
    CONTAINER_APP_FQDN    FQDN of the Container App (alternative to API_BASE_URL)

EOF
    exit 0
}

# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --live)
                LIVE_MODE=true
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
}

# ---------------------------------------------------------------------------
# check_prerequisites - Verify required tools
# ---------------------------------------------------------------------------
check_prerequisites() {
    log_step "Checking prerequisites"

    local all_ok=true

    # Python 3
    if command -v python3 &>/dev/null; then
        log_info "python3 found: $(python3 --version 2>&1)"
    else
        log_error "python3 is not installed"
        all_ok=false
    fi

    # pytest
    if python3 -m pytest --version &>/dev/null 2>&1; then
        log_info "pytest found: $(python3 -m pytest --version 2>&1 | head -1)"
    else
        log_warn "pytest not found. Install with: pip install pytest pytest-cov pytest-asyncio"
        all_ok=false
    fi

    # az CLI (optional - needed for infra validation)
    if command -v az &>/dev/null; then
        log_info "Azure CLI found: $(az version --query '"azure-cli"' -o tsv 2>/dev/null || echo 'installed')"
    else
        log_warn "Azure CLI not found. Infrastructure validation will be skipped."
    fi

    if [[ "$all_ok" == true ]]; then
        record_result "Prerequisites" "PASS"
    else
        record_result "Prerequisites" "FAIL"
    fi
}

# ---------------------------------------------------------------------------
# validate_infra - Build all Bicep files
# ---------------------------------------------------------------------------
validate_infra() {
    log_step "Validating infrastructure (Bicep)"

    if ! command -v az &>/dev/null; then
        log_warn "Azure CLI not available. Skipping Bicep validation."
        record_result "Infrastructure (Bicep)" "SKIP"
        return
    fi

    # Ensure bicep is installed
    if ! az bicep version &>/dev/null 2>&1; then
        log_info "Installing Bicep CLI..."
        az bicep install 2>/dev/null || {
            log_warn "Failed to install Bicep. Skipping infra validation."
            record_result "Infrastructure (Bicep)" "SKIP"
            return
        }
    fi

    local failed=0

    # Validate main.bicep
    log_info "Building: main.bicep"
    if az bicep build --file "${INFRA_DIR}/main.bicep" --stdout >/dev/null 2>&1; then
        log_info "  main.bicep - OK"
    else
        log_error "  main.bicep - FAILED"
        failed=1
    fi

    # Validate each module
    for bicep_file in "${INFRA_DIR}"/modules/*.bicep; do
        local filename
        filename="$(basename "$bicep_file")"
        log_info "Building: modules/${filename}"
        if az bicep build --file "$bicep_file" --stdout >/dev/null 2>&1; then
            log_info "  ${filename} - OK"
        else
            log_error "  ${filename} - FAILED"
            failed=1
        fi
    done

    if [[ "$failed" -eq 0 ]]; then
        log_info "All Bicep files validated successfully"
        record_result "Infrastructure (Bicep)" "PASS"
    else
        log_error "One or more Bicep files failed validation"
        record_result "Infrastructure (Bicep)" "FAIL"
    fi
}

# ---------------------------------------------------------------------------
# run_unit_tests - Execute pytest with coverage
# ---------------------------------------------------------------------------
run_unit_tests() {
    log_step "Running unit tests"

    if ! python3 -m pytest --version &>/dev/null 2>&1; then
        log_error "pytest is not installed. Cannot run unit tests."
        record_result "Unit Tests" "FAIL"
        return
    fi

    local unit_dir="${TESTS_DIR}/unit"
    if [[ ! -d "$unit_dir" ]]; then
        log_warn "Unit test directory not found: ${unit_dir}"
        record_result "Unit Tests" "SKIP"
        return
    fi

    # Count test files
    local test_count
    test_count="$(find "$unit_dir" -name 'test_*.py' -o -name '*_test.py' | wc -l)"
    if [[ "$test_count" -eq 0 ]]; then
        log_warn "No test files found in ${unit_dir}"
        record_result "Unit Tests" "SKIP"
        return
    fi

    log_info "Found ${test_count} test file(s) in ${unit_dir}"

    # Run pytest from the project directory so imports resolve correctly
    if (cd "$PROJECT_DIR" && python3 -m pytest \
        "${unit_dir}" \
        --cov="${SRC_DIR}/app" \
        --cov-report=term-missing \
        --cov-fail-under=80 \
        -v \
        2>&1); then
        log_info "Unit tests passed"
        record_result "Unit Tests" "PASS"
    else
        log_error "Unit tests failed or coverage below 80%"
        record_result "Unit Tests" "FAIL"
    fi
}

# ---------------------------------------------------------------------------
# run_smoke_tests - Hit live endpoints (only with --live)
# ---------------------------------------------------------------------------
run_smoke_tests() {
    log_step "Running smoke tests"

    if [[ "$LIVE_MODE" != true ]]; then
        log_info "Smoke tests skipped (pass --live to enable)"
        record_result "Smoke Tests" "SKIP"
        return
    fi

    # Resolve base URL
    local base_url="${API_BASE_URL:-}"
    if [[ -z "$base_url" && -n "${CONTAINER_APP_FQDN:-}" ]]; then
        base_url="https://${CONTAINER_APP_FQDN}"
    fi

    if [[ -z "$base_url" ]]; then
        log_error "No endpoint configured. Set API_BASE_URL or CONTAINER_APP_FQDN."
        record_result "Smoke Tests" "FAIL"
        return
    fi

    log_info "Target endpoint: ${base_url}"

    # Check if smoke test directory has pytest tests
    local smoke_dir="${TESTS_DIR}/smoke"
    if [[ -d "$smoke_dir" ]] && find "$smoke_dir" -name 'test_*.py' | grep -q .; then
        log_info "Running pytest smoke tests..."
        if (cd "$PROJECT_DIR" && API_BASE_URL="$base_url" python3 -m pytest \
            "${smoke_dir}" \
            -v \
            2>&1); then
            log_info "Smoke tests passed"
            record_result "Smoke Tests" "PASS"
        else
            log_error "Smoke tests failed"
            record_result "Smoke Tests" "FAIL"
        fi
    else
        # Fallback: manual curl-based health checks
        log_info "No pytest smoke tests found. Running curl-based health checks..."
        local smoke_ok=true

        # Health endpoint
        log_info "Checking: GET ${base_url}/health"
        local http_code
        http_code="$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 30 "${base_url}/health" 2>/dev/null || echo "000")"
        if [[ "$http_code" == "200" ]]; then
            log_info "  /health -> HTTP ${http_code} - OK"
        else
            log_error "  /health -> HTTP ${http_code} - FAILED"
            smoke_ok=false
        fi

        # Readiness endpoint
        log_info "Checking: GET ${base_url}/health/ready"
        http_code="$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 30 "${base_url}/health/ready" 2>/dev/null || echo "000")"
        if [[ "$http_code" == "200" || "$http_code" == "503" ]]; then
            log_info "  /health/ready -> HTTP ${http_code} - OK (endpoint responsive)"
        else
            log_error "  /health/ready -> HTTP ${http_code} - FAILED"
            smoke_ok=false
        fi

        # OpenAPI docs (verifies FastAPI is serving)
        log_info "Checking: GET ${base_url}/docs"
        http_code="$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 30 "${base_url}/docs" 2>/dev/null || echo "000")"
        if [[ "$http_code" == "200" ]]; then
            log_info "  /docs -> HTTP ${http_code} - OK"
        else
            log_warn "  /docs -> HTTP ${http_code} - Not available (may be disabled in prod)"
        fi

        if [[ "$smoke_ok" == true ]]; then
            log_info "All smoke checks passed"
            record_result "Smoke Tests" "PASS"
        else
            log_error "One or more smoke checks failed"
            record_result "Smoke Tests" "FAIL"
        fi
    fi
}

# ---------------------------------------------------------------------------
# print_summary - Final results table
# ---------------------------------------------------------------------------
print_summary() {
    echo ""
    echo -e "${BLUE}==========================================${NC}"
    echo -e "${BLUE}         VALIDATION SUMMARY               ${NC}"
    echo -e "${BLUE}==========================================${NC}"
    echo ""

    for result in "${RESULTS[@]}"; do
        echo -e "  ${result}"
    done

    echo ""
    echo -e "  -----------------------------------------"
    echo -e "  ${GREEN}Passed: ${TOTAL_PASS}${NC}  ${RED}Failed: ${TOTAL_FAIL}${NC}  ${YELLOW}Skipped: ${TOTAL_SKIP}${NC}"
    echo ""

    if [[ "$TOTAL_FAIL" -gt 0 ]]; then
        echo -e "  ${RED}RESULT: FAIL${NC}"
        echo ""
        return 1
    else
        echo -e "  ${GREEN}RESULT: PASS${NC}"
        echo ""
        return 0
    fi
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
main() {
    parse_args "$@"

    echo ""
    echo -e "${BLUE}CUSTOMER_NAME Intelligent Bill Explainer - Validation${NC}"
    echo -e "${BLUE}==================================================${NC}"
    echo ""

    check_prerequisites
    validate_infra
    run_unit_tests
    run_smoke_tests

    print_summary
}

main "$@"
