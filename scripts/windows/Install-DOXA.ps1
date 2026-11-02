[CmdletBinding()]
param(
    [string]$PackageRoot,
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'Programs\DOXA'),
    [switch]$AddToPath,
    [string]$EnvironmentKey = 'Environment'
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'DOXA-InstallCommon.ps1')
if ([string]::IsNullOrWhiteSpace($PackageRoot)) { $PackageRoot = $PSScriptRoot }
$root = Get-DoxaRoot $InstallRoot
$package = Get-DoxaRoot $PackageRoot
Assert-DoxaEnvironmentKey $EnvironmentKey
$release = Get-Content -LiteralPath (Join-Path $package 'package-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($release.application -ne 'DOXA' -or $release.format -ne 1 -or $release.build -notmatch '^v[0-9]+$') {
    throw 'Unsupported DOXA distribution.'
}
if (@($release.files | Where-Object { $_.path -eq 'DOXA/doxa.exe' }).Count -ne 1) { throw 'The executable must be listed in the integrity manifest.' }
if (@($release.files | Group-Object path | Where-Object { $_.Count -ne 1 }).Count) { throw 'Duplicate distribution entries are not allowed.' }
foreach ($file in $release.files) {
    if ($file.path -match '(^|/)(\.env[^/]*|ledger\.sqlite3[^/]*|credentials|\.doxa|\.venv|node_modules|private|exports)(/|$)' -or $file.path.EndsWith('.dpapi')) {
        throw 'Distribution contains a forbidden private-data path.'
    }
    $source = Get-DoxaChild $package $file.path
    if (-not (Test-Path -LiteralPath $source -PathType Leaf) -or (Get-DoxaHash $source) -ne $file.sha256) {
        throw 'Distribution integrity check failed; installation was not changed.'
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $package 'DOXA\doxa.exe'))) { throw 'Packaged doxa.exe is missing.' }
$old = Read-DoxaInstallation $root
if ((Test-Path -LiteralPath $root) -and -not $old -and @(Get-ChildItem -LiteralPath $root -Force).Count) {
    throw 'Destination contains unrelated files. Choose a new per-user installation directory.'
}
if ($old -and $old.environment_key -ne $EnvironmentKey) { throw 'Use the original installation environment key.' }
$bin = Get-DoxaChild $root 'bin'
$shim = Get-DoxaChild $root 'bin\doxa.cmd'
$pathState = Get-DoxaUserPath $EnvironmentKey
$processPath = $env:Path
try {
    $env:Path = $processPath + ';' + [Environment]::ExpandEnvironmentVariables([string]$pathState.value) + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $commands = @(Get-Command doxa -All -ErrorAction SilentlyContinue)
} finally { $env:Path = $processPath }
foreach ($command in $commands) {
    if (-not $old -or $command.CommandType -notin @('Application', 'ExternalScript') -or
        -not $command.Source.Equals($shim, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Another command named doxa already resolves in this shell. It was not replaced.'
    }
}
$pathBefore = $pathState.value
$pathKindBefore = $pathState.kind
$pathAdded = $false
$pathAfter = $pathBefore
if ($old -and $old.path_added) {
    $pathAdded = $true; $pathBefore = $old.path_before; $pathAfter = $old.path_after
    $pathKindBefore = $old.path_kind_before
}
$owned = @{}
if ($old) { foreach ($file in $old.files) { $owned[$file.path] = $file.sha256 } }
[void][IO.Directory]::CreateDirectory($root)
$manifestPath = Get-DoxaChild $root 'install-manifest.json'
$manifest = [ordered]@{ application='DOXA'; format=1; root=$root; build=$release.build;
    environment_key=$EnvironmentKey; path_added=$pathAdded; path_before=$pathBefore;
    path_after=$pathAfter; path_kind_before=$pathKindBefore; state='installing'; files=@() }
if (-not $old) { Write-DoxaJson $manifestPath $manifest }

foreach ($file in $release.files) {
    if (-not $file.path.StartsWith('DOXA/')) { continue }
    $relative = 'versions/' + $release.build + '/' + $file.path
    $target = Get-DoxaChild $root $relative
    $source = Get-DoxaChild $package $file.path
    if ((Test-Path -LiteralPath $target) -and (Get-DoxaHash $target) -ne $file.sha256) {
        throw 'This installed version differs from the package. Existing files were not overwritten.'
    }
    $owned[$relative] = $file.sha256
    $manifest.files = @($owned.Keys | Sort-Object | ForEach-Object { @{path=$_; sha256=$owned[$_]} })
    Write-DoxaJson $manifestPath $manifest
    [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target))
    if (-not (Test-Path -LiteralPath $target)) { [IO.File]::Copy($source, $target, $false) }
    if ((Get-DoxaHash $target) -ne $file.sha256) { throw 'Installed file verification failed.' }
}
foreach ($name in @('DOXA-InstallCommon.ps1', 'Uninstall-DOXA.ps1', 'INSTALLATION.md')) {
    $entry = @($release.files | Where-Object { $_.path -eq $name })
    if ($entry.Count -ne 1) { throw 'Distribution control file is missing.' }
    $target = Get-DoxaChild $root $name
    if ((Test-Path -LiteralPath $target) -and $old) {
        $prior = @($old.files | Where-Object { $_.path -eq $name })
        if ($prior.Count -ne 1 -or (Get-DoxaHash $target) -ne $prior[0].sha256) { throw 'Modified control file preserved.' }
    }
    [IO.File]::Copy((Get-DoxaChild $package $name), $target, $true)
    $owned[$name] = $entry[0].sha256
}
[void][IO.Directory]::CreateDirectory($bin)
if (Test-Path -LiteralPath $shim) {
    $prior = @($old.files | Where-Object { $_.path -eq 'bin/doxa.cmd' })
    if ($prior.Count -ne 1 -or (Get-DoxaHash $shim) -ne $prior[0].sha256) { throw 'Modified command shim preserved.' }
}
$commandText = "@echo off`r`n`"%~dp0..\versions\$($release.build)\DOXA\doxa.exe`" %*`r`nexit /b %errorlevel%`r`n"
[IO.File]::WriteAllText($shim, $commandText, [Text.UTF8Encoding]::new($false))
$owned['bin/doxa.cmd'] = Get-DoxaHash $shim
$manifest.files = @($owned.Keys | Sort-Object | ForEach-Object { @{path=$_; sha256=$owned[$_]} })
$manifest.state = 'installed'
Write-DoxaJson $manifestPath $manifest

if ($AddToPath) {
    $current = Get-DoxaUserPath $EnvironmentKey
    $present = @(([string]$current.value -split ';') | Where-Object { Test-DoxaPathEntry $_ $bin }).Count -gt 0
    if (-not $present) {
        if (-not $pathAdded) { $manifest.path_before=$current.value; $manifest.path_kind_before=$current.kind }
        $next = if ([string]::IsNullOrEmpty($current.value)) { $bin } else { [string]$current.value + ';' + $bin }
        $manifest.path_added=$true; $manifest.path_after=$next
        # Record reversal before changing the single current-user PATH value.
        Write-DoxaJson $manifestPath $manifest
        Set-DoxaUserPath $EnvironmentKey $next $current.kind
    }
    if (-not @($env:Path -split ';' | Where-Object { Test-DoxaPathEntry $_ $bin }).Count) { $env:Path += ';' + $bin }
    Write-Output 'DOXA current-user PATH registration is ready. Open a fresh terminal host, then type doxa.'
} else {
    Write-Output 'Installed without PATH changes. Re-run with -AddToPath for explicit current-user registration.'
}
Write-Output "Installed $($release.build) at $root. No workspace or credential was moved."
