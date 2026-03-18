#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

exec "$SCRIPT_DIR/.venv/bin/pyinstaller" \
  --noconfirm \
  --clean \
  "$SCRIPT_DIR/imap-sync-gui.spec"