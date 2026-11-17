# Windows source installation and optional packaging

Use the repository [README](../README.md) for current source installation and launch.
No binary release is provided. The optional packaging/installer tools below are for
verified internal Windows builds; old archives are not automatically updated by source fixes.

## Internal terminal builds

The product version is **DOXA 0.1.0 Alpha 1** (`0.1.0a1`).
`src/doxa/version.py` is authoritative for package metadata, CLI/help, the terminal
title, Windows executable metadata and the portable archive name. The current
archive is `DOXA-0.1.0a1-Windows.zip`; it is a local review artifact, not a published
release. Numeric `vNN` identifiers remain diagnostic build identities.

Installer compatibility deliberately retains `bin/doxa.cmd` and
`versions/<internal-build>/DOXA/doxa.exe`. Do not rename these directories to the
public label: existing installer ownership, rollback and launcher diagnostics use
the internal build key. Workspace and credential paths are independent of both
the public version and the executable directory. Existing packages and versions
are preserved, including their historical labels.

Build on Windows with the appropriate Python environment. `requirements-terminal.lock`
records the internal Windows/Python 3.14.7 packaging environment, including optional Moss
and PyInstaller dependencies. It is not a cross-platform runtime lock. The source package
has `dev`, `packaging` and `moss` extras for the corresponding development tools.

`DOXA-Terminal.spec`, `scripts/terminal_entry.py`, `scripts/build_terminal.ps1` and
`scripts/package_terminal.py` package the existing terminal and Python engine. They include
migrations and the model catalog, and exclude tests, development tools and graphical clients.
Node.js, a browser and a Vite server are not runtime requirements.

Before a new internal build, choose a new numeric terminal build identity in `src/doxa/version.py`.
The build script derives its default from that identity and rejects conflicting versions.
Run the [development checks](README.md#development-checks),
then from the repository root:

```powershell
.\scripts\build_terminal.ps1 -Version vNN
```

Replace `vNN` with that new numeric identity. Existing version directories and archives are
refused rather than overwritten. Do not distribute an old binary as containing newer source
fixes. Verify the resulting manifest and test startup, shutdown and workspace preservation
before distributing. Signing and clean-machine acceptance are not established by CI.

## Install a verified internal package

Extract it outside active workspaces and synchronization folders. In the extracted folder:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-DOXA.ps1 -AddToPath
```

The override applies only to this process. The default installation is per-user under
`%LOCALAPPDATA%\Programs\DOXA`, with a stable `bin\doxa.cmd` and versioned executable
under `versions\<build>\DOXA\doxa.exe`. No administrator access is needed for that default.
Without `-AddToPath`, the installer does not register a persistent PATH entry.

The installer validates package hashes, refuses conflicting commands and unrelated
destinations, and preserves modified installed files. Open a fresh terminal host after
PATH registration, then use `doxa`, `doxa --version` or `doxa --help`. `Get-Command doxa`
shows which installation will launch.

## Workspace and removal

Workspace selection, settings and credentials remain outside the installed version.
See [storage](storage-map.md) and [recovery](recovery.md). Installation is not permission
to run inference, reconcile billing or move/merge histories.

Close viewers and deliberately stop owned workers before removing their executable:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\Programs\DOXA\Uninstall-DOXA.ps1"
```

Uninstall removes only hash-matching manifest-owned files and the owned current-user
PATH entry. Unknown/modified files, research workspaces, preferences, credentials and
exports are preserved. Uninstalling a viewer does not cancel a remote operation or settle
its bill. Keep verified backups independently of application installation files.
