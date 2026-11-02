param([ValidatePattern('^v[0-9]+$')][string]$Version = 'v20')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$buildPath = Join-Path 'dist' "DOXA-Terminal-$Version"
$archivePath = Join-Path 'dist' "DOXA-Terminal-$Version-Windows.zip"
if ((Test-Path -LiteralPath $buildPath) -or (Test-Path -LiteralPath $archivePath)) {
    throw 'Choose a new build version; existing portable artifacts are preserved.'
}
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath $buildPath DOXA-Terminal.spec
if ($LASTEXITCODE -ne 0) { throw 'Terminal packaging failed' }
& .\.venv\Scripts\python.exe scripts/package_terminal.py $Version
if ($LASTEXITCODE -ne 0) { throw 'Terminal distribution assembly failed' }
