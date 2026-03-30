#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SERVER_SCRIPT="$REPO_ROOT/.github/plugin/mcp/csa_tools_server.py"

if [[ -x "$REPO_ROOT/.venv/bin/python" ]] && "$REPO_ROOT/.venv/bin/python" -c "import mcp, tools" >/dev/null 2>&1; then
    cd "$REPO_ROOT"
    exec "$REPO_ROOT/.venv/bin/python" "$SERVER_SCRIPT"
fi

if command -v uv >/dev/null 2>&1; then
    cd "$REPO_ROOT"
    exec uv run python "$SERVER_SCRIPT"
fi

if command -v python3 >/dev/null 2>&1 && (cd "$REPO_ROOT" && python3 -c "import mcp, tools" >/dev/null 2>&1); then
    cd "$REPO_ROOT"
    exec python3 "$SERVER_SCRIPT"
fi

echo "CSA-Copilot plugin MCP server could not start." >&2
echo "Expected one of the following:" >&2
echo "  1. A repo-local .venv with the project dependencies installed" >&2
echo "  2. 'uv' available on PATH so the plugin can bootstrap from pyproject.toml" >&2
echo "  3. A system python3 with both 'mcp' and the repo dependencies installed" >&2
exit 1