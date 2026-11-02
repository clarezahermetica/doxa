# Terminal copy and Help audit — November 1, 2026

## Scope and outcome

Reviewed Getting Started, workspace/home, F1 and Ctrl+P, model/provider and agent setup,
experiment creation/launch, live activity/status, evidence, claims/criticism/revisions,
evaluations/comparison, memory, recovery, export/backup references, preferences and
errors/empty/disabled states. This changes interface language and the small Help
callback/layout defects described below, not research contracts or algorithms.

The [complete discovery inventory](terminal-copy-inventory.md) retains all **212 original
keyword-search hits**, with source locations and dispositions, including code matches that
were never user text. The fifteen-area review and findings outside those keywords are
also recorded there. The list is discovery evidence, not 212 defects.

| Classification | Initial hits |
| --- | ---: |
| Internal APIs/code, not displayed | 90 |
| Output statements whose displayed text was reviewed separately | 75 |
| Source documentation/docstrings | 4 |
| Intentional input hints (`placeholder=`) | 21 |
| Invocation/argument examples | 8 |
| Advanced unknown-cost disclosure | 1 |
| Connection verification limitations | 3 |
| Legitimate technical/scientific terminology | 5 |
| Framework wording in ordinary Help | 5 |

No actual unfinished TODO/FIXME/TBD/coming-soon/dummy user copy was found. Blank error,
summary and status labels are populated dynamically; they are not unfinished screens.
Input hints and example commands are intentional. `Select.NULL`, `DEVNULL`, framework
imports and internal variable names are code, not text to replace. “Unknown is null” is
an accounting explanation in advanced recovery details; it does not describe a graphic.
Tests, fixed-response demonstrations and historical provider/model output were not renamed
as live or independently verified research.

## Rewrites

| File/area | Before | Result |
| --- | --- | --- |
| `reference.py`, application actions | “Textual action” and controller implementation note | “In-application action”; availability/prerequisites; earlier versions are preserved |
| `reference.py`, shortcuts | Framework labels, Python widget class/action names | Application shortcuts and familiar names such as Tables, Text fields, Text panels, Help and Branch review |
| `reference.py`, application commands | “Textual built-in command … Availability is supplied by Textual” | Purpose and invocation; original command callback retained |
| `reference.py`, CLI root/groups | Generated name-only summary | Console entry, experiment creation and recorded-run supervision summaries |
| `console.py`, palette commands | Generic Theme/Quit/Keys/Screenshot descriptions | Saved appearance; viewer-only exit; focused-control help; SVG screenshot and research-data disclosure |
| `main.py`, four empty/inspection states | Direct users to Studio | Existing terminal actions or CLI alternatives |
| `onboarding.py`, offline guide | “synthetic fixtures” | “Responses are simulated, not live inference or verified conclusions”; no-paid-service explanation retained |
| `operations.py`, launch | “Local: no paid API. Remote: both authorizations…” | Configured model connections; explicit remote disclosure, paid-call authorization and spending limits |
| `operations.py`, synthetic launch | “Offline synthetic fixture” | “Offline synthetic demonstration”; no live inference/paid calls retained |
| `research_tools.py` | One-word headings and “Run operation” | Compare trajectories, Search eligible memory, Request metadata or Check readiness, with relevant inference/network/spending context |
| `workbench.py`, exposed CLI docstring | “existing Textual application” | DOXA research console in the selected workspace |

Model transport/capability terminology, unverified endpoint/model status, disabled unsupported
connections, credential-reference warnings, role/model separation and immutable-history
language remain where they convey a real constraint. Criticism, revision, LLM evaluation,
deterministic verification and human annotation remain distinct. Unknown costs are not zero.
Remote retrieval and model-backed experiments retain their existing permission/budget gates.
Backup and restore remain explicitly shell commands; this pass did not add terminal forms.

## Exact Theme Help text

```text
Theme

Change DOXA's color theme.

Press Ctrl+P, select Theme, and choose a color scheme.

Your selection is saved automatically.

Open action opens the same theme chooser. No model call is made.
```

The palette synopsis is “Change DOXA's color theme. Your selection is saved automatically.”
The actual stock theme identifiers are retained. No framework code, duplicate theme chooser,
appearance storage format or persistence implementation was changed.

## Disabled Open action: cause and correction

The reference copied built-in palette titles/help into `ReferenceEntry` but discarded their
callbacks. Its enablement check accepted only named DOXA actions. Theme therefore appeared
in search while Open action was disabled, despite working through Ctrl+P.

Reference entries now retain the existing `SystemCommand.callback`. Open action closes Help
and schedules that exact callback after the screen refresh. Named research actions keep their
existing dispatch/availability validation. No research validation is bypassed.

Shell commands and keyboard reference entries have no runnable callback and now say
**Reference only**. Their details describe where/how to invoke them. Unavailable research
actions remain disabled with the controller/client availability reason displayed. A button
does not claim to execute a shell command or perform a no-op.

## Oversized panel and NULL graphic

Help previously occupied 96% of the terminal's height and gave the result table all remaining
space. Filtering to one row did not shrink that table. The result list is now bounded to
3–8 rows, and the dialog follows the result count with a viewport cap; the detail area remains
scrollable and the action row stays visible. Column widths leave room for descriptions at
80 columns. A solid panel background improves separation from the dimmed workspace.

**The robot labeled NULL was not reproduced or identified.** There is no corresponding
terminal graphic, asset or displayed label in DOXA's source, and it is absent from all six
rendered views inspected in this pass. Code-level null sentinels/accounting nulls are not a
robot asset. No original screenshot containing that robot was attached to this request,
so its source and intent cannot be established. It was not removed or attributed to another
application without evidence. The original image is needed to finish that specific investigation.

## Verification actually performed

**Final suite: 333 passed**, one existing Starlette deprecation warning, 414.18 seconds.
Ruff passed for source/tests/packaging; strict mypy passed for 90 source files. An earlier
complete run also passed 333; the final run includes the last root/group-help wording.

Four new parametrized interaction cases exercise both light/dark themes at 80×24 and
120×40. They verify populated descriptions, no framework-specific ordinary instructions,
Theme search/current details, enabled original callback, actual chooser selection,
immediate saving/reconstruction, unavailable run reasons, shell reference-only behavior,
button visibility and compact single-result layout. Existing tests were updated to accept
real callbacks as executable actions and assert the revised simulation disclosure.
The existing offline workflow, launch-state, history, claims/criticism/revision, provider,
recovery, installation and theme-persistence tests continue to pass.

Visual inspection went beyond string assertions: six SVG snapshots from the actual Textual
renderer were opened and inspected: Theme in light/dark at 80×24 and 120×40, and shell-only
Help in light/dark at 80×24. All core Theme instructions and action controls were legible;
long advanced reference text is scrollable. Local evidence is in `.doxa/copy-visual/`.

The **actual frozen v17** was also launched through the isolated installed `doxa` command
in a fresh Windows PowerShell process and owned Windows pseudoterminal. F1, Theme search,
keyboard focus to Open action, the existing theme chooser, a dark-to-light change,
saved `textual-light` preference and clean `q` exit were exercised. These are not claims
of manual Windows Terminal testing or clean-machine acceptance.

## Distribution and explicit upgrade

The production installation remains **v16**, unchanged. The new candidate is:

- `dist/DOXA-Terminal-v17-Windows.zip`
- **35,883,505 bytes**, 143 entries.
- SHA-256: `5b7043bd4d9aca9d15d8124169263d16c3ec3d930733f66713468a32623db8c9`.

An actual isolated installation of the old v16 bundle was upgraded using the v17 installer.
PowerShell and CMD resolved the stable command to v17; help, version, legacy `--cli`,
workspace selection and the same nine-run history passed. Old v16 binary hashes and
preferences were preserved. Explicit rollback with the original v16 installer restored
the stable command to v16 and retained v17's directory. Uninstall then removed both owned
versions/shim and restored the exact test PATH/value kind while preserving an unknown export
and preferences. Isolation used the same Windows account with separate directories,
preferences and an HKCU test key, not a second Windows login.

To upgrade deliberately, close viewers/workers before changing the installation, extract
the new ZIP to a normal local folder outside OneDrive, and run from that extracted folder:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-DOXA.ps1 -AddToPath
```

Then open a fresh terminal host and verify:

```powershell
doxa --version
doxa
```

Expect `DOXA 0.1.0a0 (terminal v17)`. The existing per-user PATH location is reused, the old
version directory retained and the remembered workspace/theme preserved. No administrator
access is needed. To roll back deliberately, run the preserved v16 installer with the same
options. [Installation/removal details](../windows-installation.md) remain applicable.
No production upgrade was performed silently by this audit.

## Preservation and remaining work

Verified unchanged: README, credentials, historical table contents (223 events, 291 records,
five configurations, one reservation, one operation), older archives, and the installed v16
manifest/executable/every owned file. Integrity checks passed for 37 referenced artifacts.
The uncertain Moss reservation was not settled/released. The researcher's `rose-pine`
appearance preference predates this audit and was retained; it differs from the older
installation-task snapshot, so that older snapshot was not used to reset the preference.
Other saved preferences still match that snapshot. The v17 ZIP contains no forbidden
workspace/credential paths or known credential values from the environment file.

Remaining issues for later consideration, without starting Pass 4:

- Identify the NULL robot from the original screenshot; no origin has been established.
- Broader manual Windows Terminal/accessibility and clean-machine/signing acceptance remains
  outside the verification above. This is still an unsigned one-folder distribution.
- Full command reference remains extensive by design. Long technical CLI/JSON details and
  some inherited keyboard descriptions remain under advanced/reference categories.
- No general research/provider gap was implemented to make copy sound complete. Unsupported
  runtime/modalities and unverified live provider/model behavior retain their existing limits.

No new provider, algorithm, ledger schema, history rewrite, dependency upgrade, paid call,
live Moss/RunPod inference, deployment, commit, push or Pass 4 work was performed.
