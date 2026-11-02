# Proof-of-concept publication preparation — November 2, 2026

CI compatibility follow-up: the original publication's Ubuntu jobs for Python 3.12 and
3.14 stopped at mypy with four Windows-only `ctypes.windll` references, before running
tests. Explicit platform guards now keep credential protection and Windows parser jobs
unavailable outside Windows; parser handle types remain explicit across both branches.
CI also checks the Windows platform types on Ubuntu. Local focused credential/document
verification passes 24 tests; the corrected commit reruns the complete remote matrix.
That rerun cleared both type checks and exposed a test-collection path mismatch between
the `pytest` launcher and `python -m pytest`. The repository root is now an explicit pytest
test path so the canonical offline study helpers can be imported with either entry point.

The owner's proof-of-concept update is terminal only. React Studio and native desktop
source/build files are excluded from the published tree and retained locally; the
graphical entry point and Studio CI job are removed. The CLI, existing Textual workbench,
shared controller, optional local API and canonical ledger remain. Historical graphical
descriptions in earlier reports below do not describe this publication's supported UI.

Security review identified and corrected two issues before publication: untrusted Rich
markup could dispatch terminal actions on click, and slow web responses could outlive the
fetch timeout. Research text now renders literally. Web DNS uses a killable credential-free
resolver child; TLS and every HTTP receive share an absolute deadline with complete-response
checks. These changes are in source; previous internal binaries and installed v17 are not
updated. No binary release is included. Live inference and independent real-world acceptance
remain unverified. README preserves the owner's personal wording and separates GPT's note.

Final terminal-only verification: 376 tests pass on Windows with Python 3.14.7, including
the publication security regressions, against an isolated source tree with no GUI files or
private workspace. One existing Starlette TestClient deprecation warning remains. Ruff and
strict mypy (89 source files) pass; regenerated HTTP/domain schemas match the staged files.
The terminal entry reports its version without opening the viewer. The staged 221-file tree
and all 149 historical blobs in the two prior commits pass the known-credential/pattern and
private-path review. No scanner is a guarantee of absence of vulnerabilities. Protected local
workspace, credential, preference, installed-app and old-build hashes remain unchanged.

Only source is published: current binary packaging, clean-machine acceptance, live providers,
paid inference and independent research use are not verified by this update. Earlier commits
retain the retired GUI and original author metadata; history is not rewritten. Public visibility
requires the owner's final confirmation. The Pass 4 counts and package checks below refer to
their historical checkpoint, before these security fixes.

# Pass 4 — offline validation and internal candidate — November 2, 2026

Final verification: 360 tests pass with one existing Starlette warning; Ruff and strict
mypy (90 source files) pass. A preregistered fixed-corpus A/B/C fixture and finite all-six
companion preserve inspectable sources, participant identities, contexts, claims,
criticism, revisions, evaluation and branch ancestry. Independent standard-library
archive inspection and isolated workspace backup/restore pass. These synthetic controls
demonstrate procedural integration, not model-quality improvement or citation entailment.

Corrected exposed structured synthetic execution, two provider stop-state classifications,
responded-challenge adjudication selection and stale CLI model instructions. Known-credential
checks now cover custom/historical authentication references, shadowed copies, JSON escapes,
duplicate members, compressed DOCX metadata and JSON/JSONL/ZIP exports. A discovered large
atomic-write regression was fixed and its 1,050-record case passes. No research algorithm,
public contract, dependency version or historical record was replaced.

The separate internal v20 candidate passed payload inspection, isolated v17→v20 upgrade,
rollback, PowerShell/CMD command resolution, frozen Windows pseudoterminal launch/theme
restart/exit and uninstall preservation. It has not replaced the user's installed v17.
All 337 baseline protected files and original ledger/accounting rows remain unchanged.
Live-provider/Moss compatibility remains pending separate authorization; no live calls,
paid operations, deployment, staging, commit, push, tag or publication occurred.

See [the complete twelve-part report](verification/pass4-validation.md),
[canonical operator procedure](canonical-research.md),
[controlled corpus](../examples/canonical-research/PROTOCOL.md) and
[provider scope](provider-support.md). OneDrive backup publication produced an access error;
the isolated local backup/restore succeeded. Synchronized concurrent writers, general
binary-content secrecy, clean-machine/signing acceptance, broader modalities and text-model
branch continuation remain explicit limitations. README is reserved and untouched.

Historical reports below describe their own checkpoints; this section supersedes their
current-version and current-capability statements without erasing them.

# Terminal copy audit — November 1, 2026

Ordinary Help now explains DOXA actions without framework implementation notes. Theme Help
retains the original chooser callback, explains automatic saving and opens from Help.
Reference-only shell/shortcut entries and unavailable actions are explicitly distinguished.
The single-result Help panel is compact; terminal empty/launch/research-tool copy is corrected.
Final source: 333 tests, Ruff and strict mypy (90 files) pass; one existing warning remains.
Light/dark 80×24 and 120×40 renderings were visually inspected; frozen v17 interaction,
isolated v16→v17 upgrade, explicit rollback and uninstall passed. Installed v16 remains
unchanged. The NULL robot was not reproduced/identified and needs its original screenshot.
See [audit, exact text, package and limits](verification/terminal-copy-audit.md) and
[complete discovery inventory](verification/terminal-copy-inventory.md). README, credentials,
history and reservations are preserved; no live calls, push or Pass 4 work occurred.

# Installed terminal command — November 1, 2026

Terminal v16 is installed per-user with the stable `doxa` command. Source and bundled
entry points share the existing Typer/Textual application, including the accepted
theme-persistence fixes. Automatic CWD/ancestor workspace selection was removed;
the existing remembered workspace remains authoritative. Fresh Windows PowerShell
and CMD checks passed outside the repository; the bundled no-argument TUI and theme
restart passed in an owned Windows pseudoterminal. Isolated uninstall restored PATH
and preserved preferences, research history and an unknown export. Final source:
329 tests, Ruff and strict mypy (90 source files) pass; one existing Starlette warning.
README, credentials, original preferences, ledger/reservation contents and old archives
are unchanged. No live calls, dependency upgrades, push or Pass 4 work occurred.
See [installation verification and limits](verification/pass3-installation.md) and
[install/uninstall instructions](windows-installation.md). This is an unsigned
one-folder build, not manual Windows Terminal or clean-machine acceptance.

# Pass 3 reliability gate - November 1, 2026

Source theme changes now persist immediately and survive normal exit, forced process loss
and actual Windows console-window closure. Reproduced credential/control and JSON/JSONL
publication gaps are fixed. Process-death tests verify transaction rollback, detached worker
survival and conservative pending-call recovery without replay/release. An original-workspace
backup was restored outside OneDrive: 223 events, 291 records, 37 referenced artifacts
(39 stored files hashed), nine runs and all configuration/reservation rows match.
Final source: 322 tests pass; Ruff and strict mypy (91 files) pass. One existing Starlette
warning remains. Existing history, credentials, preferences and portable package archives
are unchanged. Frozen v15 does not contain this source fix; Open DOXA Source Terminal.cmd
opens the corrected existing app. README, storage map, recovery and provider matrix are written.
No live acceptance was authorized/performed. See the [gate report and precise limits](verification/pass3-reliability-gate.md).
No new provider/model/scientific feature or visual redesign was added. Historical reports follow.

# Pass 3 model-backed research - November 1, 2026

The existing controller/Textual worker path now supports an explicit bounded structured
research cycle with native OpenAI Responses/Chat, Anthropic Messages, Gemini generateContent
and compatible transports. Mock-provider acceptance covers multiple instances/profiles,
evidence, criticism, responses/revisions, context/authorization manifests, evaluation,
branch comparison and complete ZIP export. No live model/Moss/RunPod inference was performed.
Final source: 308 tests, Ruff, strict mypy (89 files), schemas/types and compatibility build pass.
Original 223 events/291 records/configurations/credentials/workspace preference and uncertain
Moss hold are unchanged. Current startup-help settings were retained; the saved guide position
changed while a concurrent v14 viewer was open (see preservation audit). v15 original-history/export/preflight and Windows PTY startup/exit
checks pass; v14 remains the fallback. Manual Windows Terminal/clean-machine acceptance is unverified.
See [precise scope, six-system boundaries and acceptance evidence](verification/pass3-model-execution.md).
No further development pass is started. Historical reports follow.

# Pass 2.7 model catalog and connection setup - October 31, 2026

Model-first terminal setup searches a sourced offline catalog or accepts any custom ID,
then offers conditional connection fields. Developer/family, connection and hosting are
separate. Existing text adapters are reused; unsupported native transports register notes
only. No inference backend, contract or migration was added. Canonical profiles/assignments
remain versioned in SQLite; descriptive notes are non-authoritative UI metadata. Existing
workspace selection disables creation. Final checks: 262 tests, Ruff, mypy (84 files) pass.
v14 packaged catalog/custom save/guide return/exit and all nine export comparisons pass;
v13 remains the fallback. Original records/configurations/accounting/credentials are unchanged;
the startup preference predates this request and was retained. The Moss hold is untouched.
See [Pass 2.7 report, sources, captures, artifact hash and limitations](verification/pass27-model-catalog.md).
No live inference was tested. Unsupported transports, model-specific fixed-request compatibility,
canonical identity review and authorized readiness tests remain separately scoped Pass 3 work.
Manual novice/Windows Terminal/clean-machine and cold-start timing acceptance remain unverified.
Pass 3 is not started. Historical status follows.

# Pass 2.6 navigation and onboarding - October 31, 2026

Getting Started now distinguishes existing research, general experiment setup, optional offline
simulation and help. Child forms preserve the guide and step on save/cancel/Escape; nested
help and F1 reopening retain context. Execution mode is explicit. Agent fields are labeled,
scrollable and have fixed actions; new web permissions remain off and prior settings unchanged.
The controller supports new attempts under an immutable experiment, but that dedicated TUI
operation remains future work. Final checks: 253 tests, Ruff and strict mypy (82 files) pass;
v13 ConPTY action/return/focus/exit and all nine export comparisons pass. All 223 original
events, 291 records, accounting, credentials and personal preferences are preserved. v12 remains
a fallback. See [Pass 2.6 findings, captures, artifact hash and remaining gaps](verification/pass26-terminal-navigation.md).
Manual novice/Windows Terminal/clean-machine acceptance is unverified. The historical $1 Moss
hold remains uncertain; no live/paid service was contacted. Pass 3 is not started.
Historical status follows.

# Pass 2.5 terminal cleanup - October 31, 2026

Getting Started now opens at three compact task choices with prerequisite-ordered offline
instructions and explicit unavailability reasons. F1 defaults to common research actions;
all reference entries remain categorized/searchable. OneDrive precautions and readable
recovery accounting are visible. The historical $1 Moss reservation remains held, billing
unknown. No backend semantics or credentials changed. Final checks: 243 tests, Ruff and
strict mypy (81 source files) pass. Portable v12 startup/exit, remembered preferences and
all nine controller/export comparisons pass; v10 is preserved. Manual novice/Windows Terminal
and clean-machine acceptance remain unverified. [Pass 2.5 report](verification/pass25-terminal-cleanup.md)
records exact evidence, the resolved packaging lock and remaining limits. Pass 3 has not started.
Historical status follows.

# Pass 2 usability — October 31, 2026

The existing Textual client now has a skippable first-launch guide, shared contextual actions,
searchable F1 reference derived from real commands/bindings, bounded chronological activity
operations with exact event expansion, complete event-field search/paging and state-specific
guidance. Final source: 236 tests, Ruff and strict mypy (81 files) pass. See the
[Pass 2 report and recorded views](verification/pass2-terminal-usability.md).
No provider/backend research semantics changed. Pass 3 has not started. Historical sections follow.

# Pass 1 stabilization — October 31, 2026

Workspace selection and backend reliability have been audited and corrected. The project
ledger remains intact (9 runs, 223 events). Final source: 223 tests, Ruff and strict mypy
(78 files) pass. See [Pass 1 findings, verification, recovery limits and Pass 2 boundary](verification/pass1-stabilization.md).
Pass 2 has not started; GUI development remains frozen. Historical sections follow.

# Terminal-first corrective pass — October 25, 2026

The existing Textual app is the primary human interface. Active Studio/native desktop
UI development is frozen; their sources and archived builds are preserved. The controller,
canonical SQLite ledger, permissions and six research systems remain shared. See
[terminal-first setup and precise boundaries](terminal-first.md).

| Category | Current scope |
| --- | --- |
| Implemented and demonstrated | Compact experiment-first terminal, inspectors/filtering/palette/help, workspace selection, masked DPAPI credentials, versioned model/template configuration, synthetic and authorized model-backed worker launch, evidence-linked review, branching/comparison/memory/export. Full offline terminal interaction and mocked compatible inference tests pass. |
| Implemented, not live-verified | Native remote inference, local compatible runtimes, Moss retrieval, endpoint metadata discovery, optional structured model research actions. No actual provider inference/discovery or paid call was made for this pass. |
| Contracts or unsupported features | Images, embeddings, provider-native function calls and streaming are not implemented by current text adapters. GGUF/repository registration records provenance only; it does not execute weights. Direct LiteLLM SDK integration is not implemented. |
| Remaining acceptance and research limits | Real authorized provider/runtime tests, clean-machine/Windows Terminal manual acceptance, citation entailment and independent verification for open-ended debates, continued model execution on text-analysis forks, broader corpus/runtime/model-import support. |

Original Moss credentials remain in the original root .env. Workspace resolution uses
that file in place; no rotation or replacement was performed. Historical status sections
below describe earlier stages and do not supersede this terminal-first direction.

# Research workbench and desktop preview - updated October 25, 2026

The local-first workbench now has instance-based Councils, versioned text-debate tasks,
scoped sources/context manifests, guarded native GPT/Claude text adapters, ledger SSE,
Textual monitoring/revisions and a redesigned Studio. A pywebview Windows one-folder
preview bundles the production UI, Python runtime and Alembic migrations. See
[workbench setup and limits](workbench.md) and [baseline audit](workbench-audit.md).

| Status | Precise scope |
| --- | --- |
| Implemented and verified | Previous workbench/provider safeguards plus branch-scoped human claim/challenge/response/adjudication commands; rubric/pairwise annotations; integrity-checked text checkpoints and analysis forks; persistent FTS5 cache; bounded PDF/DOCX ingestion preserving originals; disabled-by-default agent tool loops tested offline; incremental local Moss session snapshots tested with SDK-shaped mocks; terminal setup/import/start/cancel/review controls; readable common CLI commands with --json; continued post-run SSE; v3 frozen CLI/TUI/PDF/DOCX/native-window acceptance and 0002→0003 history-preserving upgrade. |
| Implemented, not live-tested | Native GPT/Claude/Runpod inference; optional Moss semantic retrieval and snapshot API integration; pinned HTTPS fetch. Durable allowances/reservations and canonical eligibility remain mandatory. |
| Blocked by external setup | Live research requires exact selected models, applicable credentials, enabled profiles, allowances and explicit authorization. A live search provider and its pricing are not selected. Clean-machine/other-Windows-version certification requires a separate machine; signing requires a certificate. |
| Remaining release work | Automatic structured debate criticism/adjudication and richer citation validity metrics, corpus selection across experiments beyond the reusable local index, live provider/search acceptance, and clean-machine desktop certification. Text checkpoint continuation is human analysis only. The portable distribution is unsigned; no installer or auto-updater is claimed. Generated-code execution remains disabled pending an enforced container runner. |

This is an operational desktop **preview**, not completion of the entire requested
research-workbench release. General debate is a bounded text protocol, not the cache
oracle or a fully implemented general-purpose Council research system. Existing cache
research commands and tests remain available. No six-system algorithm was replaced.
No paid inference, deployment, research web-tool request or GitHub push was performed in this task.
The Studio acceptance demonstration adds one explicitly synthetic run to the canonical
project ledger. Packaging/test workspaces are disposable acceptance fixtures, not services.

The earlier sections below are historical and remain for provenance.

# Backend infrastructure hardening - October 24, 2026

The optional provider registry, local readiness/configuration reports, guarded RunPod
and explicit HTTPS compatible inference adapters, atomic provider outcome/accounting,
operator recovery/reconciliation, concrete finite TaskEnvironment port, CLI commands
and Studio readiness/assignment views are implemented. See [Windows setup and RunPod
handoff](windows-setup.md) and [verification](verification/backend-completion.md).

Live inference remains untested and disabled in this installation. No endpoint, model
or credential was invented, and no paid request or deployment occurred. The current
ledger has three offline agents and no configured model profiles. WSL is not installed;
Docker/Podman are unavailable. Generated source execution therefore remains disabled.
The six-system algorithms, Memory Tribunal rules and Moss adapters were preserved.

The earlier stage descriptions below are historical, superseded where the current
infrastructure handoff or research-system handoff documents tested functionality.

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
