# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import os


PROJECT_DIR = Path(SPECPATH)
WINDOWS_ICON = PROJECT_DIR / 'assets' / 'icon.ico'
WINDOWS_VERSION_FILE = PROJECT_DIR / 'windows-version-info.txt'

icon_arg = str(WINDOWS_ICON) if WINDOWS_ICON.exists() and os.name == 'nt' else None
version_arg = str(WINDOWS_VERSION_FILE) if WINDOWS_VERSION_FILE.exists() and os.name == 'nt' else None


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[(str(PROJECT_DIR / 'assets'), 'assets')],
    hiddenimports=['PIL.ImageTk', 'PIL._tkinter_finder', 'PIL._imagingtk'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='imap-sync-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_arg,
    version=version_arg,
)
