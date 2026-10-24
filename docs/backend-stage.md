# October 24 backend stage

This stage extends the existing modular monolith. Python owns orchestration, credentials,
provider calls, retrieval eligibility and accounting. CLI and local FastAPI use the same
controller. SQLite and content-addressed artifacts remain canonical. No Node backend,
cloud database, GPU deployment, hosted service, queue or new execution infrastructure.

## What actually works

- Immutable, versioned agent definitions and model profiles in the same migrated SQLite
  database. Agent IDs, names, instructions/version, enabled state, role, permissions,
  tool/message allowances and private/shared scope are separate from credential references.
  Runs pin assignments; later configuration versions do not rewrite past experiments.
- Atomic run lifecycle events and terminal-state validation. Duplicate execution commands
  return their terminal history; changed commands conflict. Interrupted active runs need
  operator cancellation/reconciliation rather than automatic replay.
- A fixed **cache-policy v1 finite task**, selecting among three prewritten policies.
  It is not arbitrary generated-code repair. Its independent oracle checks read, update
  and deletion behavior; cases cannot be silently removed under version 1.
- Solo Direct makes one proposal; Solo Deliberative has separate proposer, skeptic and
  defender contexts with one physical model assignment; Collaborative asks a distinct
  researcher for an independent candidate; Adversarial tests a challenger's alternative.
  Deterministic evidence authorizes revision. Synthetic fixtures supply answers explicitly;
  no model-quality finding is inferred from their outcomes.
- Immutable commitments, typed references, negative criticism verdicts, retained failures,
  content-hashed observable checkpoint restoration, alternative branch ancestry, and
  descriptive commitment/outcome comparisons. Reflection records trigger/skip reasons
  and performs a bounded fresh post-intervention check when allowed.
- Memory quarantine, task-specific lesson validation, promotion, correction/supersession,
  terminal revocation and run-scoped private/shared eligibility. Retrieval re-reads SQLite
  after external awaits and returns SQLite text, never index-supplied authority or text.
  Operator inspection/export sees all records; participant context is a strict allowlist.
- Optional RunPod HTTP adapter and optional Moss Python SDK adapter, exercised using
  mocked boundaries only. SDK import succeeded on this Windows/Python 3.14 machine.

The original six research-system ports remain intact. These bounded operations are not
complete general implementations of every method in those ports. The original container
sandbox stays disabled; no generated Python, shell command, patch or tool executes on
the Windows host. The finite task mutates only its prewritten in-memory key/value model.

## Windows PowerShell setup

Run these from the repository root:

```powershell
Set-Location 'C:\Users\danad\OneDrive\Documents\ChatGPT\doxadoxadoxa'
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\doxa.exe init
.\.venv\Scripts\doxa.exe config-import .\examples\council.json
.\.venv\Scripts\doxa.exe configure .\examples\backend-run.json
```

Copy the run UUID printed by `configure`:

```powershell
.\.venv\Scripts\doxa.exe run-task <run-uuid> .\examples\execute-offline.json
.\.venv\Scripts\doxa.exe memory-query <run-uuid> .\examples\memory-query.json
.\.venv\Scripts\doxa.exe inspect <run-uuid>
.\.venv\Scripts\doxa.exe serve
```

In a second PowerShell terminal:

```powershell
Set-Location 'C:\Users\danad\OneDrive\Documents\ChatGPT\doxadoxadoxa\studio'
npm.cmd ci
npm.cmd run dev
```

Studio still uses the persisted-record inspector. It displays projected lifecycle status
and actual event records; there is no separate UI research state. No elaborate agent UI
was added. API schemas are available at `http://127.0.0.1:8000/docs`.

For all four offline protocols and the two-agent memory fixture:

```powershell
.\.venv\Scripts\python.exe scripts\demo_backend.py --data-dir .doxa\offline-demo
```

This writes actual local history plus `.doxa/offline-demo/demo-summary.json`. It preserves
the failed Solo Direct baseline alongside passing supplied-answer treatments. Those
differences demonstrate wiring and tests, not superiority of a model or protocol.
Separate data directories are suitable for offline fixtures only; keep one canonical
ledger directory for all paid work and aggregate accounting.

## Moss installation and local credentials

The requested JavaScript package is installed at the **repository root**, in a private
development-tools package. It is not a Studio dependency or a second backend.

```powershell
# Repository root: optional developer SDK
npm.cmd ci
# Python backend adapter
.\.venv\Scripts\python.exe -m pip install -e '.[moss]'
```

Root `.env` contains the supplied Moss credentials and disabled feature flags. It is
ignored by Git. `.env.example` contains dummy placeholders only. Environment variables
override the root `.env`; no global Windows environment or browser storage was changed.
On a new checkout, copy `.env.example` to `.env` and fill it locally. Do not overwrite an
existing `.env` containing real credentials. Neither installation opens a Moss session.

Official references: [Moss quickstart](https://docs.moss.dev/docs/start/quickstart) and
[Python sessions](https://docs.moss.dev/docs/reference/python/sessions). The SDK session
can authenticate, obtain model artifacts and report usage even when indexing locally.
DOXA uses `auto_load_on_init=False`, scoped disposable sessions and no `push_index` call.
SDK index contents are derived and rebuildable; SQLite decides trust and access.

| Variable | Purpose / default |
| --- | --- |
| `DOXA_MOSS_ENABLED` | `false`; installation or supplied keys do not opt in. |
| `MOSS_PROJECT_ID`, `MOSS_PROJECT_KEY` | Backend credentials only; already saved locally here. |
| `DOXA_MOSS_ALLOWANCE_USD` | `0` until explicitly configured; $100 reported credit does not increase the $75 aggregate ceiling. |
| `DOXA_RUNPOD_ENABLED` | `false`. |
| `RUNPOD_API_KEY` | Backend credential value, never an agent field. |
| `RUNPOD_ENDPOINT_ID` | Existing Serverless vLLM endpoint ID; none deployed by this task. |
| `RUNPOD_MODEL_ID` | Exact deployed/served model ID; required by `profile-from-env`. |
| `RUNPOD_BASE_URL` | Optional official HTTPS override; credentials, query strings and foreign hosts rejected for RunPod. |
| `DOXA_RUNPOD_ALLOWANCE_USD` | `0` by default, no greater than the reported $25 allocation. |

## Before the first authorized RunPod call

1. Separately verify the endpoint, served model, promotional-credit terms/balance, vendor
   limits and a complete per-attempt upper bound covering GPU/compute charges. Token usage
   is not proof of total compute cost. No deployment or balance check happened here.
2. Set the backend environment variables above. Explicitly enable RunPod and choose an
   allowance within $25 and the $75 aggregate cap. Merely doing this does not call inference.
3. Pin configuration without a network call:

```powershell
.\.venv\Scripts\doxa.exe profile-from-env --version 1
.\.venv\Scripts\doxa.exe config-import .\examples\runpod-agent.json
```

4. Configure a **new** live Solo Direct run using that agent. The existing synthetic run
   cannot be reinterpreted as live. `doxa configure examples/runpod-run.json` only configures
   the run. `examples/execute-runpod-disabled.json` is an intentionally unauthorized template.
   When separately authorized, submit an execution command
   with `authorize_paid: true` and `upper_bound_usd_per_attempt` set to the verified complete
   bound. No such command was submitted during implementation.
5. Each retry gets a distinct durable reservation and operation ID. Usage includes response
   ID, reported model, exact assignment, reported tokens and latency; unknown billing stays
   null and retains the reservation. Budget rejections occur before HTTP dispatch.

The documented base is
`https://api.runpod.ai/v2/{ENDPOINT_ID}/openai/v1`; see
[RunPod's compatibility reference](https://docs.runpod.io/serverless/vllm/openai-compatibility).
Profiles bound retries, concurrency, context bytes conservatively against the token cap,
output tokens and timeout. Live tests remain outstanding; no credit balance is verified.

## Before the first authorized Moss session

This section concerns the Python retrieval adapter. The separately requested JavaScript
SDK lookup is recorded below and does not validate Python session integration.

1. Separately confirm project/key access, credit terms, SDK telemetry/data policy, and an
   upper bound covering the whole session (initialization, embeddings/query and close).
2. Enable `DOXA_MOSS_ENABLED`, set a conservative allowance, and issue a query selecting
   `backend: "moss"`, `authorize_paid: true`, a unique `idempotency_key`, and a verified
   `upper_bound_usd`. Private-memory indexing also requires `authorize_private_upload: true`.
3. The controller reserves cost, admits dispatch once, and creates a run/agent/operation
   scoped session from only currently eligible records. A failed SDK/index uses the local
   baseline, with fallback recorded. Stale returned IDs are rechecked against current
   SQLite state, so neither quarantine, revocation nor peer-private records become guidance.
4. Compare local/Moss relevance and latency only after that live test. Current mocks
   establish the privacy gate and SDK call shape; they establish no Moss performance result.

## Requested live JavaScript SDK lookup

After the offline implementation checks, Dana explicitly requested a live call using
`@moss-js/moss`: load `agent-memory-context`, query `how to sleep`, and request `topK: 3`.
The developer-only scripts `scripts/moss_lookup.mjs` and
`scripts/run_authorized_moss_lookup.py` preserve that exact lookup, adding cleanup,
a 60-second process deadline, local secret resolution and durable accounting. They do
not constitute a Node application backend, a live index mutation, or approved agent memory.

**Observed result:** the attempt exceeded 60 seconds without returning documents. The
local Node process was stopped. The record is a failed live test, not a successful
retrieval or evidence that the index exists. The output did not identify which SDK
stage stalled. No automatic second attempt was made.

Run ID: `ed769333-2b50-598d-91d2-68b62d0f028d`.
Operation ID: `dc8f9fd6-a89d-582a-9a09-633804f09387`.
The conservative $1 reservation remains held; actual billing is null/unknown, not $1
and not zero. Root `.doxa/moss-live-lookup.json` contains the sanitized outcome and the
ledger links an immutable hashed output artifact. Inspect vendor usage/reconcile the
uncertain operation before any further live test. Application feature flags stay disabled.

Moss's [pricing reference](https://docs.moss.dev/docs/pricing) distinguishes unmetered
local queries from transfer/session charges; no credit balance or invoice was verified.

## Crash accounting and cancellation

```powershell
.\.venv\Scripts\doxa.exe accounting
.\.venv\Scripts\doxa.exe cancel <run-uuid>
# After checking the vendor's actual bill, not as a way to clear a guard blindly:
.\.venv\Scripts\doxa.exe reconcile <operation-uuid> <operator-confirmed-billed-usd>
```

An in-flight/uncertain operation is never automatically resent under the same ID.
Cancellation stops the local wait where possible and records a terminal run outcome;
it does not prove that remote compute stopped or that its charge is zero. Reservations
and ambiguous dispatch survive restart. Reconciliation is operator-reported billing,
not an independently queried invoice. Already settled amounts cannot be silently changed.

## Remaining release work

Live service tests, vendor billing/credit verification, restricted generated-code sandbox,
general task adapters, full source patch/checkpoint workflows, cross-run governed retrieval,
human annotation mutation UI/API, richer memory semantic validation, multi-process worker
ownership and broad research experiments remain outstanding. Context views are not an
authentication system: this is a trusted single-user loopback operator API, not public SaaS.
All six named systems and four protocols remain in scope for the eventual release.
