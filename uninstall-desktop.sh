#!/usr/bin/env bash
set -euo pipefail

DESKTOP_FILE="${HOME}/.local/share/applications/imap-sync-gui.desktop"
ICON_FILE="${HOME}/.local/share/icons/hicolor/scalable/apps/imap-sync-gui.svg"

removed=0

if [[ -f "$DESKTOP_FILE" ]]; then
  rm "$DESKTOP_FILE"
  echo "Removed $DESKTOP_FILE"
  removed=$((removed + 1))
fi

if [[ -f "$ICON_FILE" ]]; then
  rm "$ICON_FILE"
  echo "Removed $ICON_FILE"
  removed=$((removed + 1))
fi

if [[ $removed -eq 0 ]]; then
  echo "Nothing to uninstall — desktop launcher was not installed."
  exit 0
fi

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "${HOME}/.local/share/applications" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache "${HOME}/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "Desktop launcher uninstalled."
