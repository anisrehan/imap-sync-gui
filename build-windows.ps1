$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPyInstaller = Join-Path $ScriptDir '.venv\Scripts\pyinstaller.exe'
$PyInstaller = if (Test-Path $VenvPyInstaller) { $VenvPyInstaller } else { 'pyinstaller' }

& $PyInstaller --noconfirm --clean (Join-Path $ScriptDir 'imap-sync-gui.spec')
