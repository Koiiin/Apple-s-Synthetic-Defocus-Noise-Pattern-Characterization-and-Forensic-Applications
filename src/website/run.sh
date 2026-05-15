#!/usr/bin/env bash
# Run the SDNP Forensic Analyzer web server.
# Usage:  ./src/website/run.sh [port]

set -e

PORT=${1:-8000}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "============================================"
echo "  SDNP Forensic Analyzer — Web Interface"
echo "  Project root : $PROJECT_ROOT"
echo "  Server port  : $PORT"
echo "============================================"

# Use project .venv if it exists, otherwise system python
VENV="$PROJECT_ROOT/.venv"
if [ -f "$VENV/bin/uvicorn" ]; then
  PYTHON="$VENV/bin/python"
  UVICORN="$VENV/bin/uvicorn"
  echo "  Using .venv: $VENV"
  "$VENV/bin/pip" install -q -r "$SCRIPT_DIR/requirements_web.txt"
else
  UVICORN="uvicorn"
  echo "  Using system Python"
fi

# Launch uvicorn from the website directory so relative imports work
cd "$SCRIPT_DIR"
exec $UVICORN app:app --host 0.0.0.0 --port "$PORT" --reload
