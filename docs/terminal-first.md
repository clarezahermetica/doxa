# Terminal-first DOXA — October 25, 2026

Historical implementation checkpoint: GUI development was frozen at this stage and
was later retired from the published tree. Workspace selection was subsequently corrected
in Pass 1; the current default does not search ancestor project directories. Use
[README](../README.md) for current terminal installation and [storage map](storage-map.md)
for current workspace paths. The README and launchers described below are historical.

## Product boundary and audit

The existing Textual ResearchConsole is now the primary interactive client. Studio and
pywebview sources and v1/v2/v3 desktop builds are preserved experimental artifacts;
active graphical development is frozen. The only Studio edit in this pass is mechanical
API type regeneration; its build checks compatibility with the shared contracts.
README remains intentionally empty.

The audit found a short viewer with setup/review modals, a fixed provider enum, no local
unauthenticated inference path, and differing workspace defaults. The correction extends
that same app and controller; it does not create another terminal or research engine.

## Launch and workspace selection

```powershell
.\.venv\Scripts\doxa.exe
.\.venv\Scripts\doxa.exe console --data-dir .\.doxa
.\Open DOXA Terminal.cmd
```

The source and terminal binary resolve an explicit DOXA_DATA_DIR first, then the last
selected workspace, then an existing ancestor project's .doxa. First-run fallback opens
a workspace selector instead of silently initializing a new history. A missing remembered
workspace is not silently recreated by ordinary CLI initialization. W opens the selector;
creation requires an explicit checkbox and an empty destination. Existing histories never
merge. The last workspace path is an operational preference in LocalAppData/DOXA/client.json,
not a second research ledger. Explicit --data-dir remains available for automation.
The selected canonical directory is always visible in the status area.

The project workspace resolves its existing parent .env in place. Original Moss project
credentials were found in the root .env and remain untouched; no key was replaced or
rotated. A workspace-specific .env or explicit DOXA_ENV_FILE can select another existing
credential file. New credentials entered in the terminal are masked and protected using
Windows current-user DPAPI under the workspace's ignored credentials directory. Existing
credential blobs are never overwritten by model registration. Values never enter model
profiles, prompts or ledger records. Profile authentication stores a reference only.

## Workspace operation

The experiment list occupies five rows; the selected experiment and live activity are the
main working area. There is no logo, splash page or introductory dashboard. Activity is a
bounded recent-event window rebuilt from persisted history after selection/reconnection.
Ledger reads run outside the Textual event loop; UI and worker lifetime are independent.
Inspect offers filtered claims, criticism, source text, exact context messages, Council
instances/templates, model profiles, memory, evaluations and checkpoints. A side inspector
shows readable detail; Ctrl+J opens the exact selected record. Rendering is bounded to
1,000 matching rows and 500 recent activity events; exports preserve the entire history.

Tab/Shift+Tab move focus; Enter selects table rows. Ctrl+P searches actual commands.
F1 explains controls. N creates experiments, A creates/versions agent templates, M
registers/versions model profiles, I imports evidence, S opens launch authorization,
X cancels active runs, C opens branch review, W switches workspaces, E exports, Q quits
only the viewer. Compare, Memory and Connection commands are also in the palette.
Selecting an agent template/model in Inspect before A/M edits a new immutable version.
An experiment's pinned instances remain distinct from its reusable templates.

Experiment setup configures collaborative/adversarial/solo protocols, repeated template
counts, sequential or round-parallel scheduling, rounds, concurrency, call limits,
synthetic/model-backed execution and optional structured research actions. Agent forms
configure model assignment, instructions, enabled state, web-tool permissions and memory
scope. Generated code execution remains disabled. Imports retain originals and parser
provenance. Starting a worker does not imply a successful run; persisted states and errors
remain authoritative. The detached worker survives closing the viewer.

Review can propose/revise claims with selected source links, submit criticism, respond
with an optional revised proposition, record human adjudication/annotations, evaluate,
checkpoint and fork. Comparisons use the existing branch-comparison controller projection.
Memory querying applies the existing eligibility/visibility checks. Export uses a shared
core operation and never overwrites an existing destination. Low-level CLI commands and
JSON exports remain available; common list/inspect/compare commands provide --json.

## Models, connections and extensions

Model identity is an arbitrary string, independent of the runtime adapter and agent role.
ModelProfile.provider can name a custom connection; adapter selects a compatible wire
implementation. The previous native integrations remain, and openai_compatible accepts
explicit hosted HTTPS endpoints or explicitly unbilled local loopback endpoints. No model
family whitelist exists. Local inference can use authentication=none and requires no paid
API credential or fictitious monetary reservation. Local dispatch admission is atomic in
the same SQLite ledger, bounds calls/concurrency and blocks replay/interrupted dispatch.
A loopback gateway that bills remote inference must not be declared an unbilled runtime.

Remote inference retains provider switches, persistent allowances, per-attempt bounds,
aggregate/run ceilings, explicit disclosure authorization and paid authorization. The
terminal can configure a runtime allowance without editing .env; operational controls
are stored in ignored runtime-settings.json. Setting a profile/allowance dispatches nothing.

Model setup includes endpoint, auth reference, masked credential entry, temperature,
context/output limits, timeout, concurrency, enabled state and explicit text/structured
capabilities. Unknown declared capabilities remain unknown. Requested protocol capabilities
and structured research assignments reject incompatible or unknown declarations. Broader
images/embeddings are not implemented by the current text adapters. Streaming and native
tool-call schemas remain unavailable. Structured research uses validated prompted JSON;
that is distinct from provider-native function calling.

The Connection palette command explicitly authorizes a bounded GET /models. It never
sends a generation request. Missing discovery is an unavailable feature, not proof of an
incompatible model. A reachable model listing leaves generation and capabilities unverified.
No real endpoint discovery or live inference was performed as development acceptance.

Trusted Python extensions register AdapterRegistration through register_adapter. The
registration supplies a factory implementing ModelProvider, a profile validator, declared
capabilities, enable-switch reference and allowance reference. Profiles do not import code.
Council orchestration and research systems do not change when registering another adapter.
See providers/contracts.py and providers/registry.py. Extensions must sanitize provider
responses/errors and preserve DOXA's guarded dispatch; they cannot replace its ledger.

Ollama and llama.cpp can be connected through their compatible server interfaces; installing,
starting, downloading or tuning those runtimes is not performed automatically. Repository
identifiers can be registered without downloads. Existing GGUF files can be registered as
path/size/hash/version metadata; no tensor deserialization or model-code execution occurs.
Header recognition is not full weight validation and does not establish hardware fitness
or prove that an endpoint serves those exact weights. Actual GGUF loading remains the
external runtime's job. PyTorch pickle imports and arbitrary repository code are unsupported.

LiteLLM was evaluated as optional interoperability. Its compatible proxy can be an explicit
endpoint today; a direct LiteLLM SDK adapter was not added. Its retries, fallbacks and cost
estimates must not bypass DOXA's admissions or silently change model identity. A large
external gateway is not required.

Primary references inspected:
- https://github.com/ollama/ollama/blob/main/docs/api/introduction.mdx
- https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- https://docs.litellm.ai/docs/
- https://docs.litellm.ai/docs/proxy/cost_tracking

## Structured research and evaluation boundaries

Optional structured_actions requests validated claim, challenge, response and Archivist
adjudication objects from model turns. The runtime owns the actor identity, phase and
idempotency. Generated source links must refer to sources actually supplied in that turn's
context manifest. Challenges/responses/revisions use the existing deterministic validators.
Claim authorship and append-only ancestry remain checked. Model adjudication has
llm_evaluator provenance and no independent verification; human review retains separate
human_annotation provenance. Synthetic action fixtures retain imported_source provenance.
No model consensus is promoted to objective truth.

Evaluation now includes evidence-linked claim and challenge-response rates with explicit
denominators; objective correctness and citation entailment remain null. Source references
and links do not prove that a source supports a proposition. Long documents use deterministic
ranked excerpts from the reusable local FTS index while full originals remain canonical.
The exact supplied excerpt is preserved in each context artifact.

## Distribution and acceptance

Build the separate one-folder console distribution with scripts/build_terminal.ps1.
It needs no Vite, React assets, WebView2 or installed end-user Python. Workspaces, credentials
and experimental artifacts live outside the application folder. Existing desktop builds
are not deleted or rebuilt. The terminal-only binary explicitly reports that graphical
commands require the separate archived graphical client.

Acceptance tests use temporary workspaces, mocked transports and explicit synthetic output.
They cover arbitrary model IDs/custom compatible connections without credentials, multiple
same-role instances, structured criticism/response/revision/model adjudication, DPAPI
round-trip/nonreplacement, original Moss-file resolution, narrow terminal inspection/resize,
and configuration-through-export entirely through Textual interaction. A full synthetic
terminal run is not evidence of successful external model inference.

Live providers, real Ollama/llama.cpp hardware execution, direct LiteLLM SDK integration,
non-text modalities, exact weight-to-endpoint attestation, Windows Terminal GUI/manual
usability and clean-machine distribution remain unverified or unsupported as described.
PowerShell PTY and Textual headless interaction are distinct from a manual Windows Terminal
acceptance session. Do not claim one substitutes for the other.

To reproduce the recorded Windows Python 3.14.7 build environment in a separate virtualenv:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-terminal.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\scripts\build_terminal.ps1
```

The lock pins the recorded development/build dependencies; it excludes the graphical shell.
Run this in a separate build checkout/environment if preserving an existing virtualenv.
