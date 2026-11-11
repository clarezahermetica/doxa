# Terminal workbench

Install and launch using [README](../README.md). The existing Textual application is
the primary interface; CLI commands use the same controller and workspace.

## Begin an experiment

1. Open `doxa`. Select an existing workspace or explicitly create a new empty one.
   `W` opens workspace selection; Settings shows its canonical path. Changing the
   shell directory does not select another research history.
2. Press Ctrl+P and choose **Add agent template**. Define the role, instructions,
   permissions and memory scope. Multiple instances can share a template or model.
3. For an offline exercise, leave model assignment optional and select synthetic
   execution. For future live work, **Choose model and connection** saves a versioned
   profile without making an inference request. Use the exact model ID and capabilities
   supported by your endpoint; credentials are masked references, not agent names.
4. Choose **Create experiment**, supply the research question, participants, protocol
   and resource limits, then **Import evidence** into that configured experiment.
5. Inspect launch preflight. **Start selected run** distinguishes synthetic execution
   from explicitly authorized live inference. Completed runs cannot simply restart;
   another attempt is an explicit operation with new history.
6. Inspect Activity, Claims, Sources, Contexts and Evaluations. **Review branch and
   revise claims** supports immutable human proposals, challenges, responses and review.
   **Compare trajectories** and **Export experiment history** inspect/export real records.

F1 opens searchable guidance and Ctrl+P opens commands. Unavailable actions explain
which prerequisite or run state blocks them. Raw JSON is an optional inspector.

Follow the [complete offline exercise](canonical-research.md) for source files, staged
criticism, revisions, comparisons and an independently inspectable export. Follow
[separate live acceptance](providers.md#test-an-httpapi-connection) only with a named provider/model and
explicit spending/disclosure approval. Saving a profile is not connection verification.

For an existing Codex account session, select **Local account CLIs / Codex CLI** in
Connection setup. **Check installed CLIs** reports safe local readiness without inference.
See [CLI setup](providers.md#configure-codex-in-the-terminal) for the distinct quota acknowledgment and limits;
this path uses no API credential or positive USD allowance.

## What a run records

Every participant has an instance ID, template/instruction versions and a pinned model
assignment. Sequential turns see earlier committed messages; parallel rounds start from
a fixed history cursor, with actual completion order retained. Calls, rounds, concurrency,
time and token admission are bounded alongside durable spending controls.

Context manifests identify the actual permitted sources, history and eligible memories
supplied to a request. Private, revoked and quarantined material cannot become eligible
just because a search adapter returns it. Shared model identity remains visible; several
agents agreeing does not establish independent corroboration or objective truth.

Claims and revisions retain exact evidence/version links. Human judgments, model
adjudication and deterministic checks remain different record types/provenance. Citation
linkage or a valid source span does not establish entailment. Text-analysis checkpoints
and forks restore recorded history; they do not restore a model's hidden state, replay
paid calls or automatically resume inference.

## Evidence and retrieval

TXT, Markdown, JSON, text PDFs and DOCX are supported subject to import/extraction bounds.
Original bytes and extracted text have separate hashes and parser provenance. PDF/DOCX
parsing has a 12-second wall timeout, 512 MiB memory and 6-second CPU limits through
Windows Job Objects or Unix resource limits. Archive expansion and extracted text are
bounded. OCR, embedded-object execution and layout fidelity are not provided.

Uploading retains the complete original; it does not imply every call received it.
Context assembly includes full authorized source text when its budget share permits.
Otherwise it supplies multiple ranked excerpts with original character ranges and PDF
page locations, records partial coverage in the context manifest, and retains the
full source artifact. Eligible memory/history receive reserved context room. Inspect
the persisted context messages to determine exactly which text an agent received.

SQLite FTS5/BM25 and optional Moss snapshots search authorized material; they do not own
experimental truth or memory trust. Moss cache reuse remains scoped by project, run and
participant, with eligibility rechecked after retrieval. Live Moss acceptance and remote
cloud synchronization are unverified. See [provider support](providers.md).

Web research requires explicit run/agent permissions, authorization and quotas. Approved
fetches use allowlisted HTTPS domains, validated public DNS, TLS, no redirects/proxies,
a cumulative I/O deadline and a 256 KiB response bound. DNS runs in a credential-filtered
child process that can be terminated on timeout. Synthetic tools return labeled fixtures;
no live search provider is configured. Generated code receives no network capability.

## Supervision and automation

Closing the viewer leaves detached execution separate from inspection. Reopen the same
workspace to follow committed events. Cancellation does not establish remote termination
or final billing. Use [recovery](workspaces.md#recovery-principles) for interrupted calls and held reservations.

Use `doxa --help` for exact CLI syntax. Common entry points include `profiles`, `agents`,
`experiment new`, `run preflight`, `run start`, `run watch`, `run cancel`, `claims`,
`compare` and `export`; list/inspection commands offer readable output and `--json` where
supported. The optional loopback API is started with `doxa serve`; it is not a graphical UI.

Legacy cache-policy CLI examples remain in `examples/council.json`, `backend-run.json`,
`execute-offline.json` and `memory-query.json`. They are explicit synthetic fixtures for
compatibility scripting, not live research results or required terminal setup.

## Investigations and outcomes

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


### Require dispute review

In **Create experiment → Protocol and limits**, choose **Investigation**, enable
**Structured actions**, use **Sequential** scheduling, and optionally select
**require criticism and reviewer follow-up before a supported conclusion**.

The equivalent CLI configuration is:

```powershell
doxa experiment new --name "Bounded review" --question "Your research question" `
  --member "Reader:1" --member "Critic:1" --member "Archivist:1" `
  --investigation --review-disputes --rounds 2 --data-dir "C:\path\to\workspace"
```

Use existing enabled template names. This creates an offline configured experiment;
import evidence before starting. `--investigation` selects structured actions; the
terminal form exposes that prerequisite explicitly. Model-backed execution still needs
configured assignments and separate disclosure/spending or subscription authorization.

The opt-in rule is pinned in the existing task `evaluation_criteria` as
`doxa:review-disputes-v1`. No field is added to historical records and no SQL migration is
required. Existing experiments without it retain the Archivist-judgment stopping policy.
Selecting the rule for fixed rounds is rejected before experiment creation or execution.

For a supported/rejected model judgment to end review under this rule:

- Every active claim needs a judgment on its current version from every assigned Archivist.
- Criticisms need recorded responses.
- Every assigned Skeptic needs a current acceptance/withdrawal assessment after any of
  that Skeptic's newer criticisms. An older acceptance cannot close a newer objection.
- Conflicting Archivist judgments remain unresolved and can continue within the caps.

All Archivists abstaining ends with an explicitly unresolved conclusion. Continuing review
never overrides round, call, per-agent, context/token, timeout or spending guards. Plateau
and cap stops remain unresolved, even if an Archivist previously said retain. Acceptance
does not force a challenge or revision. Shared models do not create independent evidence.

Each complete cycle appends an `investigation-criteria-v1` evaluation containing the
reason, policy, pending criticism/reviewer IDs, missing judgments and denominators. Open
**Inspect → Evaluations** to read these fields and the ordinary final evaluation. They
are deterministic controller diagnostics, not independent correctness verification.


## Evidence-quality diagnostics

Final text evaluations use `text-descriptive-v3`. Alongside existing criticism, revision
and human-label measures, they record:

- Document citation links and non-document evidence links.
- Invalid/missing source references or mismatched source-artifact references.
- Exact character spans that fall inside the referenced UTF-8 source text.
- Missing locations and invalid/unsupported spans.
- Located-span rate with the document-link denominator.

These measures count current claim/evidence links, not unique papers. Physical-page prose
alone is not an exact character span. Artifact-reference matching is distinct from the
workspace's full hash-integrity check. A well-located citation may support a false claim;
entailment, objective correctness and unlabeled research quality remain unknown. Existing
human correction labels remain separate. Previous evaluations are never rewritten.


## Inspect exchanges and activity

Ctrl+P offers **Inspect claim exchanges**, **Replay recorded activity**, **Prepare research
control** and **Label revision quality**. An exchange opens its versions and linked
arguments; citations open separately, and full document text requires an explicit action.

Activity shows the active agent, requested model/effort, elapsed time and reported usage.
Process milestones precede validated claims. Replay reads committed events without model
generation; it is not time-paced token playback. Full-cycle offline stress rehearses the
configured scheduler/context pipeline in a disposable workspace without invoking a model.


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
research report separately. Review exports before sharing them.
