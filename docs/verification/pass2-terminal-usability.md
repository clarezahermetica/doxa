# Pass 2 — Terminal usability and discoverability

October 31, 2026. This pass extends the existing Textual ResearchConsole. It does not change
controller research semantics, ledger contracts, migrations, spending/recovery controls or
provider adapters. Existing GUI sources/builds remain frozen. Pass 3 is not started.

## What changed

- First launch offers a short, skippable seven-step Getting Started guide: workspace,
  experiment, agents/assignments, evidence, offline execution, inspection/review and export.
  It explains that templates are needed before creating a Council experiment and that
  assignments are pinned at creation. Existing model forms are described, not redesigned.
  Synthetic output is explicitly distinguished from live inference and verification.
- The guide's launch checkbox and last viewed step are stored atomically in the operational
  LocalAppData/DOXA/terminal.json preference file. They contain no research records, credentials
  or experimental decisions. Missing/corrupt preference files are tolerated. Dismissing the
  first guide disables repeat display unless the checkbox is enabled. F1 → Getting Started
  always reopens it. W/recent workspace selection remains the Pass 1 implementation.
- One contextual Actions selector plus Open replaces a footer crowded with shortcuts.
  Shortcuts remain available and documented. F1 and Ctrl+P expose ordinary operations without
  memorizing letter keys. The experiment list highlights the actual selected experiment;
  persisted run states update in the table. Narrow windows reduce the list height.
- Activity is a chronological table of bounded adjacent operations/turns. Actor, action,
  result and origin are primary; UUIDs and JSON are not. Adjacent claim turns can group
  context/call/message events. Claims end groups. Criticism, responses, revisions, decisions,
  verification and failures remain separately inspectable. Groups never reorder events and
  have a fixed maximum size to prevent quadratic growth on long histories.
- Search scans all committed event fields in the selected branch history, including ancestors
  and entries outside the initial page. Earlier/Later expose every operation in 100-row pages.
  Search includes record text/metadata, not arbitrary full-text contents of referenced files.
  The existing evidence/retrieval infrastructure is unchanged.
- Enter expands an activity operation into readable original-record details, provenance,
  causal parents, exact model/call assignments, evidence links and versions. The original
  typed events button and Ctrl+J expose exact event JSON. Inspect supports F2/Expand record
  for readable detail, with Ctrl+J retaining exact record access. Long previews show an ellipsis.
- State-specific action availability explains missing workspaces/experiments, configured,
  running, terminal and unsupported setup states. A historical running status is never treated
  as proof of a live worker: the UI reports observed local OS ownership or explicitly unverified
  activity. Uncertain operations expose read-only Recovery details and the existing guarded
  shell commands; they are never automatically released or replayed.
- Synthetic Start hides irrelevant paid authorization inputs and labels the fixture clearly.
  Existing live authorization and model configuration forms retain their original controls.

## Help and command-reference coverage

F1 is the single searchable reference; Ctrl+P is the existing executable palette. The same
ActionSpec registry supplies the contextual menu, palette and terminal-action descriptions,
required form context, examples, restrictions and unavailable-state explanations. Help also
lists currently registered Textual built-in palette commands.

Keyboard references are derived from the actual inherited binding registries for the app,
all focused control classes used by its forms and its modal screens: tables, text inputs,
read-only text areas, selectors, tabs, buttons, checkboxes, selection lists, collapsibles,
scroll containers, guide, reference, operation detail, workspace/setup/review/import/start/
model/retrieval/export dialogs. Focused-widget bindings are explicitly contextual.

All 49 registered Typer command/group paths are traversed from the real command registry,
including compatibility commands. Argument names, types, required flags and options are
read from the actual parameter definitions. CLI callback docstrings now provide meaningful
shared descriptions for both shell help and F1. Examples use clearly identified placeholders.
Shell entries cannot execute inside the TUI. Native Typer rich help is not printed during
reference construction, avoiding corruption of the active terminal display.

## Recorded interaction states

The acceptance descriptions below refer to actual Textual interaction tests using synthetic
fixtures, not live model activity:

| State | Visible behavior and appropriate next operation |
| --- | --- |
| First launch | Compact Getting Started 1/7; Next/Previous, one operation button, launch preference and Skip/close. Escape dismisses; F1 can reopen it. |
| No workspace | Existing workspace selector or explicit empty-directory creation. No history is silently created or merged. |
| Empty workspace | No runs message with canonical path and W guidance. Configure agents/experiments or open an existing workspace. |
| Configured synthetic experiment | Selected name, configured/synthetic labels. Import evidence and Start available. Start explicitly identifies offline fixtures. |
| Historical running without owned lock | Historical running / worker activity unverified. Inspect activity and Recovery details; no assumption of active remote execution. |
| Owned running worker | Running / local worker owned. This is an ownership observation, not proof of remote progress or correctness. Viewer exit does not cancel it. |
| Uncertain operation | Uncertain operation warning with Recovery details. Unknown billing remains held; no replay/release button bypasses the controller. |
| Completed | Readable operation history and inspections, review/evaluation/export; Start and Cancel are unavailable. |
| Failed/cancelled | Persisted outcome remains explicit. Inspect original events and guarded recovery instructions; no silent retry. |
| Missing/unsupported model/task setup | Configuration unavailable message and Inspect/Help guidance. No model is substituted and no inference is dispatched. |
| Long histories/content | Bounded rows, complete event-field search and chronological pages. Enter opens scrollable details; resizing preserves navigation. |

## Acceptance and verification

The new-user acceptance follows the guide at 80×24 through explicit workspace creation,
agent creation, a two-instance experiment, Markdown evidence import, detached synthetic
execution, claim inspection and export. The resulting history is completed and contains
no ModelCall. Separate interaction tests cover skip/reopen/repeat preference, checkbox Space,
F1 search, table focus/Enter, Ctrl+P navigation, raw typed-event expansion, Earlier/Later,
missing model state, owned/unowned workers and uncertain-operation guidance.

Existing acceptance retains claim revision, evidence links, checkpoints, branches, comparisons,
memory, export, CLI compatibility, budget/recovery and original-history preservation. Tests
exercise 80×24, 120×40 and 160×50, long experiment names and claim content, 621 activity rows
and a 1,050-claim history with searches beyond the display window. Projection reads occur in
background workers; row rendering is bounded. No new scientific engine or database exists.

Final source checks and packaged acceptance are recorded below after completion.

## Known usability limits and Pass 3 boundary

- Search is case-insensitive substring search over committed event/record fields and metadata.
  It is not semantic/full-document search. Existing artifact previews retain their current
  size bound; exact event JSON preserves references to canonical full source artifacts.
- The client loads a run's persisted events to construct its view. Rendering is bounded,
  but very large ledgers still incur linear read/projection cost. No million-event benchmark
  or distributed/multi-host workspace support is claimed.
- Short operation previews require Enter/Expand for full context. Unmapped historical actor
  identities remain generic participants, with exact identity available in original events.
- F1 availability is a presentation hint. The deterministic controller remains authoritative
  and can reject an action if state or authorization changes while a dialog is open.
- CLI introspection uses the installed Typer parameter types and pinned Textual bindings.
  Future framework upgrades must rerun coverage tests. Shell-only advanced recovery and
  compatibility commands remain shell-only; Help does not execute arbitrary shell text.
- Manual Windows Terminal, clean-machine, signing and extended human usability certification
  remain distinct from Windows headless Textual and PowerShell ConPTY acceptance.

Before Pass 3, retain the passing full suite and review the recorded interactions in the target
user terminal. Remaining manual work is Windows Terminal/PowerShell human acceptance at laptop
sizes and longer real-workspace sessions. There are no new provider capabilities in this pass.
Pass 3 model/provider configuration work requires a new instruction; it is not begun here.
Broader scientific gaps recorded in Pass 1 (citation entailment, model-backed fork continuation,
cross-experiment corpus selection) are unchanged and must not be represented as completed.

No live inference, paid calls, live Moss, autonomous web research, deployment, GitHub push or
GUI development was performed. Existing credentials and historical records are preserved.

## Final source and captured-view verification

After the last application source change, the full suite passed **236 tests** in 159.25
seconds. Ruff passes and strict mypy reports no issues in 81 source files. The only warning
is the pre-existing Starlette/httpx TestClient deprecation. Thirteen new Pass 2 acceptance
cases were added; legacy non-onboarding tests explicitly suppress the guide rather than
writing personal preferences. No controller, storage or provider implementation changed.

The captured source-client acceptance opened the real, unchanged project workspace: all
nine persisted runs were visible. The selected branch's 22 canonical events appeared in
14 operation rows, with exact chronological identity preserved. At 80 columns the activity
column widths were 8/11/17/19/13, keeping actor/action/result/origin on screen.
The selected context uses three compact lines for the readable experiment name/kind, state
and canonical path. Event times retain canonical UTC; full timestamps are in detail.

F1 contained 259 searchable entries in the recorded context: 17 application actions, all
16 inherited/application bindings, focused-control/modal bindings, built-in palette actions
and all 49 registered CLI command/group paths. Coverage is checked against the real registries.

Actual Textual SVG exports and a machine-readable record are excluded from Git under
.doxa/pass2-ui-acceptance/: guide-80x24.svg, activity-80x24.svg, activity-120x40.svg,
help-120x40.svg and verification.json. These are headless Textual renders, not manual
Windows Terminal or desktop GUI screenshots. The capture used isolated UI preferences;
it did not dismiss the guide or alter the user's personal startup preference.

## Portable acceptance and preservation

The separate PyInstaller v10 console application opened the guide in PowerShell ConPTY
at 80×24, accepted Escape, displayed the remembered project history, opened F1 through
the actual terminal key sequence, and searched for doxa run start. The selected shell
entry displayed required RUN_ID, a usage example and explicit authorization restrictions.
Shell entries remained reference-only. Ctrl+Q exited cleanly. Isolated preferences were
used, so the user's own first-launch choice was not changed by automation.

Packaged CLI exports of all nine runs matched direct controller records. Workspace integrity
remained 223 events. All 137 packaged files and 181 publishable project files were scanned
for configured secrets: zero findings. Workspace/history/credentials, .env, node_modules,
Studio and WebView assets are absent from the bundle. Existing desktop artifacts are retained.
The previous v9 console folder/ZIP are retained; the project launcher now targets v10.

Portable ZIP: dist/DOXA-Terminal-Windows.zip
Size: 35,788,621 bytes.
SHA-256: 1782500e95836c8bf423368ccf4755fab6ee28d3a2457e6626f8fedf646fd7f4

For portable shell examples, replace the leading doxa command with .\DOXA.exe or the
absolute executable path. The palette accepts action names, not arbitrary shell text.
Private acceptance metadata is .doxa/pass2-package-verification.json.
