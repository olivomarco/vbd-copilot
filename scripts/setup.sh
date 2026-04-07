#!/usr/bin/env bash
set -euo pipefail

# ── CSA-Copilot — One-time setup ─────────────────────────────────────────────
# Creates the Python virtual environment, installs backend and frontend
# dependencies, and optionally installs system packages for PPTX thumbnails.
#
# Usage:  ./scripts/setup.sh [--with-system-deps]
# ──────────────────────────────────────────────────────────────────────────────

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

WITH_SYSTEM_DEPS=false
for arg in "$@"; do
  case "$arg" in
    --with-system-deps) WITH_SYSTEM_DEPS=true ;;
    -h|--help)
      echo "Usage: $0 [--with-system-deps]"
      echo ""
      echo "Options:"
      echo "  --with-system-deps  Install libreoffice-impress and poppler-utils"
      echo "                      (needed for PPTX thumbnail generation)"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
  esac
done

# ── Dev Container detection ───────────────────────────────────────────────────

if [[ -n "${REMOTE_CONTAINERS:-}" || -n "${CODESPACES:-}" || -f /.dockerenv ]]; then
  echo "📦 Running inside a Dev Container — skipping setup (already provisioned)."
  echo "   Start the app with: ./scripts/dev.sh"
  exit 0
fi

# ── Preflight checks ─────────────────────────────────────────────────────────

echo "🔍 Checking prerequisites..."

if ! command -v gh &>/dev/null; then
  echo "❌ GitHub CLI (gh) not found. Install it from https://cli.github.com/" >&2
  exit 1
fi

if ! gh auth status &>/dev/null 2>&1; then
  echo "❌ GitHub CLI not authenticated. Run: gh auth login" >&2
  exit 1
fi

if ! command -v uv &>/dev/null; then
  echo "❌ uv not found. Install it from https://docs.astral.sh/uv/" >&2
  exit 1
fi

if ! command -v node &>/dev/null; then
  echo "❌ Node.js not found. Install Node.js 18+ from https://nodejs.org/" >&2
  exit 1
fi

if ! command -v npm &>/dev/null; then
  echo "❌ npm not found. It ships with Node.js — reinstall Node.js." >&2
  exit 1
fi

echo "✅ All prerequisites found."

# ── System dependencies (optional) ───────────────────────────────────────────

if $WITH_SYSTEM_DEPS; then
  echo ""
  echo "📦 Installing system dependencies..."
  if command -v apt-get &>/dev/null; then
    sudo apt-get update && sudo apt-get install -y libreoffice-impress poppler-utils
  elif command -v dnf &>/dev/null; then
    sudo dnf install -y libreoffice-impress poppler-utils
  elif command -v brew &>/dev/null; then
    brew install --cask libreoffice && brew install poppler
  else
    echo "⚠️  Could not detect package manager. Install libreoffice-impress and poppler-utils manually."
  fi
fi

# ── Python backend ────────────────────────────────────────────────────────────

echo ""
echo "🐍 Setting up Python environment..."
uv venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
uv pip install -e .
echo "✅ Python backend ready."

# ── Frontend ──────────────────────────────────────────────────────────────────

echo ""
echo "⚛️  Installing frontend dependencies..."
cd frontend
npm install
cd "$ROOT_DIR"
echo "✅ Frontend ready."

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "══════════════════════════════════════════════"
echo "  ✅ Setup complete!"
echo ""
echo "  Start the app:  ./scripts/dev.sh"
echo "══════════════════════════════════════════════"
