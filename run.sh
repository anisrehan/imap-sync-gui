#!/usr/bin/env bash
# Run IMAP Sync GUI using the project's virtual environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec "$SCRIPT_DIR/.venv/bin/python" main.py "$@"
