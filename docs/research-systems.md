# Research systems — implementation and reproduction

This stage implements controller-owned research transitions on `cache-policy` v1.
It is a finite, built-in stateful environment, with real state changes and fixed
independent read/update/delete tests. Inputs and demonstration annotations are
explicitly synthetic. These are engineering checks, not model-performance results.
The pre-change audit is [research-audit.md](research-audit.md).

## Reproduce the integrated experiment

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\doxa.exe research-demo
```

`research-demo` initializes/migrates the canonical `.doxa` ledger, then creates a
new synthetic experiment there. It makes no provider, Moss, deployment or paid call.
It prints the actual run, checkpoint, child IDs, evaluations and retrieval outcomes.
Use those printed IDs below; do not replace them with invented records:

```powershell
.\.venv\Scripts\doxa.exe inspect <run-id>
.\.venv\Scripts\doxa.exe compare-branches <run-id> <first-child-id> <second-child-id>
.\.venv\Scripts\doxa.exe export <run-id> .doxa/research-export.json
.\.venv\Scripts\doxa.exe export-jsonl <run-id> .doxa/research-export.jsonl
```

Exports refuse overwrites. JSON includes accounting; JSONL contains the run and
canonical events with nested records, artifact references, ancestry and provenance.
Neither is an artifact archive. Keep exports private. All commands and the HTTP
`POST /api/runs/{run}/branches/{branch}/commands` route use `Controller.research_command`.
`GET /api/runs/{run}/compare-branches?baseline=...&treatment=...` exposes persisted
comparison data to the existing Studio/API inspector without adding a frontend design.

The demo records a known faulty policy/diagnosis, independently verifies failure,
pins S0, mutates the parent's actual values to S1, and restores two independent
children. One child accepts a verified update-invalidation criticism and selects a
passing built-in policy; the other rejects a misleading delete criticism and retains
its original failure. It records reflection checks/skips, quarantines a generalized
lesson, promotes/retrieves/revokes a narrow lesson, evaluates both outcomes, saves an
explicitly synthetic dimensional label/pairwise preference, and closes the run.
Tests reconstruct this history through new controller instances and JSONL exports.

## Shared correctness rules

Research commands are typed proposals. The deterministic controller checks record
type, participant identity, branch visibility, transition preconditions, artifact
integrity and evidence gates. Commands carry stable caller idempotency keys and
SHA-256 request fingerprints. Retries return the original event; changed requests
using the same key conflict. A serialized SQLite transaction checks the prepared
branch cursor and writes events plus immutable records together. Restore and fork
events commit in one transaction. Failed commands append sanitized rejection facts;
they never record successful restore or execution. A concurrent stale cursor is
rejected, and the caller must reread rather than execute stale instructions.

The existing event names, migrations and v1 records are retained. Added optional
fields have historical defaults; `trajectory_state` is an additive discriminator.
No SQL table rewrite or separate subsystem database was introduced. Event timestamps,
actor IDs, model assignments and causal links attribute record versions. Original
serialized migration fixtures remain tested. This does not provide database tamper
resistance against the local operator.

## Epistemic Git

`systems/research.py` reconstructs commitments by inheriting only the ancestor
prefix pinned at a fork. Future parent writes and sibling revisions are excluded.
Controller claim commands append stable commitment identity plus immutable version
IDs, author, status, declared/inferred dependencies, support, contradiction and
rejected evidence. Qualification, contestation, retraction and supersession append
versions. Contradictory evidence cannot overwrite existing text. Supported status
requires independently verified matching proposition evidence; attaching an imported
statement is insufficient. Authors preserve separate positions.

Declared dependency graph traversal finds transitive affected claims and decisions.
The upstream revision stores their review IDs; it never declares the dependents
false. Inferred relationships remain labeled and are not treated as declared causes.
Branch/cursor diffs expose old/new propositions/status, author, evidence additions,
removals/rejections, dependency types and affected IDs. Historical challenge targets
remain exact immutable version IDs.

Events: `CLAIM_PROPOSED`, `CLAIM_REVISED`, `EVIDENCE_ATTACHED`, `DECISION_RECORDED`;
critic-authorized revisions also live inside `CHALLENGE_RESPONDED` with exact ancestry.
Tests: `test_epistemic_versions_dependency_impact_and_restart`,
`test_conflicting_branches_pin_ancestor_prefix_and_diff`, criticism transition tests.
Interactions: supplies targets to Critic, lineage to Counterfactual, and trace metrics
to Gym. Limitation: no semantic dependency inference or general proposition oracle.

## Counterfactual Engine

Manifested checkpoints pin versioned fixture/configuration artifacts, canonical
serialized cache state, observations, model assignments, budget policy, eligible
memory version references and event cursor. Restore checks every referenced artifact,
manifest consistency, fixture hash, model/policy configuration and canonical state
equality before creating a child. The restored state itself is persisted on the
child; subsequent actions load that state, not a new default environment. Parent
events and working state remain unchanged. Children can diverge and survive reload.

Replay is an explicit read-only historical continuation. Fresh execution is labeled
separately; it does not promise stochastic reproducibility. Comparisons expose
verified starting hashes, interventions, final state hashes, configuration, claim
diffs, and separately stored branch evaluations/resources. Inherited work is included
in each branch view and must not be summed as independent work. Memory snapshots
never override current Tribunal authorization after revocation.

Events: `CHECKPOINT_CREATED`, atomic `BRANCH_CREATED` / `CHECKPOINT_RESTORED`,
`ACTION_EXECUTED`, `TRAJECTORY_COMPLETED`. Rejections use `DECISION_RECORDED` with a
typed evidence record whose source is `research-command-rejected`.
Tests: actual S0/S1/two-continuation test, corrupt/missing/incomplete restore controls,
replay and abandonment tests, atomic batch/stale-cursor tests, branch comparison test.
Limitation: restores only finite serialized state; no external effects or arbitrary
workspace/process recovery. The source-code fixture remains blocked by sandboxing.

## False Critic

Challenges identify exact claim version, critic/model via actor event, alleged
failing oracle cases, optional confidence and candidate revision. The concrete
`CacheIndependentVerifier` implements the existing `IndependentVerifier` port;
the controller uses its same pure task check for adjudication. It tests the target
and proposed alternative independently. An objection is valid only for actually
failing alleged cases, invalid for passing alleged cases, partial for mixed cases,
and unverified when no checkable cases are supplied. Critic confidence is not used.

Accept/reject/qualify/investigate/defer are separately attributed response records.
Accept requires a valid objection and independently passing replacement; qualify
requires partial evidence and never asserts full correctness. Outdated target
versions cannot be revised. Rejecting a bad objection does not certify the original
answer. Conflicting challenges are retained separately.

Events: `CHALLENGE_SUBMITTED`, `VERIFICATION_RECORDED`, `CHALLENGE_RESPONDED`.
Tests: five criticism-class cases, unsafe-accept negative controls, exact immutable
targets, IndependentVerifier port evidence, and four-context deliberation control.
Interactions: creates Epistemic revisions, Reflection signals, and Gym discrimination
denominators. Limitations: natural-language objections without supported case IDs
remain unverified; no universal truth assessor or reward for agreeing with critics.

## Memory Tribunal

Existing proposal/validation/transition/retrieval commands now retain stable memory
identity, category (episodic/semantic/procedural/reflective), branch validity and
explicit source cursor. New candidates and narrowed/superseding proposals enter
quarantine. Promotion needs independent validation of the exact candidate version;
rejection/revocation is terminal. Narrowing changes content/conditions via another
quarantined version requiring fresh validation. Private/shared changes require an
explicit new proposal. Retrieval checks current versions, approval, validation,
ownership/shared permission, requested eligibility and branch scope after external
search returns. Moss remains an optional candidate-ID search, never authority.

Events: `MEMORY_PROPOSED`, `VERIFICATION_RECORDED`, `MEMORY_STATUS_CHANGED`,
`RETRIEVAL_RECORDED`. Tests: existing `test_moss_tribunal.py` poison/stale/private/shared
controls plus narrowing, branch scope, revocation/reload and abandoned-origin tests.
Interactions: checkpoint references and prompt eligibility, Gym contamination audits.
Limitations: validators remain a small explicit cache-policy lesson set; retrieval
is run-scoped. Cross-run transfer needs an explicit independently validated proposal,
not implicit reuse of another run's private history.

## Self-Correction Gym and annotation

`research_evaluation.py` computes rates with explicit numerator metrics and
denominators. A zero denominator yields null. Outcomes include task success, test
pass rate, failure recovery, regression, criticism discrimination, unjustified
revision, memory contamination, repeated errors and evidence trace integrity.
Objective verification requires the claimed policy to be deployed. Trace integrity
checks matching candidate content in independent evidence, not mere citation count.
Observed calls/tools and latency are recorded; absent token/billing data stays null.
Run comparisons reject mismatched task/environment/evaluator versions. Branch
comparison retains configuration and does not assert causal superiority.

Human labels are separate `Annotation` records, never objective result replacements.
`trajectory-quality-v1` permits 1–5 ratings in overall, evidence, consistency,
criticism, revision, memory, recovery and efficiency. Anchors: 1 = clear failure,
2 = substantial problems, 3 = mixed/adequate, 4 = strong with minor issues,
5 = fully supported for the stated scope. Pairwise A/B/tie/neither requires two
actual distinct trajectories; reviewer, rubric, timestamp/event and targets persist.
The demo reviewer is explicitly synthetic. Actual human review must supply a real
reviewer reference and judgment through the command API/CLI.

Events: `EVALUATION_RECORDED`, `HUMAN_ANNOTATION_ADDED`. Tests: recovery/regression
denominators and null billing, matched-run comparisons, annotations/export/reload,
invalid pairwise targets/ratings, failed-vs-successful branch comparison.
Limitations: no statistical inference, broad benchmark suite, actual human ratings,
or complete artifact export archive. General costs are not inferred from token counts.

## Adaptive Reflection

`reflection_rule` is a pure first-match `adaptive-v1` policy. Ordering: hard resource
stop; verified-success skip; repeated-trigger escalation; verified regression with
an integrity-checked recoverable checkpoint; stagnation escalation; contradiction
verification; validated-criticism reflection (cap); unsupported-objection skip;
failure verification then targeted critique (cap); seek evidence; retrieve verified
memory; continue. Critique and reflection share a maximum of two interventions per
branch, bounded further by experiment policy. Repeating a trigger cannot start an
unbounded review loop. No private model reasoning is consulted.

The controller derives signals from visible records, actual reservations, calls,
tool use, elapsed time and integrity checks. Decisions persist trigger, rule ID,
selected/considered actions, budget before/after and resulting state. Decision
computation itself consumes no paid budget, so before/after can correctly be equal.
Actions are proposals for the next controller operation; selecting rollback does
not falsely assert restoration, and selecting reflection does not call a model.
Every eventual paid dispatch still requires the existing persistent spending guard.

Events: `REFLECTION_TRIGGERED`, `REFLECTION_SKIPPED`; actual restoration only emits
restore events after its own checks. Tests: ordered-rule matrix, durable repeated
trigger, full reservation hard stop, intervention caps, rollback prerequisite and
success-skip integration. Limitation: no learned policy or automatic human escalation
delivery; policy decisions remain inspectable recommendations for controller commands.

## Protocols and remaining release gates

Existing four modes retain distinct behavior and common storage/evaluation. Direct
makes one proposal and verifies; cooperative investigators receive separate contexts;
adversarial challenges require external evidence; Deliberative separates proposer,
skeptic, defender and adjudicator contexts. Live Deliberative requests all four
phases. Historical synthetic fixtures with only three supplied answers remain
supported; supplying `adjudicator` exercises the fourth phase. A deliberately wrong
fourth-phase proposal fails independent checks, as tested. No live provider inference
was performed in this task and no model assignment is fabricated for offline fixtures.

**Incomplete release requirement:** generated cache-repair source code still cannot
execute. `DisabledSandbox` remains fail-closed. Required next port: an enforced
container runner implementing `SandboxLimits` (no network/secrets, CPU/memory/time/
filesystem quotas), its adversarial enforcement acceptance tests, and a task adapter
that deploys patches and runs the locked repair oracle there. A filesystem snapshot
or worktree alone is insufficient. This assignment deliberately adds no infrastructure.
The finite-policy experiment therefore proves six-system domain interaction, not
completion of the locked executable code-repair flagship or general DOXA release.
