[CmdletBinding()]
param([string]$InstallRoot)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'DOXA-InstallCommon.ps1')
if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
    $InstallRoot = if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'install-manifest.json')) {
        $PSScriptRoot
    } else { Join-Path $env:LOCALAPPDATA 'Programs\DOXA' }
}
$root = Get-DoxaRoot $InstallRoot
$manifest = Read-DoxaInstallation $root
if (-not $manifest) { Write-Output 'No owned DOXA installation found; no files or PATH were changed.'; return }
foreach ($file in $manifest.files) {
    $target = Get-DoxaChild $root $file.path
    if ((Test-Path -LiteralPath $target) -and (Get-DoxaHash $target) -ne $file.sha256) {
        throw 'Modified installation files were preserved. No uninstall was attempted.'
    }
}
$bin = Get-DoxaChild $root 'bin'
if ($manifest.path_added) {
    $current = Get-DoxaUserPath $manifest.environment_key
    if ($current.value -ceq $manifest.path_after) {
        Set-DoxaUserPath $manifest.environment_key $manifest.path_before $manifest.path_kind_before
    } else {
        $next = @( ([string]$current.value -split ';') | Where-Object { -not (Test-DoxaPathEntry $_ $bin) }) -join ';'
        Set-DoxaUserPath $manifest.environment_key $next $current.kind
    }
}
$remaining = @()
$directories = @{}
foreach ($file in $manifest.files) {
    $target = Get-DoxaChild $root $file.path
    if (-not (Test-Path -LiteralPath $target)) { continue }
    if ((Get-DoxaHash $target) -ne $file.sha256) {
        $remaining += $file.path; continue
    }
    # All removals are named manifest files, validated inside the explicit install root.
    Remove-Item -LiteralPath $target -Force
    $parent = [IO.Path]::GetDirectoryName($target)
    while ($parent.Length -gt $root.Length) { $directories[$parent]=$true; $parent=[IO.Path]::GetDirectoryName($parent) }
}
foreach ($directory in @($directories.Keys | Sort-Object Length -Descending)) {
    if ((Test-Path -LiteralPath $directory) -and -not @(Get-ChildItem -LiteralPath $directory -Force).Count) {
        Remove-Item -LiteralPath $directory
    }
}
if ($remaining.Count) { throw 'Modified installation files were preserved. Installation metadata retained for inspection.' }
Remove-Item -LiteralPath (Get-DoxaChild $root 'install-manifest.json')
if (-not @(Get-ChildItem -LiteralPath $root -Force).Count) { Remove-Item -LiteralPath $root }
Write-Output 'DOXA installed files and its owned user-PATH registration removed. Workspaces, preferences, credentials, exports and unrelated files were preserved.'
