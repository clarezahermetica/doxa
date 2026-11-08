# Post-live overhaul: audit and verification map

## Confirmed baseline (November 4, 2026)

The native CLI completed two genuine calls in the failed research experiment. Preserve
its immutable history, original sources, artifacts, holds and exports. This pass is offline.
No inference, credential changes, installed replacement, README edits or publishing.

The canonical ledger already represents claim authors/revisions, challenge targets,
responses, evidence, judgments, checkpoints and evaluator provenance. No second database
or replacement of the six systems is needed. Existing workers persist call-start and
call-finish records; Textual polls committed events independently of worker lifetime.
At the audited baseline, CLI stdout was buffered and parsed only at completion. It must not be exposed
as private reasoning or treated as accepted research before controller validation.

At the audited baseline, ContextAssembler inserted full sources before structured history, measures content bytes
without schema/transport overhead, and can omit active objections. The provider validator
adds these costs later. Preflight checks only initial configuration. The fixed role/round
scheduler does not distinguish research outcome from successful process termination.
The inspector expands evidence artifacts into claims. Version v17 is installed independently
from source v20; changing source never upgrades the global Windows launcher.

## Dependency order

1. Shared exact context accounting, bounded relevant passages, required active history,
   full-cycle offline stress preflight, and source/installed runtime diagnostics.
2. Ledger-derived claim positions and bounded state-driven investigation scheduling;
   explicit termination reasons and unknown correctness scores.
3. Existing Textual activity as primary workspace, threaded claims and targeted citations,
   expandable content and replay; preserve advanced records and existing commands.
4. Reproducibility manifests, explicit control conditions and labeled quality comparisons.
5. Offline regressions, full suite, Ruff/mypy/schema checks, preserved-history verification,
   Windows launch instructions and a separately authorized next live test.

## Diagram interpretation

Claim -> criticism or acceptance -> author response/revision or justified maintenance ->
Archivist evidence assessment. Stop with supported/rejected findings or a recorded
unresolved outcome. Continue only for a recorded useful contribution within explicit
limits. Consensus alone is never a correctness criterion. Model judgments stay unverified.

## Compatibility

Prefer additive defaulted fields and ledger projections. Historical records are not
rewritten. New outcome or relationship semantics must be absent/unknown in older runs;
never infer a completed cycle from the old run status alone. No destructive migration.

## Verification

Final check results are recorded below. Tests establish infrastructure behavior, not live provider
compatibility or empirical research-quality improvement. Missing scores remain null.

## Implemented behavior and module map

| Area | Implementation | Verification boundary |
| --- | --- | --- |
| Request planning | `core/context_planning.py`, `core/workbench.py`, `providers/cli_session.py`: shared CLI serialization includes escaped JSON messages, trusted prefix, schema bytes and reserved output. Required claim exchanges precede bounded, relevant, located evidence passages. Agent and aggregate admission are applied before dispatch. | Deterministic tests and offline full-cycle stress; no claim about a provider's hidden prompt/tokenizer overhead. |
| Full-cycle preflight | `core/cycle_preflight.py`, `core/preflight.py`, CLI `run preflight --full-cycle`, existing terminal launch checks. A disposable synthetic workspace exercises the actual scheduler/context pipeline with growing structured responses. Original workspace is read-only. | Explicitly synthetic; no provider probe/generation, no tools, no proof arbitrary future model text will fit. |
| State-driven investigation | `core/investigation.py`, `core/text_research.py`, `core/workbench.py`, additive contracts in `core/models.py`. Targeted criticism, attributed responses/revisions, reassessments, evidence-linked Archivist judgments and separate research outcomes. | Offline fixtures, including multiple Skeptics, maintained claims, acceptance without invented objections, rejection without consensus, unresolved outcomes and resource stops. New live protocol untested. |
| Observable CLI activity | `providers/cli_session.py`, `core/execution.py`, `cli/activity.py`: durable process-start/session/turn/output-available/finish milestones, actual process ID when observed. | A real Python fixture process emits JSONL. No new live Codex invocation was performed. Model reasoning bodies are excluded; complete output still waits for normal validation/commit. |
| Existing terminal | `cli/console.py`, `cli/research_view.py`, `cli/inspectors.py`, `cli/research_tools.py`, `cli/screens.py`, `cli/reference.py`: activity first, compact actual agent/model/effort/time/usage, exchange table, complete thread/diff, separate citation navigator, full text on explicit request, recorded-event replay, control/label forms. | Automated real Textual widget interaction at 80x24, 100x30, 120x40, 160x50 in dark/light themes. Native visual acceptance is not certified; see below. |
| Procedure and controls | `core/research_manifest.py`, `core/controls.py`, `core/quality_labels.py`, CLI `main.py`/`workbench.py`: source/build/configuration/procedure manifest; unstarted solo, self-correction and multi-agent conditions; descriptive comparisons and explicit human correction labels. | Offline only. Human labels are annotations, not independent truth; unequal compute is disclosed. No causal improvement result. |
| Version and launch | `core/runtime_identity.py`, `version.py`, `scripts/launch_development.ps1`: source v21-dev, package remains 0.1.0a0; diagnostics show executable/workspace/commit and installed launcher target. | Current PowerShell version/diagnostic launch checked. Installed v17 and prior distributions unchanged. No new frozen build. |
| Schema/documentation | Generated `docs/contracts/records.schema.json`, `openapi.json`; linked architecture, storage, workbench and CLI notes. | Additive defaulted contracts, no SQL migration or historical rewrite. |

New regression files: `tests/test_post_live_context.py`,
`tests/test_investigation_protocol.py`, `tests/test_overhaul_research_views.py`.
The six research-system algorithms are retained; this extends their surrounding
controller, context, presentation and evaluation workflow.

## What the research outcome means

Select **Investigation** in the existing experiment form, structured actions and
sequential scheduling, with at least one Researcher/Executor, Skeptic and Archivist.
The fixed-round protocol remains available and is the compatibility default.

One challenged claim normally needs five turns: author claim, Skeptic criticism,
author response (revise, qualify or maintain), Skeptic reassessment, Archivist judgment.
A Skeptic can accept a claim without fabricating a criticism. An Archivist may abstain.
Multiple same-role instances are individually attributed. The independent verifier is
not an LLM Council participant.

`ResearchOutcome` separates concluded/stopped/interrupted/failed execution from
supported/rejected/mixed/unresolved epistemic outcomes. Supported/rejected means the
recorded, **unverified model judgment**, not independently established correctness.
Contradictory Archivist judgments remain unresolved. Historical runs without this record
have an unknown research outcome; their old `completed` flag is not retroactive evidence
of a complete investigation. For compatibility, a cleanly stopped worker may have legacy
Run status `completed` and ResearchOutcome `stopped/unresolved`; the terminal prioritizes
the latter. Failed operations retain failures and prior output, rather than replaying them.

The continuation check is a conservative structural heuristic over claim text and
source artifact/location changes plus explicit cycle/agent/call/time/context limits.
It is **not** a validated semantic detector of novel arguments or paraphrase loops.
No demand for consensus, automatic concession, forced revision, automatic verifier truth,
or automatic continuation after restart was introduced.

## Context and citation guarantees

The original document remains content-addressed and unmodified. Context selection is a
separate artifact with selected source/history IDs, actual message bytes, bounded text,
locations and explicit omissions. It prioritizes the active claim's ancestry and objections,
then relevant permitted evidence, then eligible memories. Private/revoked/quarantined or
superseded records do not become authorized because a retrieval backend returned them.
Unavailable referenced evidence is explicitly identified. Required state/passages that
cannot fit stop before dispatch with component/input/schema/output/remaining-budget details.

The CLI request byte count is exact for DOXA's serialized envelope and schema; byte-based
"token upper bound" remains conservative admission, not a calibrated model tokenizer.
HTTP accounting retains its existing conservative message overhead. Neither measures a
provider's hidden instructions. Native Codex internal connection retries remain outside
DOXA's zero-retry setting and cannot establish a hard subscription dollar cap.

Citation inspection opens recorded character spans when available. Otherwise a claimed
physical PDF page can be inspected with an explicit unverified-location label; it does
not invent printed-page mappings or prove entailment. Full source text is a separate action.
The full-cycle rehearsal copies scoped sources/configurations; it does not clone every
possible future memory or exercise network-tool follow-ups. Its report states those limits.

## Reproducibility, quality and sharing

Every newly started research run receives an immutable procedure-manifest artifact with
source hashes, source commit/tree hash when available, app/build, task, pinned agent/model
assignments and limits. Context artifacts and call records preserve what was supplied and
requested. Resolved model identity and random seed remain unknown unless observed; a
requested model or reasoning setting is not certified as the provider's effective setting.
Procedure reproducibility does not guarantee deterministic model output.

**Prepare research control** creates an unstarted condition; it does not authorize inference.
Solo uses one author call; self-correction uses claim/self-critique/response; multi-agent uses
the investigation protocol. Source hashes, question, rubric and pinned settings can be
compared. Different call budgets/usage remain visible. Heterogeneous models or customized
round-specific instructions require deliberate experimental design; preparing conditions
alone does not establish a scientifically controlled causal experiment.

**Label revision quality** appends explicit human labels for initial correctness, final
correctness and justification. Missing labels stay null; only fully labeled revisions
contribute to the descriptive net-correction count. This metric is not independently
validated. Unsupported concessions, appropriately maintained positions and appropriately
unresolved disagreements do not receive fabricated automatic scores. Claim counts,
citation presence, consistency checks and model consensus are structural observations.

Exact workspace archives and experiment exports are **private**: they can contain research
text, user instructions, metadata and operational details. New `public-summary` is a small
whitelist of nonidentifying counts/statuses/condition and epistemic caveats, not an anonymized
full archive or a guarantee arbitrary attachments are safe to publish. Review any public
research report separately. No public files were published in this task.

## Windows launch and observation

The global `doxa` command still launches the previously installed v17. To inspect corrected
source without replacing it, use PowerShell from this repository:

```powershell
.\scripts\launch_development.ps1 -VersionOnly
.\scripts\launch_development.ps1 -Workspace "$env:LOCALAPPDATA\DOXA\existing-research-workspace" -Diagnostics
.\scripts\launch_development.ps1 -Workspace "$env:LOCALAPPDATA\DOXA\existing-research-workspace"
```

The launcher requires the existing project `.venv`, accepts an existing ledger only,
restores the caller's workspace environment, and does not replace global launchers or
saved workspace preferences. Diagnostics show v21-dev, the source interpreter and the
v17 installed-wrapper warning. Do not migrate the project's old revision-0003 workspace
merely to view this test. Use the existing revision-0004 research workspace above.

1. Open the existing experiment in the list. Activity shows committed events in order;
   the failed research attempt remains failed and cannot be restarted as a fresh run.
2. Open **Inspect claim exchanges** from Ctrl+P or the Claims/exchanges view. Enter opens
   the full linked exchange and version comparison. Open a citation separately; request
   full source text only when needed.
3. **Replay recorded activity** displays persisted events without generation or worker
   dispatch. It is a read-only ordered record viewer, not time-paced token playback.
4. For a new attempt, explicitly create a new configured Investigation, import evidence,
   inspect pinned agents/settings and **Full-cycle offline stress**. Synthetic execution
   remains visibly synthetic. Do not select a live start until separately authorized.
5. For an approved live start, keep Activity open: process and turn milestones precede
   validated claims and judgments. Closing a viewer does not own/cancel the detached
   worker. Reopening reads the committed history. Errors/uncertain billing remain visible;
   never replay an uncertain call or release its hold automatically.

## Smallest proposed next live acceptance (NOT authorized or launched)

After reviewing this offline pass, prepare a **new** experiment ID in a clearly named new
workspace, for example `%LOCALAPPDATA%\DOXA\next-investigation`; do not repair
history by replaying the previously successful calls. The exact path/IDs and fresh readiness
report must be shown before requesting approval. Suggested procedure:

- Adapter/provider: existing locally authenticated Codex CLI, no API-key fallback.
- Requested model: `gpt-6.1-sol`; effort `low` for all participants. Resolved metadata remains
  separately observed/unknown. Check the installed CLI's current readiness before approval.
- One Researcher, one Skeptic, one Archivist, one claim and one criticism/response cycle.
  Maximum **five calls**, sequential concurrency one; per-agent turn limit two; no tools
  or DOXA retries. Acceptance rather than criticism can use fewer turns.
- Proposed ceilings: 60 seconds per call, 300 seconds total; 16,384 context admission units,
  32,768 serialized input bytes, 2,048 output units, evidence passages up to 8,192 bytes;
  32,768 per-agent and 98,304 aggregate admission units. Rehearse the exact pinned
  configuration/schema before approval; these are a proposal, not an already validated run.
- ChatGPT/Codex subscription quota consumption, potentially unknown usage/USD equivalent;
  CLI-managed retries can occur. No separately billed API provider, no hard subscription
  dollar guarantee. Any readiness change or new billing path requires another approval.
- Observe in the existing terminal, record original claims, actual objections/responses,
  reassessment and Archivist judgment, export privately, verify artifact hashes afterward.

This would test the corrected live trajectory. It would still not establish research-quality
improvement; that requires matched controls, evidence review and independent outcome labels.

## Incomplete and deferred

- No new live compatibility or complete genuine research trajectory was tested here.
  The preserved old research attempt contains two real calls and an incomplete exchange.
- Native Windows Terminal visual inspection, manual mouse/focus usability and a new frozen
  v21 distribution remain unverified. Automated Textual interactions/captures are not manual
  acceptance. Local SVG preview was blocked by browser policy and unsupported by the image
  viewer; no alternate hosting/browser workaround was used. Captures remain local.
- Semantic argument novelty, automatic entailment/correctness, calibrated quality metrics,
  broad ground-truth labeling and compute-matched causal studies remain incomplete.
- No automatic safe resumption of partially completed research/model calls, no automatic
  financial reconciliation, and no arbitrary untrusted-code execution were added.
- No live Moss cache/provider certification, no new model providers, no GUI revival,
  no credential rotation/replacement and no in-flight evidence-import workflow were added.
- Older binaries are not guaranteed to understand new record discriminators. Keep v17
  using its historical workspace or a backup, and use corrected source for new records.

## Final verification evidence

Final source verification completed November 5, 2026:

- **470 passed**, one pre-existing Starlette/httpx deprecation warning, 586.13 seconds.
  Entire suite: `.doxa/overhaul-frozen-source-full.log`. An earlier whole-suite run also
  passed 468 tests; the last two regression cases are included in the final 470.
- All **19 new checks** passed in their focused run (67.58 seconds), covering the three
  new test files, including four terminal dimensions/theme combinations.
- Ruff passed. Strict mypy passed for the host, explicit Windows and Linux targets
  (**99 source files** each). Package versions were preserved; the existing warning
  was not suppressed by changing dependencies.
- Both generated contract schemas reproduce exactly. Git whitespace checks passed.
  Local publication-safety scan: **190 files, zero secret/path findings**. No files staged.
- Historical six-turn configuration: isolated full-cycle stress passed with **zero model
  calls**. The distinct investigation fixtures exercised complete linked exchanges.
  Neither is genuine live research.
- All three preserved workspaces match the original ordered event-body hashes, event
  counts, record counts and SQL revisions. Record projections equal their canonical
  event payloads. SQLite quick checks pass. **73 artifacts checked, zero hash mismatches.**
- The old Moss operation/reservation remains uncertain/held. The failed Codex smoke
  quota operation remains uncertain. The repaired workspace retains its three completed
  quota operations. No hold was reconciled or released.
- Current PowerShell development-version and explicit-workspace diagnostics passed;
  source v21-dev, correct source interpreter and workspace, installed-wrapper v17 warning.
- Real Textual interaction tests passed in dark/light themes at 80x24, 100x30, 120x40,
  160x50. Updated local SVG captures were generated from explicitly synthetic records.
  **Manual/native visual acceptance remains unverified** for the reasons above.
- README, credentials, installed v17 and earlier distributions are unchanged. No SQL
  migration, live model/Moss/RunPod call, commit, push, release or deployment occurred.

Local operational logs/captures and preservation snapshots are in ignored
`.doxa/overhaul-*`; they are not distribution content.
