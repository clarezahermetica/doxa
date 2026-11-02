# Pass 2.6 - Getting Started and terminal navigation

October 31, 2026. This is a terminal-only usability pass. Pass 3 is not started.
Existing Pass 1, Pass 2 and Pass 2.5 reports, captures, histories and portable fallbacks
are preserved. No controller, contract, migration, provider or research-system code changed.

## Navigation defect: reproduction and correction

Before editing, an actual 80x24 Textual interaction test opened Getting Started, selected
the offline workflow, entered Add agent template and canceled. It failed because the active
screen was the default workspace rather than the original GettingStarted instance. The
private reproduction log is .doxa/pass26-reproduction.log.

Root cause: GettingStarted.finish(action) dismissed the guide before handing the action to
the application. Its workflow/step were lost; reopening constructed a fresh home screen.
Child forms also lacked a shared Escape binding. Application-level Escape alone does not
cross Textual's modal binding boundary.

The guide now remains mounted beneath child dialogs. One ClientModal base supplies ordinary
Escape cancellation for existing forms. Save/cancel/Escape dismiss the child, and the guide's
ScreenResume handler refreshes current availability and returns focus to its action or useful
alternative. Select dropdowns consume their own Escape first. No child action saves/resets the
startup preference. A small in-memory location retains workflow, step and chosen execution
mode when closing/reopening the guide in the same viewer; a fresh application opens at home.

Home explicitly returns to Getting Started home; Previous moves one step back, and Previous
at step one returns home. Escape on the guide closes it to the workspace; F1 / Getting Started
reopens its location. Inspect intentionally opens the main workspace, with that guide location
retained. F1 works inside forms; choosing Getting Started from nested Help unwinds child
screens after Help dismisses, rather than duplicating or losing the guide. Startup checkbox
semantics and the existing preference-file format are retained.

## Product introduction and execution choice

Before: three home choices, with the general creation entry identified as an offline experiment.
After: four explicit choices: Open existing research; Create a research experiment;
Try an offline demonstration; Commands and help.

Existing research opens a real persisted-run selector and then the existing inspector.
General setup explains workspace selection, execution/runtime configuration, agent templates
and pinned assignments, question/composition/protocol/limits, evidence, tool permissions,
launch authorization, inspection and export. It routes to existing operations only.
The offline path retains the validated seven-step synthetic configuration-to-export workflow.

General setup and the direct experiment form require an explicit execution-mode choice.
Model-backed research remains live configuration when models are missing; launch is blocked
with a concrete prerequisite message. It is never silently converted to synthetic output.
The offline entry explicitly selects synthetic mode. Saving a model or experiment is not
launch authorization or proof of successful inference. The guide is provider-agnostic and
adds no adapter, model capability, service or internet access.

## Dead ends, context and lifecycle findings

Selected completed/failed/running runs retain controller restrictions. An unavailable primary
action has an adjacent explanation, an experiment selector and a usable configuration action
(open workspace, add a template, or create research). Existing completed history remains
inspectable. Creating from the guide selects the returned run ID and resets only the viewer's
branch/inspection cache, so later imports/start apply to the intended newly configured run.
Current selected state is refreshed on return and while viewing a step.

The earlier instruction that a new experiment is required for every new run was too broad.
Controller.configure_run accepts the same immutable Experiment with a new idempotency key,
creating a distinct configured Run/root trajectory. A regression test confirms that the old
completed run and experiment bytes remain unchanged. The current terminal creation form
creates a new experiment plus its first run; it has no reusable-configuration retry form.
Current wording therefore offers a configured run or new research and never replays a
completed run. A dedicated new-attempt UI is a future capability, not implemented here.

## Agent form and web-permission audit

Visible labels/help now identify name, instructions, role, model assignment, enabled status,
memory scope and tool permissions. Role and model are explained separately; multiple
same-role participants may share or use different models. Private memory is owner-only;
shared memory is available to other eligible participants subject to approval/branch rules.

Fields scroll independently of a fixed Create/Cancel row. Tab moves from name to instructions
to role; selection menus use Space/arrows and Escape. A new guide Add action always creates
a template, even if an existing template was selected in the workspace inspector.
Version editing remains explicit and preserves prior immutable records.

Actual new-template defaults are enabled, unassigned model, private memory, and neither
web_search nor web_fetch selected. These tool defaults were already least-privilege before
this pass. Existing forms use persisted settings; tests verify explicit opt-in/versioning
and unchanged old records. A screenshot without its source record cannot establish otherwise.

Tool permission only allows a request. Configured/available tools, experiment policy and
explicit run disclosure/spending authorization remain separate gates. No external request
is made by onboarding, model registration or tool permission selection. The complete offline
acceptance asserts no model calls, tool-audit records or paid reservations.

## Captures and acceptance

Actual headless Textual SVG captures are private under .doxa/pass26-ui-acceptance/, at
80x24, 120x40 and 160x50: home, research-mode, guide-before-child, agent-fields,
agent-permissions, guide-after-cancel and guide-after-save. verification.json records
return to the identical guide instance at step 2 after cancel, Escape and save. These are
Textual renders, not manual Windows Terminal screenshots or novice-user certification.

New regression cases cover the original failing path; repeated save/cancel/Escape; workspace
cancel; same-step focus; startup preference and F1 reopening; Home/Previous behavior;
completed-run alternatives and correct new-run selection/import; explicit live/synthetic
separation; missing assignments without inference; blank-mode rejection; immutable experiment
reuse for another attempt; keyboard/forms/defaults/persisted permissions at three sizes;
nested Help and existing-research selection. Existing configuration-to-export acceptance
remains, updated to navigate back through the mounted guide and choose execution explicitly.

Final checks and packaged acceptance are appended after completion.

## Exact changed files in this pass

- src/doxa/cli/onboarding.py: four-entry home, general and offline workflows, retained child
  navigation, persisted-run selection, precise availability/alternatives and refreshed focus.
- src/doxa/cli/navigation.py: shared dialog Escape cancellation.
- src/doxa/cli/screens.py: labeled/scrollable agent form, fixed actions, explicit execution
  selection and returned created-run identity; same controller commands/contracts.
- src/doxa/cli/console.py: guide location, new-run selection, corrected lifecycle wording,
  nested-guide return and context-wide F1 handling.
- src/doxa/cli/reference.py: updated introduction and reference coverage for the run selector.
- src/doxa/cli/operations.py, workspace_screen.py, inspectors.py, research_tools.py: adopt
  the shared cancellation base, without changing their controller/provider operations.
- tests/test_pass26_terminal.py: targeted interaction and lifecycle regression tests.
- tests/test_pass2_terminal.py, test_pass25_terminal.py, test_terminal_first.py,
  test_text_research.py: preserve existing assertions with new return/mode-selection paths;
  strengthen offline acceptance with no tool-audit/paid-operation assertions.
- scripts/build_terminal.ps1, Open DOXA Terminal.cmd: separately verified v13 target.
- docs/status.md and this report: current scope, evidence, lifecycle findings and limits.

## Remaining gaps and boundaries

Pass 3/future capability work: a terminal operation for another run under an existing
configuration; richer model/runtime setup and readiness diagnostics if separately scoped;
existing scientific limits on citations, model-backed fork continuation, corpus scope,
modalities and tool providers. No unavailable feature is presented as operational here.

Manual acceptance work: novice comprehension, longer researcher sessions, actual Windows
Terminal/PowerShell human review, clean-machine and other-Windows-version distribution
acceptance. The portable build remains unsigned; no signing/publication was requested.

The historical Moss $1 upper-bound reservation remains reserved/uncertain, billed amount
unknown. No retry, release or settlement is performed. OneDrive precautions remain; no
workspace is moved/merged. Original credentials and all existing histories are preserved.
No live model/Moss/RunPod call, paid operation, research browsing, deployment or push occurs.
Stop after Pass 2.6; Pass 3 requires a separate instruction.

## Final verification and release artifact

- Final full-source suite: **253 passed**, one pre-existing Starlette/httpx TestClient
  deprecation warning, 356.71 seconds. Ruff passes; strict mypy passes **82 source files**.
  Ten new regression cases are included; existing tests and full offline acceptance remain.
- Packaged Windows PowerShell ConPTY at 80x24: four-entry home, offline step 1, step 2,
  Add agent template, Cancel returning to step 2; Enter reopening the child through restored
  focus; Escape returning to the same step; Ctrl+Q exiting with code 0. The cancel path that
  failed before the fix now passes in source and the separate frozen executable. No form
  was saved into the user's real workspace during the packaged smoke test.
- All nine packaged CLI exports exactly match direct-controller records. All original event,
  record, configuration, reservation and operation rows match the before snapshot: **223
  events and 291 records** remain. Original .env, encrypted credentials, README and personal
  workspace/startup preference files have identical hashes. The $1 Moss reservation remains
  held with unknown billing. Integrity/export checks reference the same canonical workspace.
- All 137 packaged files and 186 publishable project files were scanned for configured
  secret values: zero findings. No workspace, .env, credentials, history, private acceptance
  captures, node_modules, Studio or WebView is embedded in the application.
- The v12 executable/folder and v12 ZIP are preserved. The fallback ZIP retains its exact
  Pass 2.5 hash. The project launcher and build script target the separately versioned v13.
  The bare portable executable continues using shared workspace preferences; the project
  launcher explicitly selects the project's .doxa directory. No workspace was moved/merged.

[Before opening the child](../../.doxa/pass26-ui-acceptance/guide-before-child-80x24.svg) ·
[Returned after Cancel](../../.doxa/pass26-ui-acceptance/guide-after-cancel-80x24.svg) ·
[Returned after Save](../../.doxa/pass26-ui-acceptance/guide-after-save-80x24.svg) ·
[Research execution choice](../../.doxa/pass26-ui-acceptance/research-mode-80x24.svg).
These are genuine headless Textual captures; packaged acceptance is separately recorded in
.doxa/pass26-packaged-navigation.json. Manual Windows Terminal/novice/clean-machine testing
is still not claimed.

Artifact: dist/DOXA-Terminal-Windows.zip, v13 application (top-level DOXA folder).
Size: 35,801,174 bytes.
SHA-256: 9d6bdd9c2184b3644fe4c662100f9baf5ee50af8079b74825d56f6319000c666
Executable: dist/DOXA-Terminal-v13/DOXA/DOXA.exe.
No live inference, Moss/RunPod contact, paid calls, deployment, signing or GitHub push occurred.
Pass 2.6 is complete within the stated automated acceptance scope. Pass 3 is not started.
