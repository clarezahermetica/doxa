# Development and Windows packaging

Install from source using the [repository README](../README.md). Python 3.12 or newer is
required by `pyproject.toml`; Node.js and a browser are not terminal runtime requirements.

## Development checks

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy --platform linux
.\.venv\Scripts\python.exe -m mypy --platform win32
.\.venv\Scripts\python.exe scripts/export_contracts.py
git diff --exit-code docs/contracts
```

On macOS/Linux, substitute `.venv/bin/python` for the Windows interpreter path.
GitHub CI runs Python 3.12 and 3.14 on Ubuntu with Ruff, mypy, pytest and generated-schema
consistency checks. The public regression suite uses offline fixtures and mocked providers;
it is not bundled in the installed application. Passing tests do not establish model quality.

The generated [record schema](contracts/records.schema.json) and
[OpenAPI schema](contracts/openapi.json) are maintained references. Regenerate them when
contracts change rather than editing or deleting their output by hand.

## Select the source runtime

An installed executable is separate from a source checkout. Check `doxa --version`,
`doxa runtime-info --json` and, on Windows, `Get-Command doxa` before attributing behavior
to a build. The current source identifies terminal v24 and package 0.1.0a0.

After installing the checkout into its `.venv`, PowerShell can launch it explicitly:

```powershell
.\scripts\launch_development.ps1 -VersionOnly
.\scripts\launch_development.ps1 -Workspace 'C:\DOXA-workspaces\existing' -Diagnostics
.\scripts\launch_development.ps1 -Workspace 'C:\DOXA-workspaces\existing'
```

Replace the example with an existing workspace containing `ledger.sqlite3`. The helper
requires the project's `.venv`, restores the caller's workspace environment and does not
replace global launchers or saved workspace selection. Create a new workspace through the
normal terminal workflow when needed. On macOS/Linux, `.venv/bin/doxa` selects this checkout.

## Offline acceptance

Use the [canonical exercise](canonical-research.md) for the fixed corpus, A/B/C harness,
six-system companion and independent archive inspector. Keep test workspaces separate from
existing research. These are engineering acceptance checks, not causal model-quality studies.
The [six-system reference](research-systems.md) documents finite-cache transitions and limits.

## Internal terminal builds

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
Run the [development checks](#development-checks),
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
See [storage](workspaces.md) and [recovery](workspaces.md#recovery-principles). Installation is not permission
to run inference, reconcile billing or move/merge histories.

Close viewers and deliberately stop owned workers before removing their executable:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\Programs\DOXA\Uninstall-DOXA.ps1"
```

Uninstall removes only hash-matching manifest-owned files and the owned current-user
PATH entry. Unknown/modified files, research workspaces, preferences, credentials and
exports are preserved. Uninstalling a viewer does not cancel a remote operation or settle
its bill. Keep verified backups independently of application installation files.
