# Pass 3 — Model-backed research execution

November 1, 2026. Final source: **308 tests pass**, Ruff passes, strict mypy passes
(89 source files), generated schemas/types and Studio compatibility build pass.
The only warning is the pre-existing Starlette/httpx deprecation warning.
No live inference, local model server, Moss or RunPod request was performed. Provider
tests use fake HTTP transports; official documentation research was read-only.

## Architecture and changed files

One controller, canonical SQLite ledger, immutable configuration history and existing detached
worker remain authoritative. No SQL migration, new research database, orchestration framework,
GUI feature or generated-code execution was introduced. Shared contracts gain backward-readable
defaulted fields; original stored rows are not rewritten. README remains empty.

| Files | Responsibility |
| --- | --- |
| providers/contracts.py; core/models.py; profiles.py | Pinned request identity, protocol/settings, structured blocks/tool requests/finish state, artifact references, criticism details, context omissions, evaluation parameters and launch authorization. |
| providers/wire.py; runpod.py; registry.py | Native Responses/Chat, hardened Messages, native Gemini and compatible serialization; bounded response reads, parameter validation, normalized observations and sanitized errors. |
| core/workbench.py; execution.py | Staged rounds, stable parallel scientific commits, profile/context references, incomplete-output handling, recorded authorization and captured allowance bounds. Existing worker/cancellation/recovery machinery retained. |
| core/text_research.py; comparison.py; attempts.py | Evidence-linked objections, own-author generated revisions, citation character spans, descriptive measurements, historical snapshot compatibility, text-restore comparison and immutable paired/condition attempts. |
| core/preflight.py; exports.py | Read-only planning/authorization; ZIP exports with pinned configurations, recursively verified artifacts and hash manifest. Existing JSON exports retained. |
| cli/console.py; operations.py; research_tools.py; reference.py; workbench.py | Preflight/new-attempt actions, shared controller operations, explicit launch gates, search/help and CLI equivalents. |
| cli/screens.py; model_setup.py; model_catalog.py; inspectors.py | Staged-cycle option, Responses/Gemini connections, input-byte/reasoning/temperature controls, JSON/ZIP guidance. Extends the existing Textual app. |
| tests/test_pass3_providers.py; test_pass3_execution.py; test_pass3_acceptance.py | Native wire/error/cancel tests, full multi-agent workflow, ordering, preflight, uncertain-call accounting, terminal actions and export checks. |
| tests/test_backend_completion.py; test_pass27_models.py | Expected provider inventory includes Gemini; still-unsupported Cohere replaces Gemini in registration-only coverage. |
| docs/contracts/*; studio/src/api.generated.ts | Generated compatibility updates only; graphical source/features remain frozen. |
| scripts/build_terminal.ps1 | Separately versioned output; refuse overwriting existing builds/archives. |

The pre-edit capability matrix is [pass3-implementation-matrix.md](pass3-implementation-matrix.md).

## Provider and model capabilities

| Transport | Implemented and mock-tested | Limits / live status |
| --- | --- | --- |
| OpenAI native | Official Chat retained; explicitly selected Responses, ordered input, store=false, bounded output, reasoning settings, output items, usage and finish state | Exact model acceptance unverified; temperature omitted. |
| Anthropic native | Messages system separation, key/version headers, text/thinking/tool blocks, stop reason, usage including reported cache inputs, explicit thinking settings | Exact model acceptance unverified; manual thinking must fit output bound; explicit temperature omission required for thinking. |
| Gemini native | generateContent content/parts/system instruction, generation/thinking config, finish/block state, usage including reported thoughts | Exact model acceptance unverified. No Google-hosted tools or multimodal requests. |
| OpenAI-compatible | Explicit endpoint/model/auth, local loopback, hosted presets and RunPod vLLM endpoint | Transport compatibility is not provider-wide certification. No native Ollama, RunPod Jobs or deployment. |

Structured blocks and sanitized raw payloads remain inspectable. Function requests are
represented at the adapter boundary but are not automatically executed. Tool-only, partial
or refused output cannot become a completed research answer. The existing bounded prompted
tool gateway remains permission-checked separately. Native tool-result conversations,
streaming, images/audio, embeddings and unrestricted model code remain unsupported.
Unsupported parameters fail explicitly; there is no model substitution or fixture fallback.

Model identities stay open-ended. Capability declarations remain researcher declarations.
Preflight distinguishes pinned configuration, compatible adapter/credential presence and
eligibility from endpoint reachability and verified inference. Neither is inferred from a catalog.

Official implementation references:
[OpenAI Responses](https://developers.openai.com/api/docs/guides/migrate-to-responses),
[OpenAI reasoning](https://developers.openai.com/api/docs/guides/reasoning),
[Anthropic Messages](https://platform.claude.com/docs/en/api/messages/create),
[Gemini generateContent](https://ai.google.dev/api/generate-content).

## Council, context and the six systems

Staged research is explicitly selected, requires structured actions and at least three rounds:
investigation; evidence examination/cross-criticism; response/revision/adjudication. There is
no fixed participant count or privileged model family. Missing eligible targets may yield an
explicit limitation claim. Profiles/instructions are pinned and instance IDs remain distinct.
Parallel participants receive the same committed round boundary. Arrival observations can
differ in time; scientific commits follow stable participant order. Failures unblock pending
commits and leave the run failed, not falsely completed.

Context manifests identify actual message artifacts, permitted sources/memory/history and
budget/dedup omissions. Staged contexts prioritize structured history over duplicate raw model
messages. Imported/retrieved content stays untrusted data, separate from instructions.

| System | Operational Pass 3 behavior | Boundary |
| --- | --- | --- |
| Epistemic Git | Immutable claims, evidence/span links, criticism, response/revision rationale, checkpoint/fork ancestry and diff | Prior versions remain. Generated agents may revise only their own claims. Span bounds/source linkage do not establish entailment. |
| Counterfactual Engine | Verified text-analysis forks, paired attempts sharing an immutable experiment, explicit criticism-strategy condition and configuration/source-hash comparison | Analysis forks do not resume hidden model state. Criticism strategy is the supported changed factor; arbitrary model/composition/source interventions require separately configured experiments. Matching is not causal proof. |
| False Critic | Targeted typed objections, evidence, reasoning/requested correction, author responses and optional revisions; Archivist judgments | Unsupported objections remain visible. Model judgments are unverified opinions, not independent verification. |
| Memory Tribunal | Existing principal/branch visibility and eligibility apply to actual model context; retrieval attribution stays in manifests | No unrestricted cross-agent retrieval or live Moss acceptance. Existing Tribunal algorithms retained. |
| Self-Correction Gym | Bounded original→criticism→response/revision→evaluation/checkpoint cycle with explicit criteria | Revision is measured, never assumed better. General semantic correctness/entailment scoring remains absent. Cache Gym algorithms preserved. |
| Adaptive Reflection | Existing deterministic rule maps recorded criticism signals to an inspectable next-turn evidence-focus recommendation in subsequent contexts | Prompt-level bounded adjustment only; no new authority, calls, budgets or self-modifying code. A model can ignore a recommendation. |

`text-descriptive-v2` records criteria, counts and denominators: claim versions/current claims,
linked/unlinked claims, criticism addressed/unresolved, revisions, reported contradictions,
evidential objections, requests, failures/uncertainty and known-usage coverage. Correctness and
citation entailment remain null. Incomplete token/latency/bill totals remain unknown. No arbitrary
combined quality score was introduced.

## Spending, recovery, export and preservation

Preflight performs no network request, mutation or reservation. Launch records run/experiment,
profiles/connections, tools, limits, captured provider allowances, disclosure/payment approvals
and per-attempt bound in an artifact referenced by RunState. Paid dispatch cannot raise the
captured allowance. Existing run/global ($75)/service/concurrency guards recheck every call;
an eligible configuration can still encounter a transient dispatch conflict.

Unknown prices require a complete explicit bound. Unknown bills retain their reservations.
Timeout/cancellation do not mean zero charge or remote termination. Uncertain calls are not
replayed or automatically retried. Existing worker ownership, crash/recovery, cancellation,
visibility, revocation, SSRF, idempotency and migration tests remain in the full suite. Closing
the terminal viewer does not own or cancel its detached worker.

ZIP export contains history, pinned experiment/profiles and recursively referenced request,
response, source, context and checkpoint artifacts, with SHA-256/size manifest. Artifact reads
are verified, configured secrets rejected and destination replacement refused. Atomic ZIP
publication requires a filesystem supporting exclusive hard-link publication. JSON export
remains available. Existing export files are not modified.

Before changes, the 262-test baseline passed. Original table/file hashes were saved privately;
a verified SQLite/artifact backup was created outside OneDrive at
LocalAppData/DOXA/pass3-original-backup. Final preservation checks confirm unchanged original
223 events, 291 records, 37 referenced artifacts, configuration rows, reservation/operation rows,
root credentials, README and workspace preference. The startup-help checkbox remains enabled.
Its guide position changed from the baseline while a separate v14 viewer was open on the
original workspace; the current preference was retained rather than overwritten. Test viewers
used isolated preferences and exited. The private preservation audit records both hashes and
the modification timestamp. The historical Moss $1 hold remains uncertain
and untouched. OneDrive precautions remain visible; no workspace was moved or merged.

## Acceptance evidence and limits

Preserved private mock workspace: `.doxa/pass3-model-provider-acceptance`.
Observed: 49 events; three distinct participants; two model profiles; two imported sources;
nine completed model calls/contexts; seven claim versions; two criticisms; one explicit
response; two revisions; two evaluations; one checkpoint and a verified text-analysis fork.
JSON and ZIP exports match persisted records and artifact hashes. This uses the actual
model-backed controller/wire path with fake HTTP; it is not successful live inference.

3A focused verification passed 65 tests. Expanded research-system checks passed 48 tests before
final acceptance extensions. Testing exposed a cache-only branch-comparison assumption, now
fixed for verified text-history restores. A wall-clock interrupted test was rerun successfully;
no performance certification is claimed. Final regression: **308 passed**, one existing warning.
Ruff, strict mypy (89 files), generated types and Studio compatibility build pass.

The v15 packaged CLI matches all nine original run exports, passes original workspace integrity,
performs offline preflight and exports/verifies the complete mock archive. A scan of 138 package
files and 200 publishable files found no configured secrets; no workspace/credential/runtime
data is bundled. The executable rendered the persisted mock research in the host-provided
Windows PowerShell PTY and exited with `q`, code 0. Two initial custom ConPTY capture attempts
timed out; those are test-harness failures, not successful interactive acceptance. The host
PTY result and headless interaction tests establish the narrower observed checks.

Portable: `dist/DOXA-Terminal-v15-Windows.zip`, **35,875,186 bytes**.
SHA-256: `cb4ab66208ae6f790ddfac05e9411a7743506ee9c846a827fbf4f3e38184bf0a`.
The canonical `dist/DOXA-Terminal-Windows.zip` is the same verified v15 archive; the main launcher
opens v15 against the existing project workspace. v14's executable/archive and a separate
`Open DOXA Terminal v14.cmd` launcher remain available. The v14 fallback archive retains hash
`2080cdf50cce29febbf05efdefb7249fec170e09902a466b05282ac10ccb9b5d`.
Close an older viewer before using v15. v15 reads historical records, but v14's strict readers
may reject newly enriched Pass 3 fields. Use v14 with original/backup-compatible histories;
preserving its artifact does not establish forward compatibility with newly written records.
Build warnings about optional tzdata/pysqlite2/MySQLdb imports also occur in the v13/v14 build
logs; they are pre-existing. No dependency upgrade was performed.

Manual Windows Terminal/PowerShell usability, clean-machine installation,
antivirus/reputation and signing acceptance are not established by headless/ConPTY tests.

| Status | Scope |
| --- | --- |
| Implemented and demonstrated | Bounded mock-provider multi-agent cycle, typed native/compatible wire behavior, claims/criticism/revisions, context manifests, evaluations, branches, accounting uncertainty, preflight, terminal actions and complete archive export. |
| Implemented, not live-tested | Exact native/hosted/local model compatibility, credentials/account access, actual provider usage/bills, existing paid retrieval integrations. |
| Registration/contracts only | Unsupported native catalog transports; adapter descriptors do not enable them. Native tool-result orchestration is unavailable despite preserved tool-request observations. |
| Deferred | Streaming/modalities/embeddings, GGUF execution, semantic citation entailment, arbitrary controlled factors and general automatic model-backed branch continuation. |

Next permitted action is the [separate minimal live acceptance procedure](../pass3-live-acceptance.md),
only after authorization naming provider/model and maximum spend. No signing, push, deployment,
paid inference or further development pass is authorized here.
