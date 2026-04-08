#!/usr/bin/env bash
set -euo pipefail

# ── CSA-Copilot — Development launcher ────────────────────────────────────────
# Starts the full development environment (Python backend + React frontend).
#
# Usage:
#   ./scripts/dev.sh              # Browser mode  — open http://localhost:5173
#   ./scripts/dev.sh --electron   # Electron mode — desktop window
#   ./scripts/dev.sh --cli        # CLI mode      — terminal app (direct)
#   ./scripts/dev.sh --docker     # CLI mode      — Docker container
# ──────────────────────────────────────────────────────────────────────────────

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

MODE="browser"
for arg in "$@"; do
  case "$arg" in
    --electron) MODE="electron" ;;
    --cli)      MODE="cli" ;;
    --docker)   MODE="docker" ;;
    -h|--help)
      echo "Usage: $0 [--electron | --cli | --docker]"
      echo ""
      echo "Modes:"
      echo "  (default)    Browser mode  — Vite dev server at http://localhost:5173"
      echo "  --electron   Electron mode — desktop window (two processes)"
      echo "  --cli        CLI mode      — runs python app.py directly"
      echo "  --docker     Docker mode   — build + run in container (needs GITHUB_TOKEN)"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
  esac
done

# ── CLI mode (direct) ─────────────────────────────────────────────────────────

if [[ "$MODE" == "cli" ]]; then
  # Activate venv (skip if already in a container with system Python)
  if [[ -n "${REMOTE_CONTAINERS:-}" || -n "${CODESPACES:-}" || -f /.dockerenv ]]; then
    echo "📦 Dev Container detected — using system Python."
  elif [[ -d ".venv" ]]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
  else
    echo "❌ Virtual environment not found. Run ./scripts/setup.sh first." >&2
    exit 1
  fi
  exec python app.py
fi

# ── Docker mode ───────────────────────────────────────────────────────────────

if [[ "$MODE" == "docker" ]]; then
  echo "🐳 Building Docker image..."
  docker build -t csa-copilot .
  echo "🚀 Starting CSA-Copilot CLI (Docker)..."
  # Prefer GITHUB_TOKEN already in the environment.  Fall back to
  # `gh auth token` only when nothing is set.
  _token="${GITHUB_TOKEN:-$(gh auth token 2>/dev/null)}"
  if [[ -z "$_token" ]]; then
    echo "❌ No GitHub token found. Set GITHUB_TOKEN or run 'gh auth login'." >&2
    exit 1
  fi
  docker run -it --rm \
    -e GITHUB_TOKEN="$_token" \
    -v "$(pwd)/outputs:/app/outputs" \
    csa-copilot
  exit 0
fi

# ── Activate venv ─────────────────────────────────────────────────────────────

if [[ -n "${REMOTE_CONTAINERS:-}" || -n "${CODESPACES:-}" || -f /.dockerenv ]]; then
  echo "📦 Dev Container detected — using system Python."
elif [[ ! -d ".venv" ]]; then
  echo "❌ Virtual environment not found. Run ./scripts/setup.sh first." >&2
  exit 1
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# ── Browser mode (default) ────────────────────────────────────────────────────

if [[ "$MODE" == "browser" ]]; then
  echo "🚀 Starting CSA-Copilot (browser mode)..."
  echo "   Frontend + backend: http://localhost:5173"
  echo ""
  cd frontend
  npm run dev
  exit 0
fi

# ── Electron mode ─────────────────────────────────────────────────────────────

if [[ "$MODE" == "electron" ]]; then
  echo "🚀 Starting CSA-Copilot (Electron mode)..."
  echo "   Starting Vite dev server and Electron shell..."
  echo ""

  cd frontend

  # Start Vite in background
  npm run dev &
  VITE_PID=$!

  cleanup() {
    echo ""
    echo "Shutting down..."
    kill "$VITE_PID" 2>/dev/null || true
    wait "$VITE_PID" 2>/dev/null || true
  }
  trap cleanup EXIT INT TERM

  # Wait for Vite to be ready
  echo "⏳ Waiting for Vite dev server..."
  for _ in $(seq 1 30); do
    if curl -s http://localhost:5173 >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done

  npm run electron:dev

  exit 0
fi
