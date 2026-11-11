# v24: bounded dispute review, citation diagnostics and terminal update

This pass adds no providers, live calls, unlimited loop, automatic billing reconciliation
or execution resume. The existing controller, canonical ledger and frozen terminal remain
the application. Older builds and experimental histories are retained.

## Choosing the execution criterion

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

## Offline acceptance and distribution

The targeted checks exercise unresolved disagreement, accepted claims, stale judgments,
new criticisms after acceptance, conflicting Archivists, hard call caps, timeout and
cancellation, structural plateau, invalid citation data, truthful unknown metrics, CLI
configuration, 80×24/120×40 terminal forms, and export/restore preservation.

Packaging uses the numeric source identity (`v24`) and refuses an existing distribution.
The build script now derives the default identity rather than assuming an older version.
The local installer validates hashes and changes the owned launcher to the new version
while retaining prior version directories. Workspaces, appearance/preferences and
credentials stay outside the installation. No GitHub Release or binary upload is performed.

Observed full-suite, package and installation outcomes are recorded in `docs/status.md`
after verification. The packaged offline workflow completed with 17 persisted events and
zero live model calls. An unredirected, owned Windows console rendered the actual terminal
and exited with code 0 after a real quit key. The earlier redirected ConPTY fixture failed
to capture both DOXA and a minimal control application; it is not counted as a passing
terminal test. Native console automation is not manual Windows Terminal, clean-machine
or signing acceptance. The 156-file distribution passed manifest hashes, ZIP CRC and
private-data/secret checks. A stale canonical acceptance-script selector was updated to
recognize the current descriptive evaluator; its five focused checks then passed.

## Remaining limits

This is a bounded execution improvement. There is still no durable human pause/continue
cursor or automatic restart of interrupted inference. Uncertain requests/holds are not
replayed or released. Plateau detection compares claim/evidence structure, not semantic
novelty: paraphrases may look new and fresh arguments can leave that structure unchanged.
Cross-run resource policy and descendant-process containment remain separate prerequisites
for longer investigations. No live compatibility or causal research-quality improvement
is established by these offline tests.
