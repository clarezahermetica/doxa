# Pass 1 — Workspace and backend stabilization

Verified October 31, 2026. This is Pass 1 only. Studio/native GUI remain frozen; no six-system
algorithm was rewritten. Existing uncommitted work was preserved. No live inference, Moss,
paid calls, web research, deployment or GitHub push was performed. README stays empty.

## Empty-workspace root cause and preservation

The stored LocalAppData/DOXA/client.json explicitly selected LocalAppData/DOXA/workspace.
That ledger is valid and empty. The existing project .doxa ledger has 9 runs, 223 events,
291 immutable records and 37 referenced artifacts. Selection takes priority over ancestor
project discovery; launching outside a checkout also falls back to LocalAppData when no
preference exists. This was a selection/discoverability problem, not missing project data
or a split persistence implementation in the package.

The active preference now selects the existing project .doxa. The empty workspace remains
available in recents. The terminal's W selector offers recent paths, accepts existing paths,
remembers only a validated selection, and requires explicit creation. Empty workspaces now
explain that W can open an existing history. Missing/corrupt/unrelated selections fail closed.
The full canonical path is available through workspace-path and the selector. Bad preference
JSON/types do not crash startup; missing remembered paths are never silently recreated.

All 11 original workspaces were inventoried read-only. All original event ID/body hashes and
schema revisions remained unchanged. Verified backups reside under private/pass1-2026-10-31;
two backups retried outside OneDrive under LocalAppData/DOXA/pass1-backups-2026-10-31 after
Windows denied directory renames. The private backup-report.json maps each source and snapshot.
An independent restore of the project backup matches the original event/record/artifact counts.
Credentials, .env, operational preference files, runtime controls and process locks are excluded
from snapshots. The original credentials remain in place and were not rotated or replaced.

## Defects fixed and changed files

| Files | Fix or purpose |
| --- | --- |
| core/workspaces.py; cli/workspace_screen.py; cli/console.py | Validate existing SQLite shape/version before migration; remember bounded recent paths through a unique atomic preference write; handle invalid/missing/empty selections without replacing histories. Only small workspace/error UI changes. |
| cli/main.py; cli/workbench.py | Workspace diagnostics/selection, integrity checks, backup/restore and local reconciliation commands; inspection subcommands cannot silently create workspaces. Explicit synthetic demo creation in a new empty directory remains compatible. |
| storage/migrations/env.py | An interrupted upgrade previously left DDL behind. Explicit BEGIN IMMEDIATE plus commit/rollback makes upgrade DDL and version updates atomic, serializes concurrent migration writers, and supports retry. Existing version scripts and revision numbers are unchanged. |
| storage/workers.py; core/execution.py; core/workbench.py | OS-held per-run ownership excludes competing workers; fresh state is read after acquisition. The OS releases ownership after process death. Closing a viewer does not own/cancel its detached worker. A local response received after cancellation is recorded as an observation but cannot continue execution. |
| storage/database.py; storage/budget.py; storage/local_dispatch.py | Atomic admission checks reject dispatch after terminal run state. Interrupted local starts now receive immutable uncertain records; paid in-flight operations become uncertain and retain reservations. |
| core/controller.py | Recovery/reconciliation refuses active worker ownership. Local admission holds require an explicit stopped-process confirmation and nonempty evidence; the attestation is immutable human annotation, not verifier evidence or a generated model result. Billing reconciliation requires a terminal run and no owned worker. |
| storage/ledger.py | Include workspace-local protected credential values in ledger secret rejection. |
| storage/integrity.py | Read-only SQLite checks, event/index/sequence/idempotency/ancestry checks, record projection reconstruction/comparison, immutable trigger/configuration checks, settlement consistency and referenced-artifact hash/size checks. Detect corruption; do not overwrite or repair history. |
| storage/backup.py | Consistent SQLite backup API snapshot (including WAL commits), artifact copies and SHA-256 manifest. Verify before publication and after restore-copy. Restore only to a new destination; reject path traversal, replacement and merging. |
| tests/test_pass1_stabilization.py; tests/test_backend_completion.py | Twenty added acceptance cases and an existing storage-test fixture correction: service uncertainty is tested on a separate configured run instead of dispatching a failed run. |
| scripts/build_terminal.ps1; Open DOXA Terminal.cmd | Versioned portable console build using the same backend. No GUI packaging changes. |

## Recovery states and operating procedure

A configured run may be started explicitly. Only one worker can own a run. A crash releases
its OS lock but does not pretend the run completed or automatically restart it. A running
label alone does not establish that a worker is alive. Cancel the orphaned run explicitly,
then recover it. Recovery refuses a still-owned worker and never calls a provider.

Paid prepared operations become failed and paid in-flight operations become uncertain.
Their reservations remain held; unknown billed cost stays null. Started local calls become
uncertain and continue blocking their runtime slot. An operator may release a local slot
only after confirming execution stopped and recording evidence. The original call ID stays
non-replayable. A stopped-process attestation closes an interrupted attempt as failed; it
does not claim a model outcome. Remote settlement uses explicit operator-reported final
billing evidence, not an inference from a timeout or a local cancellation.

```powershell
.\.venv\Scripts\doxa.exe workspace-path --json
.\.venv\Scripts\doxa.exe workspace-open 'C:\path\to\doxa\.doxa'
.\.venv\Scripts\doxa.exe check-workspace --data-dir .\.doxa
.\.venv\Scripts\doxa.exe backup-workspace 'D:\DOXA-backups\new-snapshot' --data-dir .\.doxa
.\.venv\Scripts\doxa.exe restore-workspace 'D:\DOXA-backups\new-snapshot' 'D:\DOXA-workspaces\new-restored-copy'
.\.venv\Scripts\doxa.exe run cancel RUN_ID --data-dir .\.doxa
.\.venv\Scripts\doxa.exe recover RUN_ID --data-dir .\.doxa
.\.venv\Scripts\doxa.exe reconcile-local CALL_ID .\stop-evidence.txt --confirm-stopped --data-dir .\.doxa
```

These are example commands, not commands that execute live services. Backup destinations
must be new and outside the source workspace. Backups contain private research history;
keep them private. After restore, select the restored copy explicitly. No credentials are
automatically copied and no in-flight action is resumed. Derived FTS indexes remain caches
in the canonical database; existing rebuild tests remain intact.

## Final source verification

The entire suite was run after the last Python source change: **223 passed** in 211.66 seconds.
Twenty new cases cover missing/invalid/empty/unrelated workspaces, recent selection, Unicode/
space/percent Windows paths, legacy upgrades, rollback/retry of failed migration DDL, WAL
snapshots, restore validation/non-overwrite/path traversal, projection corruption, artifact
integrity, parallel event sequence allocation, idempotency/batch rollback, immutable SQL
triggers, secret rejection, held reservations, atomic outcome rollback, local cancellation,
worker exclusion, actual child-process termination/OS lock release and terminal workspace
interaction. Model behavior uses mocked transports only.

Ruff passes; strict mypy passes 78 source files. One pre-existing Starlette/httpx TestClient
deprecation warning remains. No new warnings/regressions remain in the final suite. No shared
Pydantic contract/schema or graphical UI changed in this pass, so Studio regeneration/build
was not required. Existing GUI changes from earlier work are preserved untouched.

## Unresolved limits

- Process death cannot establish remote job termination or vendor billing. Unknown outcomes
  remain held pending explicit operator evidence. Operator attestations are not independently
  verified. No remote cancellation guarantee is made.
- Locks protect a local workspace on one machine. Multi-host access via shared/OneDrive-synced
  ledgers is unsupported. Sync/antivirus can temporarily block publication; failures preserve
  source data. Prefer an unsynced local backup destination and retry with a new path.
- Hash manifests detect corruption, not a malicious host replacing both data and manifest.
  No cryptographic signing/encryption, power-loss certification or automatic repair is claimed.
  Pre-existing partially applied upgrades must be backed up and reviewed; no tables are dropped
  to guess a repair. The inspected workspaces passed checks.
- Budgets and dispatch guards are scoped to each canonical workspace, not an account-wide
  distributed spending service. Do not operate copied active histories concurrently.
- Manual Windows Terminal/clean-machine acceptance remains unverified; ConPTY and headless
  Textual tests are distinct. The console distribution is unsigned.

## Pass 2 boundary — not started

The next pass requires a new instruction. Recommended concrete research-capability work:

1. Audit and complete structured Council criticism/response/adjudication semantics with
   adversarial mocked transcripts and evidence/actor/branch authorization acceptance.
2. Extend citation evaluation beyond link/coverage accounting; keep entailment and objective
   correctness unknown unless a tested evaluator establishes the relevant limited claim.
3. Implement governed model execution on text-analysis forks with pinned contexts, explicit
   authorization and fresh non-replayable call identities; current forks remain human analysis.
4. Complete cross-experiment source/corpus selection while preserving separate evidence and
   Memory Tribunal eligibility boundaries.
5. Audit capability-driven provider/runtime configuration and compatible-endpoint acceptance
   using mocks. Real models/Moss, paid services and external research remain separately gated.

Do not redesign the terminal, add modalities/runtime weight loading, resume GUI development,
or perform live provider acceptance as an implicit continuation of this pass.

## Final packaged acceptance

The v9 console build opened the remembered project workspace from an unrelated temporary
working directory under PowerShell ConPTY, displayed the persisted experiments and W recent-
workspace selector, and exited cleanly. Packaged CLI runs match all nine direct-controller
records, and exact JSON exports of all nine runs match the direct controller event-for-event.
The packaged integrity report matches 223 events, 291 records and 37 referenced artifacts.
A missing remembered path is refused without creating a directory.

Two competing frozen CLI workers started one separate synthetic fixture. Exactly one
completed; the other was refused (exit codes 0 and 1). No ModelCall or paid accounting was
created. This generated fixture is separate from all original workspaces.

All 137 packaged files and 176 publishable project files were checked for the existing
configured secret values, with zero findings. Workspace/history/credential/private directories,
.env, SQLite ledgers, node_modules, Studio and WebView assets are absent from the bundle.
The original keys remain untouched. The canonical ZIP contains the v9 console application;
the prior v8 ZIP and versioned folder remain available. The launcher targets v9.

Artifact: dist/DOXA-Terminal-Windows.zip
Size: 35,750,460 bytes.
SHA-256: 59ce0a28659b0d7bfbe1a1796ec788031eb7420f0ab2251a0835d1f3159ee3f8

Native desktop builds and sources were not rebuilt or modified. Manual Windows Terminal
and clean-machine certification were not performed. No Pass 2 work was started.
