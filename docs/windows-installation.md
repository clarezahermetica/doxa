# Windows installation and the `doxa` command

This is the archived procedure for an internal v17 package. That package is not included
in the proof-of-concept publication and predates the publication security fixes. For
current source installation, use [README](../README.md). No binary release is provided.

The v17 terminal distribution includes the accepted reliability fixes and corrected Help.
Python is bundled; Node.js is not required. Existing v16 and older archives remain untouched.
Installed v16 is not changed automatically. Run the explicit procedure below to upgrade;
the installer retains its earlier version directory and preserves workspace preferences.

## Install per user

Extract `DOXA-Terminal-v17-Windows.zip` to a new local folder outside OneDrive. Open PowerShell in that extracted
folder and run the explicit PATH-registration command:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-DOXA.ps1 -AddToPath
```

The execution-policy override applies to this invocation only. No administrator privileges
are required for the default location. Nothing modifies machine-wide environment variables.
Without `-AddToPath`, installation copies the app but changes no persistent PATH value.

Default installation:

```text
%LOCALAPPDATA%\Programs\DOXA\
  bin\doxa.cmd                    stable forwarding command
  versions\v17\DOXA\doxa.exe      bundled application and dependencies
  Uninstall-DOXA.ps1
  DOXA-InstallCommon.ps1
  install-manifest.json           owned-file hashes and PATH reversal information
```

The installer checks for conflicting `doxa` commands, validates package hashes, refuses an
unrelated destination, and registers only this installation's `bin` in the current-user PATH.
Reinstalling the same verified package is idempotent. Modified installed files are not silently
overwritten. An interrupted install may leave incomplete files; do not use an incomplete
installation. Retain the extracted installer for verification/recovery.

Open a **fresh terminal host** after installation (an existing Windows Terminal process may
retain its old environment even in a new tab). From any ordinary working directory:

```powershell
doxa
doxa --help
doxa --version
```

The command opens the existing Textual application in that terminal, not a new GUI/window.
PowerShell, Windows Terminal and Command Prompt use the same forwarding command. `where.exe doxa`
or `Get-Command doxa` shows command resolution. The PATH edit does not retroactively rewrite the
environment of already running shells; opening a fresh host is the normal remedy.

## Workspace and credentials

The app first honors explicit `DOXA_DATA_DIR`, then the remembered canonical selection in
`%LOCALAPPDATA%\DOXA\client.json`. Otherwise it uses the stable per-user workspace location,
opening selection if no valid workspace exists; it does not search the shell's current
directory or silently initialize a new ledger. `W` selects/creates a
workspace deliberately. A missing remembered path remains an error/selection prompt rather
than being replaced by another empty history. Installation does not edit these preferences.

Use `doxa workspace-path` to inspect the current selection, or explicitly select an existing
workspace without moving or merging it:

```powershell
doxa workspace-open "C:\path\to\existing-workspace"
```

Theme settings remain in `%LOCALAPPDATA%\DOXA\appearance.json`. Workspace ledgers, artifacts,
credentials, reservations and exports remain outside the installed application. Environment
credential references still resolve through the existing controller. No installation or
startup action authorizes inference or releases the historical uncertain Moss hold.

## Uninstall

Close installed DOXA viewers/workers deliberately before removing their binaries. Uninstall
does not cancel a research run or settle provider charges:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\Programs\DOXA\Uninstall-DOXA.ps1"
```

Only hash-matching manifest-owned installed files and DOXA's owned current-user PATH entry
are removed. Unknown/modified files are preserved. Directories are removed only when empty;
there is no recursive workspace deletion. User preferences, workspaces, credentials, artifacts
and exports are neither removed nor reset. If PATH changed independently, only the DOXA bin
entry is removed; unrelated entries remain. A pre-existing manually registered bin path is
not claimed as installer-owned.

## Developers

The Python package already declares `doxa = "doxa.cli.main:app"`. A standard editable/package
installation supplies the same command in that environment. The standalone entry imports and
runs the same Typer app, which opens the same ResearchConsole/controller with no arguments.
There is no second research engine or independent CLI. Source and frozen `--version` use the
same application/build identity. Explicit `--data-dir` remains available for scripts.

See the [installation verification report](verification/pass3-installation.md) for actual
Windows results and the distinction between isolated same-user testing and clean-machine or
manual Windows Terminal acceptance. This release is unsigned; no signing, GitHub publication,
deployment or live inference is performed here. Pass 4 is not started.
