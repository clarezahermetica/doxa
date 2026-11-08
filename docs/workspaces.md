# Workspaces, storage and recovery

The active workspace is explicit. It is not the application installation directory. Selecting
a workspace does not merge histories. `workspace-path`, the terminal notice and `W` identify it.

| State | Location | Authority and persistence |
| --- | --- | --- |
| Model profiles and agent templates | Workspace `ledger.sqlite3`, `configurations` | Immutable versions committed in one SQLite transaction. Existing experiments pin versions; later edits do not reassign them. |
| Experiments, runs, agents, claims, criticism, revisions, evidence relationships, evaluations, memory states | SQLite `events` and `records` | Canonical append-only history and indexed projection. Atomic event/object writes, ancestry and idempotency checks; immutable-history triggers. |
| Spending and dispatch | SQLite `reservations`, `operations` | Persistent admission and conservative uncertainty. Unknown bills retain the original hold. These rows are included in workspace backup/restore. |
| Account CLI dispatch | SQLite `quota_operations` (additive revision `0004`) | One durable call admission; quota consumption and USD billing remain null. In-flight/uncertain calls block additional calls through that adapter in the workspace. Backed up with the same ledger. |
| Source/context/request-response/checkpoint bytes | Workspace `artifacts/sha256/<prefix>/<hash>` | Content-addressed, verified on read; temporary write, flush/fsync, atomic publish. A process killed before publication may leave an unreferenced temp file. No automatic deletion/reconciliation follows. |
| SQL schema revision | SQLite `alembic_version` | Additive migrations; transactional DDL. Use compatible readers. Old executables may reject newer record fields even with an unchanged SQL revision. |
| Workspace selection / recents | `%LOCALAPPDATA%\DOXA\client.json` | Atomic settings file. Missing remembered paths remain errors; never silently replaced by an empty workspace. |
| Startup help / saved guide position | `%LOCALAPPDATA%\DOXA\terminal.json` | Atomic settings file. Contains a checkbox and position, not research state or saved drafts. |
| Theme | `%LOCALAPPDATA%\DOXA\appearance.json` | Versioned per-user file, committed immediately on change with fsync/atomic replace. Independent of startup-help saves. |
| Draft form fields, selected records, filters and open dialogs | Process memory | Not saved. Closing/canceling a form discards unsaved fields. There is no durable draft repository or autosave guarantee. |
| Catalog descriptions | Workspace `model-catalog.json` | Descriptive metadata, atomically saved under a DB lock. ModelProfile versions in SQLite remain authoritative. |
| Runtime enablement / spending allowances | Workspace `runtime-settings.json` | Unique temporary file, flush/fsync and atomic replace; unrelated saved keys retained. Coordinate concurrent operators: independent read/modify/write updates are not a multi-writer merge protocol. |
| Credentials | Referenced environment / `.env`, or workspace `credentials/NAME.dpapi` | Backend-only resolution. Protected values never belong in the ledger. New DPAPI ciphertext is fully written/fsynced before exclusive publication; existing credentials cannot be replaced by save. |
| Worker ownership | Workspace `worker-locks/*.lock` | OS-held lock. Filename can outlive a process; only the OS lock indicates ownership. A dead process releases it without replaying work. |
| Worker logs | Workspace `worker-logs/` | Operational logs, not proof of model success, cancellation or billing. |
| Local search | SQLite `search_documents`, `search_fts` | Derived FTS5 index. Canonical records and authorization still determine eligibility. |
| Moss scoped session/cache | Workspace `retrieval-cache/<scope>/` | Derived, principal-scoped cache; cannot authorize memory or establish source truth. Live cache behavior remains unverified. |
| Backup | New directory with `ledger.sqlite3`, `artifacts/`, `backup-manifest.json` | SQLite backup API includes committed WAL data; copied artifacts and restored snapshot are hash/integrity verified. Excludes secrets/preferences/runtime controls/caches. |
| Research export | Explicit `.json`, legacy `.jsonl`, or `.zip` destination | New file only. JSON/JSONL flushes a temporary file before exclusive publication; ZIP includes pinned configurations and verified referenced artifacts. It is an inspection/export format, not a SQLite restore format. |
| Packaged applications | Existing `dist/DOXA-Terminal-v*` and archives | Preserved installation artifacts, never experimental authority. Source fixes do not rewrite frozen applications. |

## Operational boundaries

- Completed writes survive the tested normal exits, process termination and Windows console
  closure. Durability still depends on filesystem permissions, disk health and successful saves.
  Sudden power loss, disk corruption and sync-conflict repair were not certified.
- Local settings/credential publication uses filesystem atomic replacement or exclusive hard
  links. Filesystems that do not support the needed operation report failure rather than
  weakening exclusive creation. Current Windows/NTFS tests passed; broader filesystem support
  is not established.
- SQLite serializes scientific writes. OS worker locks coordinate local processes, not two
  computers editing synchronized copies. Keep active SQLite workspaces outside sync folders
  where practical; do not move an existing workspace without an explicit, verified operation.
- Workspace backups intentionally omit credentials and operational settings. A restored history
  can be inspected without credentials; provider environment variables may still be inherited.
- No startup, viewer reconnect or restore is permission to perform inference, replay an uncertain
  request, release a reservation or invent a model result.

The recovery sections below give the operator steps for interruption and verified restoration.

## Research records

The canonical history includes ContextManifest selection details plus ProcedureManifest,
ProviderActivity, ClaimAssessment and ResearchOutcome records in the existing canonical
events/records and content-addressed artifact store. The investigation extension did not
change the SQL revision. Optional task fields default to legacy fixed-round behavior;
old runs without outcomes remain unknown. Older executables may reject the new record discriminators: preserve historical
workspaces/backups and use corrected source for new records.

Exact exports/backups remain private. `public-summary` is a narrow nonidentifying status/count
whitelist, not a sanitized full history export. Human quality labels append annotations and
never rewrite claims or judgments. Source-launch diagnostics are read-only and do not replace
global command targets, preferences or credentials.



## Recovery principles

Recovery must preserve observed history and uncertain billing. It must not rerun inference.
Use one coordinated operator on one canonical workspace. Close older viewers before opening
newer source; do not use an old executable to repair records it cannot deserialize.

## Viewer closed or terminal window disappeared

1. Reopen the same workspace using `doxa`, `W`, or `console --data-dir PATH`.
2. Inspect the selected run and its worker observation. A viewer does not own the detached
   worker. Closing the viewer must not mark its experiment complete or destroy history.
3. An active worker can still be awaiting an external result. Do not start another attempt
   as a way of retrying that pending call. Local disappearance is not remote cancellation.
4. Committed theme changes in current source are already saved in `appearance.json` and
   restored on restart. If a save error was shown, the previous complete file remains.

## Worker died or a request timed out

The durable run may still say running after a hard process kill. This is deliberately not
an invented successful or zero-cost result. Inspect the worker lock, operations and last
committed events through the terminal recovery/accounting inspector or CLI:

```powershell
.\.venv\Scripts\doxa.exe runs --data-dir .\.doxa
.\.venv\Scripts\doxa.exe inspect RUN_ID --json --data-dir .\.doxa
```

Replace `RUN_ID` with the actual ID. If a worker is still owned, recovery is refused. Cancel
deliberately, then wait for the bounded worker to exit or stop only the verified worker
process that belongs to this run. Never delete a lock file to bypass OS ownership.

Once the worker has stopped, record cancellation and explicitly recover call states:

```powershell
.\.venv\Scripts\doxa.exe run cancel RUN_ID --data-dir .\.doxa
.\.venv\Scripts\doxa.exe recover RUN_ID --data-dir .\.doxa
```

Recovery is idempotent. Prepared/unsubmitted operations become failed; submitted/in-flight
operations become uncertain. **Both retain their reservations.** Interrupted local starts
also become uncertain, without inventing a paid bill. Recovery does not create a response,
complete a scientific objective, replay a request or release money. Repeat inspection after
recovery and keep uncertainty visible.

For a local call, releasing its execution/concurrency hold requires explicit stopped-process
attestation with evidence through `reconcile-local`. For a paid operation, settlement requires
operator-supplied billing evidence and explicit reconciliation. A zero bill is not a default.
Do not use the existing scalar `reconcile` command merely to clear a warning. Unknown Moss
or other provider charges require evidence; they are not automatically reconciled.

## Restore a workspace backup

1. Keep the original workspace and backup untouched. Choose a **new** isolated destination,
   preferably outside a synchronized folder.
2. Use a workspace snapshot produced by `backup-workspace`, containing
   `backup-manifest.json`, `ledger.sqlite3` and artifacts. A research JSON/ZIP export is not
   accepted as this snapshot; there is no general ZIP-to-ledger importer.
3. Restore and verify:

```powershell
.\.venv\Scripts\doxa.exe restore-workspace C:\Private\DOXA-backup C:\Private\DOXA-restored
.\.venv\Scripts\doxa.exe check-workspace --data-dir C:\Private\DOXA-restored
.\.venv\Scripts\doxa.exe runs --data-dir C:\Private\DOXA-restored
.\.venv\Scripts\doxa.exe console --data-dir C:\Private\DOXA-restored
```

4. Compare the expected run/event/configuration counts, inspect the experiment and check
   artifacts. Restore verifies hashes and rejects unsafe paths, replacement and merging.
   A corrupt snapshot must fail without publishing the destination.
5. Reservations and unknown outcomes restore as recorded. Inspection is safe; do not resume
   or retry paid work just because a backup was restored. Separate copies are separate local
   ledgers, **not** coordinated duplicate execution sites. Never spend against both copies
   as if their local aggregate caps were one shared financial account.

Credentials, environment files, runtime controls, preferences and caches are deliberately
excluded. Preserve those privately and deliberately configure references if needed. DPAPI
secrets are tied to the Windows user/environment; copying ciphertext to another computer
does not establish recoverability. Existing environment variables still apply after restore.

## Corrupt settings or partial files

CLI subscription calls use `quota_operations`, not dollar reservations. Recovery marks
in-flight quota calls uncertain and retains the hold. It cannot establish whether a
terminated client consumed account quota, and must not replay or automatically settle
the call. The adapter remains blocked in that workspace pending evidence-based review;
there is no quota-settlement shortcut in this version. See [CLI providers](providers.md#configure-codex-in-the-terminal).

- Theme load/save errors preserve the existing settings file. Preserve a private copy, then
  inspect or move that **specific appearance file** deliberately before selecting a new theme.
  No history or credentials need to be reset for an appearance problem.
- Runtime-control errors do not authorize dispatch or zero-cost assumptions. Fix the specific
  settings file deliberately; do not replace the whole workspace.
- New credentials are encrypted first, fully flushed and exclusively published. A failed save
  cannot replace a valid credential. Unsupported filesystem publication reports an error.
- A killed artifact/settings writer may leave an unreferenced temporary file. Do not attach
  it to history or treat it as a successful write. The integrity checker verifies canonical
  references; there is no automatic repair or broad deletion command.
- Unsaved form drafts and selection/filter state are transient. They cannot be recovered from
  the ledger because they were never committed. Previously saved profiles/templates/experiments
  remain versioned and inspectable.

These procedures were exercised with real process termination, an owned Windows console
closure, mocked pending requests and isolated restored data. Hardware power loss, arbitrary
disk damage, OneDrive conflict resolution and real provider billing recovery remain unverified.
