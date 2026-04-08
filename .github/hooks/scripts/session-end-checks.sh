#!/bin/bash
set -euo pipefail

echo "🔍 Running session-end validation checks..."

# Activate venv
if [[ -f .venv/bin/activate ]]; then
    source .venv/bin/activate
else
    echo "⚠️  No local venv found, relying on system packages"
fi

echo "── ruff format ──"
uv run --extra dev ruff format --check .

echo "── ruff check ──"
uv run --extra dev ruff check .

echo "── pytest + coverage ──"
uv run --extra dev python -m pytest tests/ -v --cov --cov-report=term-missing

echo "✅ All session-end checks passed."
