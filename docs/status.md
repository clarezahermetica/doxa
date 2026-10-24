# Current research stage — October 24, 2026

Controller-owned research commands now implement the six-system domain mechanisms
on the finite cache-policy fixture. See [the implementation handoff](research-systems.md)
for transitions, events, tests, reproduction and per-system limitations, and
[the pre-change audit](research-audit.md) for what was missing before this task.

Generated source-code execution remains disabled: no enforced container sandbox
exists. The locked source-code repair flagship and general release remain incomplete.
No deployment, paid inference or Moss operation was performed in this research task.
README is intentionally empty at the user's request; setup remains documented in
[backend-stage.md](backend-stage.md) and historical [verification notes](verification/README.md).

The original prototype status below is retained as historical context, superseded
where the research implementation handoff documents tested behavior.

# Implementation status and next gates

The October 24 backend prototype builds on the foundation. Its supplied-answer fixtures
exercise real local state and verifier behavior, but are not model-performance evidence.
See [the backend-stage guide](backend-stage.md) for precise scope and remaining live gates.

| Area | Current status | Next acceptance gate |
| --- | --- | --- |
| Shared domain contracts | Implemented, versioned and serializable | Add transition-specific validation with each command. |
| Ledger and migration | Implemented atomic append/reload/deduplication, immutable record index | Forward migration compatibility; projection rebuild and backup. |
| Artifact store | Implemented hash/address/size verification | Checkpoint manifests, isolated restore and artifact bundle export. |
| Budget storage | Implemented single-ledger run/global reservations and settlement | Integrate paid command limits, crash reconciliation, external compute, warnings and usage events. |
| Controller | Versioned configuration, run lifecycle, terminal failures/cancellation, inspection/export and participant-scoped context | Multi-process worker ownership and broader transition families. |
| Six research systems | Narrow integrated cache-policy workflows: claim revisions/diffs, verified restore/fork, criticism gate, memory governance, evaluation/compare and bounded reflection | General-purpose implementations conforming to every original port; full source-code repair. |
| Agent Council / four modes | Distinct bounded flows; separate identities/profiles, scopes and role contexts | Real-provider multi-role validation and broader protocol research. |
| Providers / retrieval | Optional RunPod HTTP and Moss Python adapters with mocked tests; dependable local keyword retrieval | Separately authorized live smoke tests. OpenAI hosted, Gemini and Claude remain ports only. |
| Task environments and independent verification | cache-policy v1 finite environment and independent fixed read/update/delete oracle; no generated code | Restricted container code-repair environment and oracle contract implementations. |
| Sandboxing | Disabled implementation; limits contract | Restricted container enforcement tests before generated code execution. |
| Evaluation / annotation | Bounded task outcomes, recovery/regression denominators and descriptive matched-version comparisons; annotation contracts retained | Human annotation mutation/rubric API and broader evaluator suites. |
| CLI / API | Config import, execute, cancel, compare, memory proposal/validation/transition/query, accounting/reconcile and export | General research commands as their controller behavior becomes available. |
| Studio | Working configuration/event inspector shell | Real claims/memory/lineage/evaluation/annotation views; React Flow then. |

## Original sequencing reference

The following preserves the foundation's original dependency order. Completed narrow
pieces are reflected in the table above; this is not a current list of wholly unstarted work.

1. Harden controller commands: immutable state transitions, typed causal/domain links,
   authorization and scoped participant reads; define reservation/call crash recovery.
2. Implement a provider with mocked-HTTP contract checks, strict output validation,
   cost upper bounds, durable usage events, retry/timeout/cancellation. Keep offline tests.
3. Implement a task adapter and independent verifier behind a proven restricted sandbox.
   Select the first fixture in a separate task; the locked cache fixture remains an
   eventual release reference, not a foundation deliverable.
4. Register Solo Direct only after one real end-to-end run passes and failures persist.
5. Add checkpoint manifests, actual validated restore and fork; then commitment version
   commands/diffs and evidence-gated criticism, preserving rejected objections.
6. Add Memory Tribunal transitions and scope-aware eligible retrieval with poison,
   quarantine and revocation tests. Add bounded reason-coded reflection and skips.
7. Implement the other three protocols with explicit behaviors and matched-cost tests;
   add Gym comparisons and human annotation with separate provenance.
8. Expand Studio around real records, complete JSON/artifact export and replay labeling,
   and verify the release against all October 18 gates. Research claims require evidence.

Each step should leave the preceding tested behavior intact. Foundations do not qualify
as complete implementations of research algorithms, provider support or sandboxing.
