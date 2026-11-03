# Storage and persistence guarantees

The active workspace is explicit. It is not the application installation directory. Selecting
a workspace does not merge histories. `workspace-path`, the terminal notice and `W` identify it.

| State | Location | Authority and persistence |
| --- | --- | --- |
| Model profiles and agent templates | Workspace `ledger.sqlite3`, `configurations` | Immutable versions committed in one SQLite transaction. Existing experiments pin versions; later edits do not reassign them. |
| Experiments, runs, agents, claims, criticism, revisions, evidence relationships, evaluations, memory states | SQLite `events` and `records` | Canonical append-only history and indexed projection. Atomic event/object writes, ancestry and idempotency checks; immutable-history triggers. |
| Spending and dispatch | SQLite `reservations`, `operations` | Persistent admission and conservative uncertainty. Unknown bills retain the original hold. These rows are included in workspace backup/restore. |
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

[Recovery](recovery.md) gives the operator steps for interruption and verified restoration.
