# Research implementation audit — October 24, 2026

Before this task, 57 tests covered a bounded cache-policy prototype. This is the
pre-change audit, not a claim that its acceptance gates were complete.

| System | Existing mechanism | Missing behavior at audit |
| --- | --- | --- |
| Epistemic Git | Immutable claims, single correction, run-level proposition diff | Typed contradiction, stable identity, branch projection, dependency impact, standalone transitions |
| Counterfactual | Hash-addressed state snapshot, finite environment restore, one child | Versioned manifest, restored continuation state, multiple independent children, failed restore audit |
| False Critic | Binary initial/alternative pass gate | Partial and unknown objections, separate responses, standalone challenges, exact-case diagnosis |
| Tribunal | Quarantine, fixed lesson oracle, approval/rejection/revocation, stale-ID recheck | Categories, narrowing, explicit branch validity, broader lifecycle tests |
| Gym | Success/recovery/regression, descriptive run comparison | Branch evaluations, complete rate denominators, human mutation/rubrics/preferences, JSONL |
| Reflection | One verify/skip decision | Ordered eight-action policy, observed resource state, durable caps and loop prevention |

All six original `systems/contracts.py` interfaces are ports. Optional provider
tests use mocks. Supplied protocol answers are synthetic. Generated code execution
is disabled because no enforced container sandbox exists. This task does not build
infrastructure or convert finite-policy checks into evidence of arbitrary code repair.

The six detailed Notion system pages were read and saved under `docs/specs/`;
the consolidated design lock remains authoritative subject to the user's current
scope (empty README, no frontend work, deployment or paid calls).
