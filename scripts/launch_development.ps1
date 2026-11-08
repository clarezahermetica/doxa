param([string]$Workspace, [switch]$VersionOnly, [switch]$Diagnostics)
$ErrorActionPreference = 'Stop'
$doxaRoot = Split-Path -Parent $PSScriptRoot
$doxaPython = Join-Path $doxaRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $doxaPython)) { throw 'Create the project .venv first.' }
# No installed launcher, credential or saved workspace selection is changed.
$doxaPreviousWorkspace = $env:DOXA_DATA_DIR
try {
if ($Workspace) {
    $doxaWorkspace = [System.IO.Path]::GetFullPath($Workspace)
    if (-not (Test-Path -LiteralPath (Join-Path $doxaWorkspace 'ledger.sqlite3'))) {
        throw 'Select an existing DOXA workspace. Nothing was initialized.'
    }
    $env:DOXA_DATA_DIR = $doxaWorkspace
}
if ($VersionOnly) {
    & $doxaPython -c 'from doxa.cli.main import app; app()' --version
} elseif ($Diagnostics) {
    & $doxaPython -c 'from doxa.cli.main import app; app()' runtime-info --json
} else {
    & $doxaPython -c 'from doxa.cli.main import app; app()'
}
$doxaExitCode = $LASTEXITCODE
} finally {
    $env:DOXA_DATA_DIR = $doxaPreviousWorkspace
}
exit $doxaExitCode
