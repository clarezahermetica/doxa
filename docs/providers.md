# Models and providers

## Supported connections

This describes the current source implementation. A transport implementation and mocked
contract test do not verify an account, credits, endpoint, exact model or provider-wide support.
Provider registration and mocked tests do not perform live acceptance.

| Connection | Implemented pathway | Verification / limitations |
| --- | --- | --- |
| OpenAI native | Explicit official-origin Chat Completions or Responses | Mock HTTP serialization, blocks, usage, finish/errors and cancellation. Exact live model/settings unverified. Temperature omitted; reasoning must be explicitly declared/configured. |
| Anthropic native | Official-origin Messages with its key/version headers | Mock text/thinking/tool blocks, stop reason, usage and thinking configuration. Exact live compatibility unverified. |
| Gemini native | Official generateContent contents/parts/system instruction | Mock generation/thinking settings, usage, stop/block state. Exact live compatibility unverified. |
| Arbitrary OpenAI-compatible server | Explicit URL, served model ID, authentication reference and compatible Chat format | Mock contract coverage. Exact server compatibility unverified. Supports explicit unbilled loopback configuration; no paid API key is required for a local no-auth server. |
| RunPod | Existing vLLM OpenAI-style endpoint | Uses the tested compatible wire boundary and official endpoint validation. Not Serverless Jobs, deployment, weight provisioning or an observed live test. |
| OpenRouter / Together / Fireworks / Groq | Compatible endpoint presets | No additional native adapter or service-wide certification. The chosen endpoint/model must accept the configured request format. |
| Ollama / vLLM / LM Studio / SGLang | Explicit OpenAI-compatible server configuration | Native Ollama protocol and model loading are not implemented. No model server/weights are downloaded or launched automatically. |
| Cohere / Bedrock / Vertex / Azure native / other unsupported catalog protocols | Descriptive registration only unless a separately installed trusted adapter exists | A catalog entry does not make an executable adapter or compatible model assignment. |
| Moss | Optional research/memory retrieval service, not a language model | Mocked eligibility/cache boundaries. Live retrieval and remote synchronization remain unverified. |
| Codex CLI account session | Native executable, existing ChatGPT login, tool-disabled text request | Offline subprocess/controller/TUI coverage, a November 4 smoke and November 5 v22 multi-agent/control acceptance. Requested model/effort were recorded; resolved settings and quota/USD cost remain unknown. See [status](status.md) for scope and [setup](#configure-codex-in-the-terminal) for authorization. |
| Claude Code / Gemini CLI / GitHub Copilot CLI | Detection and unsupported-state diagnostics only | No reviewed executable adapters; not usable for inference through these identities yet. |

Model IDs are open-ended; there is no model-family whitelist. Compatibility depends on declared
capabilities, the adapter and the exact request. Native function requests are preserved at the
wire boundary, but automatic native tool-result conversations are unavailable. Prompted web tools
remain separately permission/authorization gated. Streaming, multimodal inference, embeddings,
GGUF execution and unrestricted generated code remain unavailable. Activity milestones
are distinct from a token-stream viewer.

No automatic substitution, fixture fallback or replay is allowed for an uncertain paid call.
Unknown usage/charges remain unknown. See [live connection testing](#test-an-httpapi-connection)
for the named-provider/model/spend approval required before a real probe.

## Wire-level verification

The HTTP combinations below have **mock verification only**; Codex CLI live observations are reported separately in [status](status.md). Arbitrary saved
profiles remain configured/unverified; catalog-only protocols remain registration only.
No credential, exact model, hosted deployment or billing integration was certified.

| Adapter | Authentication and request | Output and operational limits |
| --- | --- | --- |
| Native OpenAI Chat | Fixed official HTTPS origin, Bearer reference, `store=false`, `max_completion_tokens`; temperature omitted | Chat text/usage/tool-request parsing. Model-specific reasoning parameter support is not inferred. |
| Native OpenAI Responses | Explicit `/responses`, Bearer reference, `max_output_tokens`, declared reasoning and optional schema | Preserved text/refusal/function blocks and usage. Incomplete status blocks completion; no automatic continuation. |
| Native Anthropic Messages | Fixed official HTTPS origin, `x-api-key`, version header, system separate from messages, `max_tokens`; declared thinking | `max_tokens`, `pause_turn`, and `model_context_window_exceeded` remain incomplete. Tool requests are retained; no automatic tool-result loop. |
| Native Gemini generateContent | Fixed official HTTPS origin, `x-goog-api-key`, contents/parts/systemInstruction, explicit generation/thinking controls | `MAX_TOKENS` and `CONTINUATION` remain incomplete. Candidate blocking/refusal and unknown usage remain distinct. |
| Compatible/loopback/RunPod vLLM | Chat-style explicit endpoint/model/authentication; local no-auth requires loopback; remote requests retain spending/disclosure gates | Compatibility belongs to the exact server/model/settings. Not native Ollama, RunPod Jobs, model provisioning or weight execution. |

The transport bounds response bytes, disables environment proxy inheritance and redirects,
and uses the smaller request/profile timeout. Cancellation cancels the local wait; it cannot
establish remote termination or a final bill. Error text suppresses raw responses. Dispatch
and reservations precede remote work; ambiguous outcomes retain holds. Native tool requests
cannot silently become completed research claims. Prompts and declared context limits do
not establish actual context-window or structured-output compatibility for an unknown model.

Protocol references consulted during implementation:

- [OpenAI Chat request contract](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).
- [OpenAI Responses request contract](https://developers.openai.com/api/reference/cli/resources/responses/methods/create).
- [Anthropic stop reasons](https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons).
- [Gemini generateContent contract](https://ai.google.dev/api/generate-content).
- [RunPod vLLM compatibility](https://docs.runpod.io/serverless/vllm/openai-compatibility).

These documents explain protocol semantics; they are not evidence of a successful DOXA
live call. Run the separately authorized acceptance procedure before promoting any exact
adapter/model/settings combination to live verified. These mocked checks do not establish
any live-verified combination; the live gate requires separate authorization.



## Codex account session

Codex is the implemented account-session adapter. Claude Code, Gemini CLI and Copilot CLI
have detection/unsupported states only. Install and authenticate Codex separately.

## Configure Codex in the terminal

1. Install Codex separately and sign in yourself with `codex login` if necessary.
   DOXA requires a native executable on an absolute PATH entry. Windows shell shims
   (`.cmd`, `.bat`, `.ps1`) are detected but never executed. API-key login is not accepted
   as a ChatGPT account session for this adapter.
2. Run `doxa`, open Models, and add a model. Enter the served model identifier, or
   `cli-default` to leave model selection to the installed CLI. This does not discover
   or verify which model the account will select.
3. In Connection setup, select **Local account CLIs / Codex CLI**. Use **Check installed
   CLIs** to run bounded local version/help/feature/login-status probes. These do not
   request inference. A missing or unrecognized authentication status blocks launch;
   follow the displayed manual login command outside DOXA.
4. Choose text generation and prompted structured output, or native structured output
   if the installed CLI advertises `--output-schema`. Set a short timeout and small
   input/context/output bounds. Concurrency is one and DOXA retries are zero. Codex
   manages its own transport retries; this adapter cannot pin those to zero. No API key,
   endpoint, pricing, or positive dollar allowance is required. Enable and save.
   Saving itself invokes neither a probe nor inference.
5. Assign this versioned profile to an agent template and create a live research-debate
   experiment with that participant. Import only the evidence you authorize disclosing.
   Native tools, web access and agent tool permissions must remain disabled for this path.
6. Inspect the launch preflight. A real launch requires both **external disclosure** and
   **subscription quota** acknowledgment. These are separate from paid-API authorization.
   Do not launch merely to test whether a login works.

Safe diagnostics are also available through `doxa model-clis` or `doxa model-clis --json`.
Readiness is process-local: a new shell command can explicitly refresh it with
`doxa run preflight RUN_ID --check-clis --json`. Without that flag, preflight only
inspects cached readiness and can report the session unverified. Saving never probes.
An executable/version/authentication result is local readiness, not successful model
compatibility. The traditional `doxa run start` accepts `--authorize-quota` together with
`--authorize-external`; the normal live preflight and run limits still apply.

## Execution boundary

`cli_session` and `cli_session` authentication are explicit profile fields. Executables,
arguments and config overrides are trusted adapter code, never profile-supplied command
strings. DOXA uses `asyncio.create_subprocess_exec` without a shell. Every probe and every
model invocation has a fresh temporary working directory. The model working directory
is empty; prompts go through stdin, with bounded sibling schema/final-output files.

The environment allowlist retains home/config directory references needed by the CLI's
own session management. DOXA does not open, parse, export or copy CLI authentication files.
API keys, DOXA secrets, injected Node/Python settings and parent session identifiers are
not inherited. The independently installed CLI remains a trusted local program.

The Codex invocation is ephemeral, read-only and noninteractive, ignores user instructions
and user config, disables web search, MCP, apps/plugins, skills, hooks, memories, shell,
image/browser/computer tools and subagents through installed-version controls.
Unbounded connection retries are disabled; built-in transport retries remain CLI-managed. Required controls missing from an installed version fail closed. Unexpected
tool events cannot become completed claims. A small native syntax schema is supported
when advertised, but controller citation/action validation remains authoritative.

Input bytes, stdout/stderr, event count, final response and wall time are bounded.
Cancellation and timeout terminate the local process, wait briefly, then force-kill if
necessary; pipes are drained without retention and closed. Raw stderr and authentication
output are never persisted. Errors use sanitized categories and fixed diagnostic codes.
DOXA never retries an ambiguous invocation. This does not guarantee zero internal CLI
HTTP or stream reconnection attempts.

## Accounting and recovery

Before dispatch, the same ledger transaction records the started ModelCall and one
`quota_operations` admission. It enforces run call limits and a global-per-adapter hold
across profiles in that workspace. Each call records `accounting_basis=subscription_quota`.
Tokens are preserved when reported; quota consumption and USD billing remain **null**.
An account subscription is not represented as free inference or a zero-dollar reservation.

Observed completion/failure and quota-operation transition are committed atomically.
An interrupted or ambiguous request retains an `uncertain` hold; startup recovery never
replays it or releases the hold automatically. Another CLI call through that adapter is
blocked pending evidence-based reconciliation. There is no new automatic/manual settlement
shortcut in this version. Restored/copy workspaces are not a shared account-wide budget service.

The additive `0004` migration (`0004_quota.py`) leaves prior records and USD reservations intact.
Backups include the new table. Older executables are not guaranteed to accept newer
schema/record fields; preserve a verified backup before deliberately upgrading a workspace.

## Limits and extension

- The CLI has no documented per-request generation-token ceiling used by this adapter.
  DOXA enforces admission and conservatively bounds accepted final UTF-8 bytes by the
  configured output-token count; this is **not** a hard server-side reasoning/quota cap.
  Output beyond the bound is rejected while observed usage is retained.
- Process termination cannot prove remote work stopped or establish a final bill. Hard
  parent-process termination may leave a child; uncertainty remains until investigated.
- `cli-default` is an explicit default-model sentinel. The selected/reported model is
  recorded only if supplied by CLI events; DOXA does not invent an exact model identity.
  Sampling uses CLI defaults, not an asserted temperature setting.
- Only text research is supported. No native tools, token-stream viewer, automatic continuation,
  remote history access, arbitrary CLI commands or custom executable/argument forms.
- Adapters implement the existing ModelProvider request/response/cancel boundary and are
  registered in trusted Python code. Additional account CLIs require reviewed safe flags,
  output parsing and fake-executable coverage before executable registration. Council and
  the six research systems do not need a new orchestration engine.
- Source edits do not upgrade an installed executable. Use `doxa --version` and
  `doxa runtime-info --json` to inspect the selected runtime. Packaging checks do not
  establish signing, clean-machine acceptance or live model compatibility.

Official references: [noninteractive Codex](https://developers.openai.com/codex/noninteractive),
[CLI flags](https://developers.openai.com/codex/cli/reference), and
[configuration controls](https://developers.openai.com/codex/config-reference).

Do not generalize the recorded Codex acceptance runs to untested model/runtime combinations.

## Context and progress

The context planner and CLI validator share the serialized prompt wrapper, JSON escaping
and response-schema byte count. Input/output admission is conservative; it does not measure
the provider's hidden prompt or exact tokenizer. Full-cycle stress tests are offline.
Requested reasoning effort is optional and model-dependent; it is not a verified effective
setting. Native response, stance and outcome choices derive from controller contracts;
explanations belong in `reason`. Invalid proposals remain in their original response artifact
and are not silently converted into accepted decisions.

Activity records process/session/turn/output-available/finish milestones while a CLI runs.
These are progress events, not token streaming or private reasoning. Final research records
still require controller validation.


## Test an HTTP/API connection

Name the provider, exact model and maximum spend before a live test. Saving a profile or
passing mocked checks does not verify a connection. For an account CLI, use the separate
subscription-quota and disclosure acknowledgments described above; do not invent a dollar
reservation. Never retry an uncertain operation or release its hold automatically.

1. Open the intended workspace with `doxa`. Avoid simultaneous synchronized writers;
   keep a verified backup outside any synchronization root. Do not move history implicitly.
2. Choose **Choose model and connection**. Select native OpenAI Responses, native OpenAI Chat,
   Anthropic Messages, Gemini generateContent, or an explicitly compatible endpoint. Enter the
   exact served model ID. Preserve existing credential references; saving never replaces keys.
3. Declare only known text/JSON capabilities. Configure a small output limit, sufficient input
   bytes/context, a timeout, concurrency 1 and no retries. Thinking controls require explicit
   model support. Temperature omission is available; native OpenAI always omits temperature.
   Leave network research tools disabled. No model-list request is necessary.
4. Set provider allowance and experiment run ceiling within the separately approved spend.
   A reservation ceiling is conservative local admission, not a vendor billing guarantee.
   Configure one participant and one round for the first probe; import a short local source.
   Use ordinary structured claims, not the three-round staged protocol for this first probe.
5. Open **Inspect launch preflight**. Inspect the exact profile/version/model, connection,
   permissions, call bounds and spending ceiling. Eligibility is not verified inference.
6. Only with the separate named authorization, open **Start selected run**, approve disclosure
   and paid inference, and enter the complete per-attempt upper bound. The configured run
   ceiling must not exceed the approved maximum. Keep planned calls, retries and tools within
   that amount; unknown bills retain their reservation.
7. Inspect activity, actual response/model IDs, output/finish state, usage and accounting.
   An incomplete/refused/tool-only response must not become a completed research claim.
   A timeout remains uncertain and must not be replayed. Local cancellation does not prove
   remote termination or a zero bill.
8. Export to a new `.zip` for history, configurations and verified referenced artifacts.
   Record the provider/model, timestamp, observed result and bill uncertainty. Only this
   observed result qualifies as a live-provider test.


## Test a research cycle

After a separately approved connection test, create a new experiment, import its evidence,
and choose Investigation, structured actions and sequential scheduling. Use at least one
Researcher/Executor, Skeptic and Archivist and budget for a complete exchange. Follow the
[investigation procedure](workbench.md#investigations-and-outcomes), including the optional
dispute-review criterion. Rehearse the exact pinned configuration with full-cycle offline
stress before authorizing live execution. A previous test proposal is not authorization.

**Create another run attempt** reuses immutable configuration without replaying old calls;
import evidence into the new attempt. A changed criticism strategy is a separately versioned
condition. Compare source hashes, settings, effort, calls and retrieved passages before
describing conditions as matched. Model judgments and agreement do not establish correctness.

CLI inspection commands include `doxa run preflight RUN --json`, `doxa run watch RUN`,
`doxa run cancel RUN`, `doxa run new-attempt RUN` and `doxa export RUN results.zip`.
Live-start authorization remains an explicit operator decision for that attempt.
