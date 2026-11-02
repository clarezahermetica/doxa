# Pass 3 reliability gate — persistence inventory (before changes)

Existing implementation inspected before editing. This inventory distinguishes saved records
from transient UI state. One canonical SQLite ledger per workspace remains authoritative.

| State | Location / authority | Existing write / restart behavior | Reliability gate |
| --- | --- | --- | --- |
| Model profiles / agent templates | `ledger.sqlite3`, immutable `configurations` versions | SQLite transaction; assignment pins exact versions | Reopen, compare versions/hashes; kill a transaction before commit |
| Experiments / participants / task settings | Immutable Experiment/Run/event records in the same ledger | Atomic event/object commits, idempotency, strict readers | Restart and compare exact events/configuration; preserve old rows |
| Claims, revisions, criticism, checkpoints, evaluations, context manifests | Append-only events and indexed records | Reconstructed/validated by integrity checks | Interrupted writes; restored experiment inspection |
| Sources / context / request-response / checkpoint bytes | Workspace `artifacts/sha256/...` | Unique temp + flush/fsync + atomic replacement; verified reads | Inject write/publication failure; verify all referenced hashes |
| Spending reservations / dispatch outcomes | SQLite `reservations` + `operations` | Persistent admission; unknown outcomes keep holds; no automatic replay | Kill worker with pending fake request; restart/recover and compare holds |
| Active worker ownership | Workspace `worker-locks/*.lock` | OS-held lock; persistent filename is not proof of a live worker | Kill worker; test lock release and conservative recovery |
| Worker logs | Workspace `worker-logs/` | Append-only operational output, not scientific authority | Do not use log absence as proof of zero spend |
| Workspace selection / recent paths | `%LOCALAPPDATA%/DOXA/client.json` | Unique temporary write, fsync, replace; explicit validated selection | Restart, missing path/error tests; no silent new workspace |
| Getting Started preference | `%LOCALAPPDATA%/DOXA/terminal.json` | Atomic replace; persists checkbox and guide position | Keep separate from appearance settings; preserve current values |
| Theme | Textual `App.theme`, process memory only | **No DOXA persistence hook. Reverts to default on a fresh viewer.** | Reproduce first, then save immediately on committed changes; normal/forced exit tests |
| Catalog descriptions | Workspace `model-catalog.json` | Atomic replace under DB lock; descriptive only | Reopen and compare; corrupt files must not be overwritten |
| Runtime enablement / allowance controls | Workspace `runtime-settings.json` | Fixed `.tmp`, replace; not currently fsynced | Audit partial write behavior; preserve original controls |
| Credentials | Referenced environment / existing `.env`; workspace `credentials/*.dpapi` | No credential value in ledger; DPAPI file is exclusive-create, currently not atomic/fsynced | Audit partial secret-file creation using dummy credentials only; never rotate original keys |
| Form drafts / current selection / filters / guide navigation | In-memory widgets/app fields | **No saved draft repository exists.** Unsaved forms are lost on viewer closure | Test/document this limit; do not claim autosave or add a draft product feature |
| FTS / retrieval indexes | SQLite `search_documents` / `search_fts`; workspace `retrieval-cache/<scope>/` | Derived index; eligibility comes from authoritative records, not caches | Existing revocation/visibility tests; no live Moss |
| Workspace backup | New directory with SQLite backup, artifacts and hash manifest | Includes committed WAL state; validates before publish; excludes secrets/preferences/runtime controls | Restore to a new isolated location and compare history, configuration, holds and artifacts |
| Research JSON/JSONL/ZIP export | Explicit new user-selected file | JSON and legacy JSONL wrote directly without fsync; ZIP staged before publication. **Not a restorable SQLite workspace backup.** | Reproduce JSON/JSONL flush gaps, publish atomically; distinguish backup/export without rewriting identities |
| Portable application versions | Existing `dist/DOXA-Terminal-v*`, archives and launchers | Installation files contain no authoritative workspace | Preserve artifacts and hashes; source changes do not patch existing frozen executables |
| Retained Studio / desktop | Studio uses transient React state; legacy direct desktop defaults to `%LOCALAPPDATA%\DOXA` | No browser draft store found; desktop's default differs from the terminal selection | Read-only audit only; use an explicit common data directory, do not move/merge histories or revive GUI work |

No paid/live acceptance is authorized by this gate. Existing provider transports are inspected
and documented, not expanded. A named provider/model, maximum spend and disclosure scope are
still required separately before any real request.
