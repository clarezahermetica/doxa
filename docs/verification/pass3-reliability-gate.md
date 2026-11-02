# Pass 3 reliability gate

Source verification passed: **322 tests**, Ruff and strict mypy (91 source files).
Live-provider acceptance remains pending separate approval; frozen packages remain unchanged.
No providers, models, scientific algorithms, contracts, SQL migrations or visual designs were
added. No live provider/Moss request, paid call, deployment or push was performed. Existing
portable packages and launchers were preserved, not rebuilt or patched.

## Inventory and reproduced defects

The [pre-change persistence inventory](pass3-reliability-inventory.md) was written before fixes.
Current state locations and guarantees are in [storage-map.md](../storage-map.md).

| Defect | Reproduction before fix | Correction / verified behavior |
| --- | --- | --- |
| Theme disappears | Selecting `nord` through Textual's theme command, exiting and reopening returned `textual-dark`; the regression failed | Source saves a committed change immediately in per-user `appearance.json`, restores it at startup and reports save/load errors. Normal exit, killed viewer and actual Windows console-window close tests pass. |
| Credential file could be published before durable completion | Injected fsync failure did not fail the old save and left a published file | Encrypt first; unique temp, flush/fsync, exclusive publication. Failed pre-publication save leaves no credential file. Existing credentials cannot be replaced. Dummy credentials only in tests. |
| Runtime controls lacked durable flush / unique staging | Injected fsync failure was ignored by the old write path | Unique temporary file, flush/fsync and atomic replacement; existing keys preserved. Invalid settings remain errors rather than being reset. |
| JSON history export wrote directly to its public destination | Injected flush failure did not fail the old exporter | Complete temporary file, flush/fsync and exclusive publication; no partial destination on tested failure. |
| Legacy JSONL export had the same direct-write gap | CLI returned success despite the injected flush failure | Same shared atomic publication, through the existing CLI command and core export boundary. Format and no-overwrite semantics retained. |

Theme restoration uses Textual's public reactive watcher alongside its existing style watcher.
Theme changes are saved on selection, not in an exit hook. Appearance is separate from guide
preferences, so a guide save cannot erase the theme. Unavailable/corrupt saved appearance is
not silently replaced; the terminal explains the issue. Failed saves preserve complete data.

## Changed files

| File | Purpose |
| --- | --- |
| `src/doxa/cli/appearance.py` | Versioned, validated per-user theme settings. |
| `src/doxa/cli/console.py` | Restore theme and persist actual selections; readable save/load notifications. No layout redesign. |
| `src/doxa/core/local_files.py` | Shared staged, flushed, atomic replacement / exclusive file publication. Operational files only. |
| `src/doxa/core/credential_store.py`; `core/secrets.py` | Apply the reproduced credential/runtime-control durability fixes without changing references or original values. |
| `src/doxa/core/exports.py`; `cli/main.py` | Atomic JSON/JSONL export publication; legacy CLI delegates to the shared function. |
| `tests/test_reliability_gate.py`; `tests/reliability_child.py` | Real owned-process failure injection, Windows console closure, restore and persistence assertions. |
| `Open DOXA Source Terminal.cmd` | Opens the corrected existing Textual app through the existing environment, without modifying a frozen package. |
| `README.md`; `docs/storage-map.md`; `docs/recovery.md`; `docs/provider-support.md` | Setup, storage, recovery, existing-provider scope and limitations. README is now written as requested. |

## Failure injection: what actually ran

All test workspaces, credentials, process markers and settings are isolated. No test kills a
user's existing viewer/worker. On Windows the environment's Python launcher can have a
different PID from its actual interpreter; the harness verifies the acknowledged parent/child
relationship and tracks the owned child rather than assuming the launcher PID is the worker.

| Test | Injected event | Required observation |
| --- | --- | --- |
| Theme normal restart | Select via the real ThemeProvider callback; exit/reopen at 80x24 | `nord` restored in a new app. |
| Theme process death | Kill acknowledged viewer without shutdown cleanup | Completed appearance save survives. |
| Theme console close | Send WM_CLOSE to the owned hidden Windows console | Console process exits; new source viewer restores the theme. This is not a manual Windows Terminal tab test. |
| Transaction death — ledger | Pause the actual ledger append after event/object SQL writes, before outer commit; terminate process | Concurrent reader and reopened controller see only the previous committed history; integrity passes. |
| Transaction death — configuration | Pause the actual profile/template transaction before commit; terminate process | Neither partial profile nor template version becomes visible. |
| Viewer death during pending request | Real DebateRuntime dispatches through fake HTTP and retains worker ownership; terminate a separate viewer | Worker remains alive, run remains running, recovery is refused while owned. |
| Worker death during pending request | Terminate that actual worker after durable in-flight dispatch | Restart leaves the operation in flight until explicit cancel/recover; then uncertain, original $0.10 hold retained, billed amount null. No replay, release or invented output. Recovery is idempotent. |
| Actual console close with detached worker | Production `start_worker` launches a synthetic run; trusted test hook pauses its turn; close owning viewer's console | Worker retains its OS lease and run remains running. The worker is explicitly cleaned up afterward. |
| File publication failures | Inject fsync / replace failure | No partial new credential/export; previous appearance/runtime/artifact content remains intact. |
| Corrupt appearance | Invalid saved JSON | File retained, warning recorded, save refuses corruption rather than silently resetting it. |
| Restore + draft boundary | Backup/restore committed versions and holds; open restored experiment; cancel a filled but unsaved template form | Saved state matches; unsaved draft is not falsely presented as persisted. |

The first theme regression failed as expected before the fix. Credential/control and
JSON/JSONL regressions also failed before their corresponding corrections. Individual
reproduction/fix logs and machine-readable JUnit evidence are in ignored `.doxa/`.
The expanded focused reliability run initially passed eleven cases; export and detached-window
cases were then added before the final full-suite acceptance run.

## Actual original-workspace backup/restore

The original workspace was snapshotted using SQLite's backup API and restored to an isolated
location outside OneDrive, without selecting it as the user's default workspace:

- Snapshot: `%LOCALAPPDATA%\DOXA\reliability-restore-439d60a045\snapshot`
- Restored: `%LOCALAPPDATA%\DOXA\reliability-restore-439d60a045\restored`
- Verified: **223 events, 291 records, 37 referenced artifacts and nine inspected runs**.
- Full `events`, `records`, `configurations`, `reservations` and `operations` rows compare equal.
  All **39 stored artifact files** were copied and hash-verified (37 are referenced by the
  ledger); restored integrity passes. All saved configuration
  versions and the unknown Moss reservation remain intact.
- A source Textual viewer opened the restored history at 80x24 and selected a persisted run;
  an exact restored-run JSON export was produced for inspection.
- Credentials/settings/cache files were deliberately excluded. Nothing was reconciled,
  retried, merged or written over the original workspace.

Private detailed evidence: `.doxa/reliability-restore-evidence.json`.
**This is a workspace backup restore, not a JSON/ZIP research-export importer.**

## Operational guarantees and explicit limits

- Persisted scientific history/configuration and spending guards remain on the one canonical
  SQLite ledger. No terminal-specific research database was created.
- Theme and tested file writes survive completed saves followed by the tested process/console
  exits. This is not hardware power-loss or storage-device certification. Failed publication
  cannot be treated as a successful save.
- Settings remain per-user or per-workspace as documented. Operational JSON read/modify/write
  files are not a general multi-writer merge protocol. Coordinate concurrent operators;
  OneDrive synchronization does not coordinate SQLite ownership across computers.
- Multi-file setup is not one global filesystem/SQLite transaction. A later form failure can
  leave an already saved protected credential or control file without a new profile/catalog
  note. Inspect actual saved versions before retrying; never overwrite a credential to clear
  an error. A saved key alone cannot authorize a paid call.
- Unsaved form drafts, filters and selections are transient; there is no durable draft store.
- Workspace backups exclude credentials/UI preferences/runtime controls/caches. They are not
  complete machine-environment backups. DPAPI transfer across users/machines is unverified.
- Exclusive file publication requires filesystem hard-link support. Current local Windows
  tests pass; broader filesystem, power-loss, disk-corruption and sync-conflict recovery are
  not certified.
- Existing v15 and earlier frozen applications/archives remain unchanged. They **do not include
  this source theme fix**. Use `Open DOXA Source Terminal.cmd` / the README source command.
  No new portable release or version replacement was made in this gate.

## Live acceptance status

**Not run: no separate named provider/model/spending authorization was supplied.** Existing
adapters are documented in the [provider matrix](../provider-support.md); mocked compatibility
must not be described as live compatibility. Follow the [minimal live procedure](../pass3-live-acceptance.md)
only after approval also covers disclosure scope. Do not retry or reconcile the historical
uncertain Moss request. No unknown billing reservation was released automatically.

## Final verification

Final source: **322 passed, one pre-existing Starlette/httpx deprecation warning, in 357.98s**.
Ruff and strict mypy (91 source files) pass. Machine-readable full-suite evidence is
`.doxa/reliability-acceptance-junit.xml`; the log is `.doxa/reliability-acceptance-full-tests.log`.
The fourteen added gate cases cover the failures listed above. Earlier 319/321-case runs
preceded the final export additions and are not substituted for the final-source run.

`Open DOXA Source Terminal.cmd` was also exercised in the host-provided Windows PowerShell
PTY against the original project history with an isolated saved `nord` preference. It rendered
the existing runs, retained the saved theme and exited with `q`, code 0. The private preference
remained `nord` afterward. This does not certify manual Windows Terminal interaction or change
any archived executable. Original-state/package hash evidence is in
`.doxa/reliability-preservation-evidence.json`; the read-only workspace inventory found the
original populated workspace and two separate valid empty legacy/default workspaces. None
was moved, merged, reset or selected over the user's canonical workspace.

| Gate area | Observed result |
| --- | --- |
| Source theme persistence and interrupted writes | Passed the normal/process/console-close and injected failure cases. |
| Worker ownership, pending mock request and recovery | Passed; no replay or automatic release; unknown billing retained. |
| Original workspace backup/restore and inspection | Passed; exact records/configurations/holds, 39 stored artifact hashes and nine run inspections. |
| Original data, credentials, preferences and package versions | Hash comparison passed; no original protected values or package archives were replaced. |
| Existing frozen portable theme behavior | Not patched or re-certified; use the source launcher for the fix. |
| Real provider/model/spending acceptance | Not run; separate named authorization is required. |
