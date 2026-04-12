#!/usr/bin/env bash
set -e
# Resolve the backend directory regardless of where the script is called from.
BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$BACKEND_DIR"
source "$BACKEND_DIR/.venv/bin/activate"
uvicorn app.main:app --reload --port 8000
