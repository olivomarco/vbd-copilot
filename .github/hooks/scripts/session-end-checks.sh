#!/bin/bash
set -euo pipefail

echo "🔍 Running session-end validation checks..."

# Activate venv
if [[ -f .venv/bin/activate ]]; then
    source .venv/bin/activate
else
    echo "⚠️  No local venv found, relying on system packages"
fi

echo "── ruff check ──"
ruff check .

echo "── pytest + coverage ──"
python -m pytest tests/ -v --cov --cov-report=term-missing

echo "✅ All session-end checks passed."
