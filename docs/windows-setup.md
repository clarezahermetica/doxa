# Windows setup and optional RunPod inference

For the supported terminal installation and launch, start with [README](../README.md).
These additional instructions concern optional infrastructure, not completion of the
six research algorithms or the generated-code release gate.

## Offline installation

Use Python 3.12 or newer. From PowerShell:

```powershell
Set-Location 'C:\path\to\doxa'
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
if (!(Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
.\.venv\Scripts\doxa.exe init
.\.venv\Scripts\doxa.exe config-import .\examples\council.json
.\.venv\Scripts\doxa.exe validate-config
.\.venv\Scripts\doxa.exe doctor
.\.venv\Scripts\doxa.exe configure .\examples\backend-run.json
```

Do not recreate an existing working virtual environment. Replace `-3.12` with your
installed supported Python version if needed. There is no activation requirement.
The guarded copy preserves existing credentials. No key, RunPod, Moss, Node SDK or
container runtime is needed to initialize, configure or inspect offline records.

Copy the configured run ID, then run the supported built-in finite fixture:

```powershell
.\.venv\Scripts\doxa.exe run-task <run-id> .\examples\execute-offline.json
.\.venv\Scripts\doxa.exe runs
.\.venv\Scripts\doxa.exe inspect <run-id>
.\.venv\Scripts\doxa.exe agents
.\.venv\Scripts\doxa.exe profiles
.\.venv\Scripts\doxa.exe providers
.\.venv\Scripts\doxa.exe serve
```

To open the interactive terminal instead of the optional local API:

```powershell
.\.venv\Scripts\doxa.exe
```

The terminal and CLI read the same selected workspace. Studio and the graphical desktop
are retired from this publication; Node.js and a browser are not required.

## Optional RunPod path (manual, no deployment performed)

RunPod supplies remote inference while DOXA stays local. Its official
[OpenAI compatibility documentation](https://docs.runpod.io/serverless/vllm/openai-compatibility)
specifies `https://api.runpod.ai/v2/{ENDPOINT_ID}/openai/v1`. The model ID must match
the deployed model or the worker's explicit served-name override.

1. In your RunPod account, inspect whether a suitable Serverless vLLM endpoint
   already exists. Creating/deploying a worker is a separate manual, potentially
   billable operation; this task did neither. Confirm worker limits, runtime,
   cold-start behavior, storage charges and your actual credit balance in RunPod.
2. Put the exact endpoint ID, exact served model ID and an inference-authorized
   RunPod key in your ignored root `.env`. One key can serve multiple DOXA agents:

   ```dotenv
   RUNPOD_API_KEY=replace_me
   RUNPOD_ENDPOINT_ID=replace_me
   RUNPOD_MODEL_ID=replace_me
   RUNPOD_BASE_URL=
   DOXA_RUNPOD_ENABLED=false
   DOXA_RUNPOD_ALLOWANCE_USD=0
   ```

   A base override is optional and must be the official HTTPS endpoint path.
   Endpoint ID and override must agree. Credentials, query strings, redirects,
   nonstandard ports and foreign RunPod hosts are refused. These placeholders must
   be replaced locally; do not commit `.env`.
3. When preparing a separately authorized test, set a positive local allowance
   no greater than 25 USD and enable the RunPod switch. This is an admission ceiling,
   not a verified remaining credit balance. Inspect vendor billing separately.
4. Pin a reusable model profile and assign an agent, without making a network call:

   ```powershell
   .\.venv\Scripts\doxa.exe profile-from-env --version 1
   .\.venv\Scripts\doxa.exe validate-config .\examples\runpod-agent.json
   .\.venv\Scripts\doxa.exe config-import .\examples\runpod-agent.json
   .\.venv\Scripts\doxa.exe providers
   .\.venv\Scripts\doxa.exe doctor
   .\.venv\Scripts\doxa.exe configure .\examples\runpod-run.json
   ```

   Profiles and agents are immutable versions. If version 1 exists with different
   content, choose a new profile version and update the agent's pinned version;
   increment the agent version too. The example expects profile `runpod-profile`
   version 1 and agent version 2. Runs snapshot those assignments and instructions.
   Disabling the provider switch prevents calls even from older enabled profiles.
5. The supplied `execute-runpod-disabled.json` has `authorize_paid:false` and no
   bound. Keep it that way. For the first explicitly authorized invocation, create
   a separate ignored file such as `.doxa/authorized-runpod-call.json` containing
   `authorize_paid:true` and an operator-established **complete per-attempt cost
   upper bound**. Then invoke `run-task` with the configured run ID and that file.
   This is a separately authorized action, not part of installation or these checks.

A live call requires all of: enabled profile, provider switch, valid identifiers
and key, agent remote-inference permission, explicit per-command authorization,
admissible request limits, a complete cost bound and successful durable reservation.
Readiness is local-only: `ready_for_authorized_test` never means a model was tested.

## Profile limits, pricing and supported features

Model profiles hold exact model/endpoint/credential-reference metadata, declared
capabilities, temperature, input byte limit, context/output limits, timeout, retries,
concurrency and optional versioned pricing/source. Use JSON configuration to adjust
these fields. Defaults: 4096 input bytes, 4096 context tokens, 256 output tokens,
30-second request timeout, zero retries and one concurrent call. The byte admission
guard is not an exact tokenizer; server-side context validation remains authoritative.

Only nonstreaming text chat is implemented for RunPod and explicitly configured
HTTPS OpenAI-compatible profiles. Task prompts request JSON and the task validates
the response; native schema-constrained output, model tool calling, streaming and
seed controls are not implemented. Declaring those unsupported capabilities makes
the profile not ready and fails before dispatch. OpenAI, Gemini and Claude have
visible unimplemented registry slots, not working adapters.

Optional generic compatible profiles require an explicit HTTPS base URL and a
credential environment reference (for example `OPENAI_COMPATIBLE_API_KEY`). Their
independent controls are `DOXA_OPENAI_COMPATIBLE_ENABLED=false` and
`DOXA_OPENAI_COMPATIBLE_ALLOWANCE_USD=0` by default. There is no implicit provider
fallback, endpoint discovery or credential transfer to another provider.

Pricing is null unless explicitly supplied with source and version. A configured
complete-operation bound can replace a per-command bound; the larger wins if both
are given. Generic token-price reservations use configured maximum input/output
capacities, rounded upward to micro-USD. RunPod token prices alone cannot establish
GPU/runtime/storage costs: it requires a complete-operation bound. No price, balance,
model choice or endpoint identifier is invented. Existing 75 USD aggregate and
per-run ceilings remain enforced; RunPod has an additional maximum 25 USD allocation.

## Errors, interruptions and accounting

Provider response/error records and operation outcome/known settlement commit in
one SQLite transaction. Calls preserve request/response IDs, model assignments,
request fingerprint/settings, reported usage and sanitized errors. Unreported bills
and tokens remain null. A reservation is a hold, not a measured charge.

Only failures demonstrably before sending (connection establishment errors) can
automatically retry, bounded by both profile and run limits; each attempt reserves
separately. HTTP failures, invalid responses, read timeouts and cancellation may
have unknown billing: retain their reservation and stop automatic retries. Any
uncertain operation blocks further service dispatch even if concurrency is raised.
Local cancellation cannot guarantee remote job cancellation or prevent idle costs.

If a process stopped during a run:

```powershell
.\.venv\Scripts\doxa.exe inspect <run-id>
.\.venv\Scripts\doxa.exe cancel <run-id>
.\.venv\Scripts\doxa.exe recover <run-id>
.\.venv\Scripts\doxa.exe accounting
```

Recovery requires a terminal run. It atomically records prepared calls as failed and
in-flight calls as uncertain, keeping all holds; it does not resend anything. Once
you have vendor evidence of the actual bill, `reconcile <operation-id> <billed-usd>`
records an immutable **operator-reported** charge with separate provenance. Do not
enter zero merely because a call failed. API shutdown cancels local tasks and
persists cancellation; crash recovery remains explicit. Infrastructure/model errors
produce failed runs; an ordinary failing task test remains an inspectable completed
attempt with failed task outcome.

## Generated-code execution remains disabled

This machine has no Docker/Podman executable and WSL reports it is not installed.
Missing prerequisites: WSL2/Linux-container support (or equivalent isolation), a
running container engine, an implemented runner, and acceptance tests proving
no network, no inherited secrets, restricted filesystem/commands, protected tests,
CPU/memory/PID/time/write-space quotas, stdout/stderr capture and cleanup. None was
installed automatically. A container engine alone does not pass that gate.

The concrete `CacheTaskAdapter` implements initialize/observe/validate/act/snapshot/
verified restore/terminate over prewritten finite actions. It produces typed evidence
and checkpoints for controller commits and owns no separate ledger. Its verifier
uses the fixed versioned oracle. Neither adapter is a shell or a generated-code
sandbox. `DisabledSandbox` remains the selected execution boundary and fails closed.

## Reproduce checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe scripts/export_contracts.py
npm.cmd --prefix studio run types:generate
npm.cmd --prefix studio run build
.\.venv\Scripts\python.exe scripts/check_publish.py
```

Schemas/types are committed; CI checks regeneration drift. Tests use mocked HTTP
or local storage and perform no paid inference. Root `.doxa`, `.env`, local caches,
private exports and credentials remain ignored. Keep one canonical ledger for
aggregate accounting; isolated test databases are temporary fixtures, not services.
