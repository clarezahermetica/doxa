# Event Model and Core Data Entities

Source: https://app.notion.com/p/3f103b8af6fc81b6ac43f8758dfeaaeb

Retrieved for foundation setup on October 23, 2026 (America/Chicago).
Source last edited: 2026-10-13T03:47:54.257Z. Notion verification: unverified.
This is a source snapshot, not evidence of implemented behavior.


## Why an event model

DOXA needs a history that survives rollback. Current working state can change or be restored; experimental history must remain auditable. An append-only event stream provides the chronological backbone, while tables or materialized views provide convenient current-state queries.

## Core entities

<b>Experiment</b> — task, environment version, policies, budgets, model assignments, evaluator versions.

<b>Agent</b> — role, model/provider configuration, permissions, memory scope.

<b>Trajectory</b> — one branch of execution with parent ancestry and terminal status.

<b>Event</b> — timestamped observable transition.

<b>Claim / Decision / Evidence / Challenge</b> — epistemic and review objects.

<b>Checkpoint</b> — restorable environment state plus canonical verification metadata.

<b>Memory</b> — persistent candidate lesson or record with provenance and trust state.

<b>Evaluation</b> — automated or model-based assessment with typed evaluator identity.

<b>Annotation / Preference</b> — human or automated judgment with rubric/version.

## Proposed event vocabulary

EXPERIMENT\_STARTED, AGENT\_CONFIGURED, ENVIRONMENT\_INITIALIZED, OBSERVATION\_RECEIVED, CLAIM\_PROPOSED, CLAIM\_REVISED, EVIDENCE\_ATTACHED, DECISION\_RECORDED, ACTION\_REQUESTED, ACTION\_EXECUTED, TOOL\_RESULT\_OBSERVED, CHECKPOINT\_CREATED, CHALLENGE\_SUBMITTED, CHALLENGE\_RESPONDED, VERIFICATION\_RECORDED, REFLECTION\_TRIGGERED, ROLLBACK\_REQUESTED, CHECKPOINT\_RESTORED, BRANCH\_CREATED, MEMORY\_PROPOSED, MEMORY\_STATUS\_CHANGED, TRAJECTORY\_COMPLETED, EVALUATION\_RECORDED, HUMAN\_ANNOTATION\_ADDED.

## Provenance types

At minimum: model\_output, tool\_observation, deterministic\_verifier, task\_answer\_key, human\_annotation, imported\_source, system\_inference, and LLM\_evaluator.

## Branch rules

Every non-root trajectory stores a parent trajectory and fork event or checkpoint. Restored execution creates a new branch rather than rewriting the old one.

## Required reproducibility metadata

Task/environment version, initial snapshot identifier, provider/model IDs, sampling/settings where exposed, instruction versions, tool permissions, policy version, evaluator version, and cost or usage fields where available.

## Implementation requirement

Frontend graph nodes, CLI inspection commands, and exports must derive from the same persisted entities. No UI-only shadow state for core research records.

## Ledger v1 acceptance additions — October 12, 2026

- Shared Experiment Ledger is the canonical engineering deliverable; SQLite is the local system of record. Event records are append-only, with atomic writes, stable UUIDs, explicit per-trajectory sequence, parent event IDs, branch ancestry, idempotency/deduplication key, actor role, provider/model ID, provenance type, payload schema version, and UTC timestamp.
- Attach immutable artifact hashes (for snapshots, patch diffs, verifier logs and source documents) and persist relative local artifact paths; compare restore state hashes/checkpoint manifests before asserting restoration.
- The ledger stores separate typed facts for <b>model asserted</b>, <b>tool observed</b>, <b>independently verified</b>, <b>LLM evaluated</b>, and <b>human annotated</b>. Model disagreement remains inspectable without overwriting competing versions.
- Run-level and model-call-level usage ledger: token counts as reported, estimated USD by price-version, reservation/remaining cost budget, actual billed cost if available, tool execution and branch costs. Unknown usage is explicitly unknown rather than zero.
- Commit an event and its linked object changes atomically in SQLite; process crashes or retries must not create duplicate consequential actions. Rebuild CLI, Studio, evaluation, and exports from persisted records. Test serialization, reload, migration, and fork replay.
- Privacy: store locally by default; do not leak provider keys into ledger payloads or exported bundles.
