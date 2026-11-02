$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSEdition -eq 'Desktop') {
    # A PowerShell 7 parent may supply its incompatible module search path to 5.1.
    # Correct this process only; never change a persistent environment variable here.
    $env:PSModulePath = [IO.Path]::Combine($PSHOME, 'Modules') + ';' + $env:PSModulePath
}

function Get-DoxaRoot([string]$Path) {
    $root = [IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
    if ($root -eq [IO.Path]::GetPathRoot($root).TrimEnd('\', '/')) { throw 'An installation cannot be a drive root.' }
    if ((Test-Path -LiteralPath $root) -and ((Get-Item -LiteralPath $root -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Installation roots must not be links or junctions.'
    }
    return $root
}

function Get-DoxaChild([string]$Root, [string]$Relative) {
    if ([string]::IsNullOrWhiteSpace($Relative) -or [IO.Path]::IsPathRooted($Relative) -or
        $Relative.Contains(':') -or (($Relative -split '[/\\]') -contains '..')) { throw 'Unsafe installation entry.' }
    $target = [IO.Path]::GetFullPath((Join-Path $Root $Relative))
    if (-not $target.StartsWith($Root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Installation entry escapes the named installation directory.'
    }
    $cursor = $target
    while ($cursor.Length -gt $Root.Length) {
        if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Linked installation entries are not supported.'
        }
        $cursor = [IO.Path]::GetDirectoryName($cursor)
    }
    return $target
}

function Get-DoxaHash([string]$Path) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }

function Write-DoxaJson([string]$Path, $Value) {
    $temporary = $Path + '.install-' + [Guid]::NewGuid().ToString('N')
    try {
        [IO.File]::WriteAllText($temporary, ($Value | ConvertTo-Json -Depth 12), [Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $temporary -Destination $Path -Force
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary }
    }
}

function Assert-DoxaEnvironmentKey([string]$Name) {
    if ($Name -ne 'Environment' -and $Name -notmatch '^Software\\DOXA\\InstallTests\\[A-Za-z0-9_-]+\\Environment$') {
        throw 'Only the current-user Environment key or an isolated DOXA test key is allowed.'
    }
}

function Get-DoxaUserPath([string]$Name) {
    Assert-DoxaEnvironmentKey $Name
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($Name)
    try {
        if ($null -eq $key -or -not ($key.GetValueNames() -contains 'Path')) {
            return @{ value = $null; kind = 'ExpandString' }
        }
        return @{ value = [string]$key.GetValue('Path', $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames); kind = $key.GetValueKind('Path').ToString() }
    } finally { if ($key) { $key.Dispose() } }
}

function Set-DoxaUserPath([string]$Name, $Value, [string]$Kind) {
    Assert-DoxaEnvironmentKey $Name
    $key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($Name)
    try {
        if ($null -eq $Value) { $key.DeleteValue('Path', $false) }
        else { $key.SetValue('Path', [string]$Value, [Microsoft.Win32.RegistryValueKind]::$Kind) }
    } finally { $key.Dispose() }
    if ($Name -eq 'Environment') {
        if (-not ('DoxaEnvironmentNotice' -as [type])) {
            Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class DoxaEnvironmentNotice {
 [DllImport("user32.dll", CharSet=CharSet.Unicode)]
 public static extern IntPtr SendMessageTimeout(IntPtr h, uint m, UIntPtr w, string l, uint f, uint t, out UIntPtr r);
}
'@
        }
        $result = [UIntPtr]::Zero
        [void][DoxaEnvironmentNotice]::SendMessageTimeout([IntPtr]0xffff, 0x1a, [UIntPtr]::Zero, 'Environment', 2, 5000, [ref]$result)
    }
}

function Test-DoxaPathEntry([string]$Entry, [string]$Bin) {
    $expanded = [Environment]::ExpandEnvironmentVariables($Entry.Trim().Trim('"')).TrimEnd('\', '/')
    return $expanded.Equals($Bin.TrimEnd('\', '/'), [StringComparison]::OrdinalIgnoreCase)
}

function Read-DoxaInstallation([string]$Root) {
    $file = Get-DoxaChild $Root 'install-manifest.json'
    if (-not (Test-Path -LiteralPath $file)) { return $null }
    $value = Get-Content -LiteralPath $file -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($value.application -ne 'DOXA' -or $value.format -ne 1 -or $value.root -ne $Root) {
        throw 'Existing installation metadata is incompatible; nothing was removed.'
    }
    Assert-DoxaEnvironmentKey $value.environment_key
    foreach ($entry in $value.files) { [void](Get-DoxaChild $Root $entry.path) }
    return $value
}
