# Installed terminal command — November 1, 2026

## Result and architecture

DOXA terminal v16 is installed for the current Windows account at
`%LOCALAPPDATA%\Programs\DOXA`.
The stable `bin\doxa.cmd` forwards all arguments and the exit code to
`versions\v16\DOXA\doxa.exe` in the same terminal. No new window or separate CLI
is introduced. The frozen executable bundles Python, dependencies and migrations;
Python and Node do not need to be installed by the researcher.

Both the existing Python package script (`doxa = "doxa.cli.main:app"`) and the
frozen launcher use the same Typer application and existing Textual/controller path.
No arguments opens the research console. `--help`, `--version`, legacy commands
and the frozen `--cli` compatibility flag remain available. Version output is
`DOXA 0.1.0a0 (terminal v16)`; dependency/package versions were not upgraded.

The installer changes only the current-user PATH, explicitly with `-AddToPath`.
It checks command conflicts, verifies package hashes, refuses unrelated install
directories, retains versioned binaries and records owned files and PATH reversal
metadata. Repeating a completed installation does not duplicate PATH entries.
Uninstallation checks hashes before changing files or PATH, removes only owned
files and empty directories, and preserves unknown or modified user files.
There are no administrator requirements or machine-wide PATH changes.

## Installation and removal

The account installation is complete. Open a fresh terminal host and type:

```powershell
doxa
doxa --help
doxa --version
```

For another installation, extract `dist/DOXA-Terminal-v16-Windows.zip` to an ordinary
local folder, outside OneDrive and other reparse/synchronization directories, then run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-DOXA.ps1 -AddToPath
```

The execution-policy override affects that process only. Omitting `-AddToPath`
installs files without persistent command registration. To remove this installation:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\Programs\DOXA\Uninstall-DOXA.ps1"
```

An already running terminal host can retain its old PATH even in a new tab. Restart
the host. The installer does not rewrite environments inside existing processes.
Close viewers/workers deliberately before uninstalling their binaries; uninstalling
does not cancel research or settle charges.

## Workspace and preservation

Resolution is explicit `DOXA_DATA_DIR`, then the remembered selection in
`%LOCALAPPDATA%\DOXA\client.json`, then the stable per-user selection location.
Automatic ancestor/current-directory `.doxa` discovery was removed. Merely opening
the app does not initialize a missing workspace. Missing remembered paths remain
visible and can be corrected with the selector (`W`); histories are never merged.
`doxa workspace-path` reports the selection, and `workspace-open <path>` explicitly
selects a validated existing workspace.

The existing canonical selection remains the project's `.doxa` directory.
Installation does not copy or reset credentials, history, preferences or exports.
Source and installed CLI inspected the same nine persisted runs. Read-only comparisons
against the task's initial snapshot verified unchanged contents of all 223 events,
291 records, five configurations, one reservation and one operation. Artifact integrity
verification passed for 37 referenced artifacts. The uncertain Moss reservation was
not settled or released. README, `.env`, existing client/terminal/appearance preferences
and all previously archived ZIPs match their initial hashes.

## Windows acceptance actually performed

| Check | Observed result |
| --- | --- |
| Isolated installation | Real v16 ZIP extracted outside the repository; separate install directory, preferences and HKCU test environment key under the current Windows account |
| PowerShell and CMD resolution | Fresh Windows PowerShell 5.1 and CMD processes, working directory outside project/install; both resolved the stable command and reported v16 |
| Standalone dependencies | Isolated command PATH contained installed bin and Windows tools, without Python/Node entries |
| Existing history and CLI | `workspace-open`, `workspace-path --json`, `runs --json`, `check-workspace`, help and version passed; nine existing runs |
| No-argument terminal | `doxa` inside a fresh PowerShell process in an owned Windows pseudoterminal opened the existing Textual console and persisted experiments |
| Theme | Ctrl+P → Theme → nord; immediate appearance file update; normal exit and fresh launch restored nord rendering |
| Viewer exit | Both owned viewers exited through `q`; no run cancellation or false completion |
| Uninstall | Installed script with no arguments removed app/shim, restored exact original PATH and registry value kind; separate preferences and unknown export survived |
| Current account installation | Real user PATH registered; fresh PowerShell/CMD processes populated from actual user/machine registry environments resolved installed v16 outside the project |
| Historical preservation | Baseline table/file hashes and artifact integrity passed after installation/removal testing |
| Distribution scan | 143 ZIP entries; no forbidden workspace/credential paths or known credential values from the existing environment file found |

The isolated environment was **not** a separate Windows login or clean machine.
Windows pseudoterminal checks are not manual Windows Terminal UI acceptance. Neither
signing, SmartScreen behavior nor a clean machine without a developer toolchain was
tested. The older reliability gate tested forced exit/window closure; this installation
pass repeated normal theme restart on the actual frozen v16, without claiming that its
window-close crash test was repeated on the frozen binary.

## Regression evidence

The final complete suite passed **329 tests**, with one pre-existing Starlette
deprecation warning, in 339.87 seconds. Ruff passed for `src`, `tests` and the
packaging script. Strict mypy passed for 90 source files. The initial full run
passed 328 tests; the final run includes the additional modified-file uninstall test.
Seven installation/entry tests cover version/no-viewer behavior, no current-directory
workspace selection, default console entry, Unicode installation paths, idempotency,
default uninstall, conflict refusal, modified-file preservation, package corruption and
unrelated destinations. An initial Windows PowerShell ANSI/UTF-8 mismatch was reproduced
and fixed with explicit UTF-8 JSON reads. Default uninstall path resolution was also
corrected and exercised from the installed script.

No shared research contracts changed, so schema/type regeneration and a Studio rebuild
were not required. Studio/native desktop development remains frozen.

## Artifact and changed files

- `dist/DOXA-Terminal-v16-Windows.zip`: **35,881,398 bytes**.
- SHA-256: `5fafdf2433e7df86c4dd481657cac75b7962de6913b76330e69d1c1a4693fe42`.
- v15 and the older unversioned ZIP remain untouched; installation points to v16.
- `src/doxa/version.py`, `src/doxa/cli/main.py`: shared version and eager version option;
  existing default Textual entry and commands retained.
- `src/doxa/core/workspaces.py`: remove implicit CWD ancestor selection.
- `DOXA-Terminal.spec`, `scripts/build_terminal.ps1`, `scripts/package_terminal.py`:
  separately versioned bundle with `doxa.exe`, installer controls and integrity manifest.
- `scripts/windows/{Install-DOXA,Uninstall-DOXA,DOXA-InstallCommon}.ps1`: per-user
  registration, ownership/hash validation, safe path checks and reversible uninstall.
- `tests/test_installation_entry.py`: entry/workspace/Windows installer regressions.
- `docs/windows-installation.md`, this report and `docs/status.md`: operating instructions
  and measured verification boundaries. README was not modified during this task.

## Remaining limits

This is an unsigned one-folder distribution and explicit PowerShell installer, not an
MSI or auto-updater. Reparse-point installation/package roots are refused; extract to a
normal local directory. An interrupted installation may need inspection using its
retained manifest and extracted package; there is no automatic repair or transactional
installer rollback. Existing modified owned files intentionally block removal rather
than being deleted. PATH conflicts are checked in the installer process; aliases or
functions defined only in another interactive shell/profile cannot be inspected there.
Rebuilding requires the existing development environment, although running the bundle
does not. The application/workspace remains local-first and existing synchronization
warnings still apply to the unchanged OneDrive workspace.

No inference, live Moss/RunPod contact, paid call, reservation settlement, dependency
upgrade, deployment, commit, push or Pass 4 work was performed.
