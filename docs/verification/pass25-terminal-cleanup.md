# Pass 2.5 - Terminal usability cleanup

October 31, 2026. Extends the existing Textual app only. Pass 3 is not started.
No shared contracts, controller, providers, storage or migration implementations changed.
The Pass 2 report and portable v10 build remain preserved as historical acceptance evidence.

## Changes and recorded interaction states

- Getting Started now opens at three task choices: explore existing experiments, create an
  offline experiment, or browse commands/help. The home panel fits within 20 rows at 80x24.
  Escape dismisses it; F1 / Getting Started reopens it. The startup checkbox retains the
  same operational preference file and meaning; no workspace preference is reset.
- Only choosing the offline workflow opens short action/result instructions, in prerequisite
  order: workspace, agent templates, experiment, evidence, synthetic start, inspection, export.
  Each view supplies the implemented operation. Existing templates may be reused. The actual
  experiment form defaults to synthetic; leave Model-backed unchecked. No model/key is needed.
- Unavailable guide operations have an adjacent explanation. Missing templates are identified
  before creation. Configured synthetic experiments can start; completed/failed/running runs
  cannot start again. Create a new experiment to obtain a new configured attempt. Live or
  unsupported model setup is explained, and this guide never starts live inference.
- F1 initially lists common research actions, rather than hundreds of widget/shell bindings.
  Its category selector separates Getting started; Experiments and runs; Agents and models;
  Evidence and retrieval; Claims and revision; Evaluation and export; Workspace and maintenance;
  Advanced CLI commands; and Application and widget shortcuts. All commands remains available.
  Typing searches the entire reference across categories, including CLI arguments and limits.
  Descriptive operation titles are shared by the palette, help and contextual action picker.
  F1 and Ctrl+P are preserved. Shell entries remain reference-only.
- Existing validation, immutable history, actual-state action checks, activity inspection,
  guide skip/reopen/startup preference and complete offline configuration-to-export workflow
  remain covered. Guidance is a presentation aid; every operation retains controller checks.

## Operational loose ends

**OneDrive:** the current project workspace is beneath OneDrive. The selected experiment's
status includes a synchronization marker; W opens explicit precautions. The workspace selector
also updates the warning when a path is edited. Avoid simultaneous use on different machines,
remote replacement or synchronization-conflict restoration of open SQLite files. Sync is not
an application-consistent database backup. No workspace was moved or merged.

**Historical Moss timeout:** a read-only query confirms one reservation, upper bound $1.00,
with billed amount null and reservation status reserved. Its Moss operation remains uncertain.
The hold remains unresolved; timeout does not establish a charge or absence of a charge.
No release, retry, settlement, credential change or service contact occurred. Actual outcome
and billing evidence are required before a separately authorized reconciliation. This does
not block offline work; it remains relevant to future paid-use readiness.

**Status and recovery:** historical running is distinguished from observed worker ownership;
uncertain activity points to Recovery details. Recovery presents readable labeled accounting
fields, renders null as unknown, and explains that a held amount is not a bill. Shell recovery
examples remain explicit, guarded operator operations. Nothing auto-replays or releases holds.

**Portable updates:** application files are separate from the remembered workspace path,
startup help preference, history and encrypted credential files. Replacing an application
folder does not migrate, initialize or copy these. Root .env credentials remain in place.
A portable application moved to another machine still needs the existing workspace and
appropriate credentials; Windows DPAPI credentials belong to the original Windows user.
Clean-machine and manual Windows Terminal acceptance remain unverified.

## Files changed in this pass

- src/doxa/cli/onboarding.py: compact task home, concise offline guidance and availability reasons.
- src/doxa/cli/reference.py: common-task default/category browsing and descriptive action names.
- src/doxa/cli/console.py: OneDrive marker and readable recovery/accounting explanation.
- src/doxa/cli/workspace_screen.py: synchronization precautions for selected/edited paths.
- tests/test_pass2_terminal.py: navigate the new home and corrected prerequisite order while
  preserving the complete guided offline acceptance and startup preference coverage.
- tests/test_pass25_terminal.py: targeted home/category/state/prerequisite/sync interaction cases.
- scripts/build_terminal.ps1 and Open DOXA Terminal.cmd: target the separate verified v12 build.
- docs/status.md and this report: current status, preservation evidence and remaining boundaries.

## Remaining work before Pass 3

Manual novice/laptop-terminal review and longer real-workspace sessions remain useful acceptance
work; automated interaction tests do not certify a novice's subjective understanding. The
historical Moss accounting hold requires evidence before paid-use reconciliation, not an
inference from this audit. Clean-machine portable acceptance and signing remain unverified.
No backend defect requiring modification was identified in this targeted cleanup. Broader
research/provider gaps recorded in earlier reports remain unchanged. Pass 3 requires a new
instruction and is not begun automatically.

Final test and portable acceptance results follow below.

## Final verification

- Full final-source regression suite: **243 passed, one pre-existing Starlette/httpx warning**,
  206.90 seconds. Ruff and strict mypy pass (81 source files). Seven new interaction cases
  cover home/category discovery, four run states, missing-template guidance and sync precautions.
- Initial combined test/build run exposed an asynchronous test wait that could inspect stale
  search rows. The test now waits, with a timeout, for the filtered visible result; the original
  exact-result, event identity and pagination assertions are retained. The final full run passes.
- Existing headless 80x24 / 120x40 / 160x50, resizing/long-history and complete offline
  configuration-to-export checks pass. Updated 80x24 home and activity, 120x40 activity/help
  SVG captures and counts are private under .doxa/pass25-ui-acceptance/.
- Source capture saw all nine existing runs; canonical branch events retain exact order and
  identity. F1 retains 259 entries, including all 49 CLI paths and 17 terminal actions.
- The v12 packaged executable opened from a temporary working directory in PowerShell ConPTY,
  displayed the three-choice guide, accepted Escape, showed saved history and OneDrive notice,
  opened F1 with 17 common actions and searched across categories for doxa run start. Ctrl+Q
  exited cleanly. A separate launch honored an existing startup-help=false preference and
  remembered workspace. Preference and credential-file hashes remained unchanged.
- All nine packaged CLI exports exactly match direct-controller records. All event, record,
  configuration, reservation and operation rows match the preservation snapshot; 223 events
  remain. Original .env bytes remain unchanged. No experimental records were added to the
  user's workspace by acceptance testing.
- The fresh v12 output avoids an observed OneDrive WinError 5 while replacing intermediate
  v11 output. v10 executable/folder and its ZIP remain preserved. No workspace was relocated.
- No configured secrets were found in 137 packaged files or 183 publishable project files.
  No workspace, credentials, .env, history, node_modules, Studio or WebView is bundled.
  No live inference, service contact, spending, deployment or GitHub push occurred.

Portable artifact: dist/DOXA-Terminal-Windows.zip (v12).
Size: 35,792,231 bytes.
SHA-256: ad982195ad29f4399ee57852a2306bcb936b434da606991b583a8d3087352ea7.
The project launcher targets its explicit project workspace. Bare DOXA.exe honors remembered
workspace selection; installing into a different directory does not select an empty workspace.
Manual Windows Terminal, real novice, clean-machine and signing acceptance are not claimed.
