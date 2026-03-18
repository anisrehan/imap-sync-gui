#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"
DESKTOP_FILE="${DESKTOP_DIR}/imap-sync-gui.desktop"
ICON_FILE="${ICON_DIR}/imap-sync-gui.svg"
EXEC_PATH="${SCRIPT_DIR}/dist/imap-sync-gui"

mkdir -p "$DESKTOP_DIR" "$ICON_DIR"

if [[ ! -x "$EXEC_PATH" ]]; then
  echo "Executable not found at $EXEC_PATH"
  echo "Run ./build.sh first."
  exit 1
fi

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=IMAP Sync GUI
Comment=Sync email accounts from Plesk servers to cPanel servers
Exec=${EXEC_PATH}
Icon=imap-sync-gui
Terminal=false
Categories=Network;Email;Utility;
Keywords=imap;email;migration;sync;plesk;cpanel;
StartupNotify=true
StartupWMClass=imap-sync-gui
EOF

cp "$SCRIPT_DIR/assets/icon.svg" "$ICON_FILE"
chmod 644 "$DESKTOP_FILE" "$ICON_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache "${HOME}/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "Installed desktop launcher: $DESKTOP_FILE"
