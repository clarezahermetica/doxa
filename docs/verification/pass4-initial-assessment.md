# Pass 4 initial capability and integration assessment

Read-only assessment, November 2, 2026. No provider calls or research records were changed.
The preservation snapshot is local at `.doxa/pass4/baseline.json`: 223 events, 291 records,
five configurations, one reservation and one operation; 337 protected files, including
installed v17, older archives, appearance/workspace preferences, credentials and artifacts.
The working tree already contains substantial tracked modifications and untracked completed
work. README is already modified relative to Git; that is pre-existing owner-reserved content.
Branch `main`, origin `https://github.com/clarezahermetica/doxa.git`, HEAD `0639d27`.

## Existing operational boundaries

| System | Exact implementation | Demonstrated boundary before Pass 4 | Verification still needed |
| --- | --- | --- | --- |
| Epistemic Git | `systems/research.py:commitments`, `commitment_diff`, `core/research.py`, `core/text_research.py:TextResearch.propose` | Append-only revisions, source evidence, branch-visible commitments and inspection tests | Canonical corpus and version/source/context trace across conditions |
| Counterfactual Engine | `ResearchRuntime.checkpoint/fork`; `TextResearch.snapshot/fork`; `core/comparison.py` | Finite cache state restored/checked; text forks explicitly `human_analysis_only` | Controlled example, archive/backup replay and clear exclusion of autonomous text-branch model continuation |
| False Critic | `ResearchRuntime.adjudicate/respond`; `TextResearch.apply_generated/propose` | Independent finite-cache adjudication; structured textual objections/responses; Archivist model-judgment attribution | Multiple critics/Archivist in one canonical trajectory; no claim of natural-language truth verification |
| Memory Tribunal | `systems/memory.py`, `core/memory_commands.py`, `ContextAssembler.assemble` | Eligibility, private/shared visibility, quarantine/revocation and scoped retrieval tests | Canonical before/after memory controls linked to contexts; distinguish corpus evidence from eligible memory |
| Self-Correction Gym | `core/research_evaluation.py:evaluate_branch`; `TextResearch.propose(ReviewEvaluate)` | Objective finite-cache rates; descriptive text counts and null correctness/entailment | Declared reference labels and denominators; keep citation linkage, span validity, entailment and correctness separate |
| Adaptive Reflection | `systems/research.py:reflection_rule`; `ResearchRuntime.reflect`; `DebateRuntime.reflect_round` | Bounded finite-task rules and text-round recommendations recorded in later context | Canonical recommendation/context linkage; no claim that recommendations grant additional calls or permissions |

The existing `research-demo` is a complete finite-cache six-system engineering trajectory.
The text research path is broader in questions/materials but deliberately weaker in independent
verification. They must not be described as equivalent scientific evaluators.

## Concrete integration findings to reproduce

1. Public experiment creation exposes `structured_actions` / `staged_research` for synthetic
   runs. `DebateRuntime.turn` supplies a plain-text default fixture, but its structured path
   immediately calls `json.loads`. A normal structured offline run therefore appears to require
   hidden programmatic `synthetic_answers`. Reproduce before fixing; use the same existing
   structured proposal/controller boundary, never a second synthetic research engine.
2. `doxa models` still has an obsolete Studio/.env empty-state instruction in
   `cli/workbench.py`, unlike the corrected sibling `profiles` command. Correct if reproduced.
3. Existing text evaluation counts evidence linkage and explicit objections, not citation
   entailment or objective correctness. Reference labels must be independently declared in the
   fixture; do not reinterpret those descriptive rates as truth measures.
4. Text checkpoint continuation is human analysis only. A fork must not silently replay model
   calls. The canonical study needs a finite-cache companion for the strongest six-system
   operational acceptance and an explicit limitation on text-model branch continuations.
5. The original README and older documentation contain historical launch/version statements.
   README stays untouched; supply an owner-review checklist and accurate current technical docs.
6. Provider configuration and mocked transports do not establish live compatibility. Official
   documentation is being checked; actual live acceptance remains pending named authorization.

## Dependency order

1. Finish baseline pytest/Ruff/strict-mypy and preserve the initial snapshot.
2. Add failing regressions for concrete blockers, then make small controller/interface fixes.
3. Preregister a fixed cache-coherence corpus, hypotheses, reference labels and A/B/C controls.
4. Exercise canonical text trajectories plus the supported finite-cache six-system trajectory;
   trace contexts, memories, revisions, adjudication, checkpoints, branch diffs and evaluations.
5. Verify independent archive/backup inspection and exposed CLI/Textual workflow; test mocked
   model failure/concurrency, spending uncertainty, credential/network boundaries and responsiveness.
6. Complete official-provider review and the separate bounded live-acceptance checklist, without
   calling providers or inferring authorization from stored keys.
7. Prepare publication exclusions/manifests and owner GitHub review checklist; do not stage/push.
8. Run final regressions/static checks, build a new internal terminal candidate (preserve v17),
   test isolated install/upgrade/uninstall and report offline readiness vs pending live acceptance.

This file records the initial assessment, not a successful Pass 4 acceptance claim.
