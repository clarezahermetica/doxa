# Account CLI providers

One authorized Codex 0.160.0 / requested gpt-6.1-sol low-effort smoke passed on
2026-11-04; see [status](status.md). This is not provider-wide compatibility certification.
Codex CLI is the first executable account-session adapter. Claude Code, Gemini CLI
and GitHub Copilot CLI are recognized identities with honest absent/unsupported states;
they have no reviewed executable adapter in this version. No CLI is installed or logged
in automatically. Existing API-key and local-server profiles keep their HTTP transport.

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
shortcut in this pass. Restored/copy workspaces are not a shared account-wide budget service.

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
- Only text research is supported. No native tools, streaming viewer, automatic continuation,
  remote history access, arbitrary CLI commands or custom executable/argument forms.
- Adapters implement the existing ModelProvider request/response/cancel boundary and are
  registered in trusted Python code. Additional account CLIs require reviewed safe flags,
  output parsing and fake-executable coverage before executable registration. Council and
  the six research systems do not need a new orchestration engine.
- Existing installed applications are unchanged by source edits. Packaging checks do not
  constitute an installed upgrade, signing, clean-machine acceptance or live model acceptance.

Official references: [noninteractive Codex](https://developers.openai.com/codex/noninteractive),
[CLI flags](https://developers.openai.com/codex/cli/reference), and
[configuration controls](https://developers.openai.com/codex/config-reference).

Do not generalize the observed one-call acceptance to untested model/runtime combinations.


## 2026-11-04 startup repair and acceptance boundary

Codex 0.160.0 rejects overrides under `model_providers.openai`: `openai` is a reserved
built-in provider ID. Removed those invalid retry overrides without changing authentication
or substituting an API provider. An isolated real-CLI diagnostic with an empty session home
and a loopback-only error fixture reproduced rejection before any request, then reached
exactly one local fixture request after correction. This verifies startup, not live inference.

Profiles can now explicitly request an allowlisted reasoning effort (`low`, `medium`,
`high`, `xhigh`, `max`). Support remains model-dependent. Omitting it retains an unverified
CLI default. Requested settings are not evidence of server-selected settings.

New invocation diagnostics include CLI version, process ID when spawned, exit code when
observed, execution stage, and sanitized failure code. Failed responses are incomplete.
A recognized local configuration rejection is classified before-request; unknown failures
retain billing uncertainty. Historical failed records and their holds are not rewritten.
The prior failed smoke run remains uncertain pending evidence-based reconciliation.

The offline repair made no live model request. A subsequent separately authorized
one-call smoke completed and persisted a source-linked claim; see [status](status.md).
Future live tests still require separate approval and acknowledgment of CLI-managed
transport retries and unknown subscription usage.

## Corrected CLI context and progress path (source v21-dev)

The context planner and Codex request validator share DOXA's exact UTF-8 prompt wrapper,
JSON escaping and response-schema byte count. Output and remaining experiment/agent limits
are reserved before dispatch. This is conservative admission, not model-specific tokenization
or measurement of the CLI/provider's hidden prompt. Full-cycle stress is offline and bounded;
it cannot guarantee arbitrary future outputs will fit.

Safe process/session/turn/output-available/finish milestones may be committed while a real
CLI process runs. Raw reasoning item bodies and terminal streams are not displayed as chain
of thought. Final research output still undergoes ordinary structured validation. The new
streaming path has offline process-fixture coverage, not another live Codex certification.
The existing uncertain quota holds remain intact; native CLI retries and unknown subscription
usage are not converted into a fictitious hard dollar bound. No API-key fallback was added.

## v22-dev: native research choices and explanatory prose

The native output schema now derives `respond.response`, `assess.stance` and
`adjudicate.outcome` from the corresponding controller contract schemas. This fixes the
v21 live failure in which a prose paragraph was permitted by the native schema but rejected
by the controller's response enum. Closed choice fields and controller validation remain
strict; there is no prose-to-decision guessing, permissive fallback, or automatic retry.

Natural-language explanations remain accepted in `reason`. For example, use
`response: "qualify"` with the full explanation in `reason`. A prose-only proposal with no
valid disposition stays preserved in its original model-response artifact and uncommitted;
it is not converted into an accepted response or historical claim revision. A future
unclassified commentary operation would need explicit semantics and attribution rather
than being silently treated as acceptance.

The regression uses the failed output's reduced shape and checks all three native enums
against the authoritative contracts. Schema overhead is still counted by the shared context
planner. Source v22-dev requires a fresh source process; the installed v17 is unchanged.
This correction has no SQL migration or historical rewrite and does not authorize another
live/subscription call. Full-cycle rehearsal is synthetic and separately labeled.

Verification: 475 full-suite tests passed (one pre-existing Starlette warning), Ruff and
strict mypy for Windows/Linux passed. All seven acceptance configurations passed isolated
full-cycle rehearsal with zero live calls. Their events, records, configuration versions,
quota operations and reservations have the same pre/post logical fingerprint. Record/API
schemas regenerate unchanged. Native online enforcement of the corrected schema still
requires a separately approved acceptance call; no such call was made for this correction.
