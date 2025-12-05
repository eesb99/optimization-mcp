#!/bin/bash
# Runner script for optimization-mcp
# Ensures venv exists and uses correct Python interpreter

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$PLUGIN_DIR/venv/bin/python"

# Auto-setup if venv doesn't exist
if [ ! -f "$VENV_PYTHON" ]; then
    echo "Virtual environment not found. Running setup..." >&2
    "$PLUGIN_DIR/setup.sh"
fi

# Run server with venv Python
exec "$VENV_PYTHON" "$PLUGIN_DIR/server.py"
