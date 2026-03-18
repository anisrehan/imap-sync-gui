# IMAP Sync GUI — Plesk → cPanel

A desktop application for migrating emails between IMAP servers (e.g. Plesk → cPanel).

## Features

- Store multiple **server profiles** (host, port, SSL, optional admin credentials) — encrypted at rest
- Store multiple **email account pairs** (source + destination email / password) — encrypted at rest
- **Bulk import** accounts from a CSV file
- **Live progress** per account: folder name, message count, progress bar, status colour
- Start / stop individual accounts or all at once
- Concurrent sync — each account runs in its own background thread

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run

```bash
bash run.sh
# or directly:
.venv/bin/python main.py
```

## Build Executable

Create a standalone Linux executable with PyInstaller:

```bash
./build.sh
```

Output:

- Executable: `dist/imap-sync-gui`
- Build files: `build/`
- Spec file: `imap-sync-gui.spec`

Run the packaged executable with:

```bash
./dist/imap-sync-gui
```

If you want a single-folder build instead of a single-file binary, replace `--onefile` with `--onedir`.

## Linux Desktop Launcher

Install a desktop launcher and icon for the current user:

```bash
./install-desktop.sh
```

This installs:

- Desktop entry: `~/.local/share/applications/imap-sync-gui.desktop`
- Icon: `~/.local/share/icons/hicolor/scalable/apps/imap-sync-gui.svg`

After installation, the app appears in the desktop applications menu as `IMAP Sync GUI`.

## Windows Build

Windows packaging should be run on a Windows machine:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\build-windows.ps1
```

The Windows build script uses:

- `build-windows.ps1`
- `imap-sync-gui.spec`
- `windows-version-info.txt`

If `assets/icon.ico` is present, it will be embedded into the Windows executable automatically.

## CSV Import Format

Each row: `source_email,source_password,destination_email,destination_password`

An optional header row is auto-detected and skipped.

## Security

Passwords are encrypted with Fernet symmetric encryption (AES-128-CBC + HMAC).  
The encryption key is stored in `~/.config/imap-sync-gui/secret.key` (mode 0600).  
The database is stored in `~/.config/imap-sync-gui/data.db`.
