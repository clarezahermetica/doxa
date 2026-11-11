# Recovery instructions

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
there is no quota-settlement shortcut in this version. See [CLI providers](cli-providers.md).

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
