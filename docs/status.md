# Status

DOXA is an unfinished terminal-first proof of concept. The published application uses
Textual and the CLI; React Studio and the native graphical desktop are retired.

## Observed verification

- **Secure model connections:** the existing terminal form can list and select local
  models before saving. Managed API references resolve only through protected storage.
  Reachability, declared capabilities and launch authorization remain separate. See
  [model connections](model-connections.md) for workflow, platform and security limits.


- **2026-11-07 v24 bounded readiness and installed update (offline):** final full suite
  **514 passed**, one pre-existing Starlette/httpx warning; Ruff and strict mypy for
  Windows/Linux pass (105 source files). Twenty-one new regressions cover opt-in dispute
  review, stale/current judgments, accepted claims, conflicting Archivists, hard caps,
  cancellation/timeout, plateau, citation reference/span diagnostics, terminal forms at
  80×24 and 120×40, CLI configuration and exact export/restore. The first full run found
  a stale descriptive-evaluator selector in the canonical acceptance script (509 passed,
  five setup errors); the selector was corrected, its five checks passed, and the whole
  suite was rerun successfully. Public schemas reproduce unchanged; no SQL migration.
  A real frozen-executable offline investigation completed with 17 persisted events and
  zero live calls. An owned, unredirected Windows console rendered the packaged terminal
  and quit cleanly with exit 0. Redirected ConPTY capture failed for both DOXA and a minimal
  control and is not counted as passing. Manual Windows Terminal, clean-machine and signed
  distribution acceptance remain unverified.
  The new 156-file package passes manifest hashes, ZIP CRC and private-path/secret scans;
  the source scan covers 199 publishable files with zero findings. The existing owned
  `doxa` command now reports terminal v24. All 425 installed manifest entries verify,
  including 276 retained previous-version files. Four operational settings/credential files,
  four workspace table/revision fingerprints and persistent PATH are unchanged. The
  OneDrive-marked package root was safely rejected; installation used the verified ZIP
  extracted to an ordinary local folder without weakening the installer guard.
  The installed v24 viewer was opened visibly on the existing repaired live-paper workspace;
  its process remained running. No experiment was started. No live inference, external
  retrieval, billing settlement, README edit, commit, push or release was performed.
  **Still bounded:** durable human pause/continuation, cross-run resource policy,
  descendant-process containment and semantic progress criteria remain prerequisites for
  open-ended execution. Citation location/linkage checks do not verify truth or entailment.
  See [the v24 report](v24-bounded-readiness.md) for configuration and limits.


- **2026-11-07 v23-dev stabilization (offline):** final full suite **493 passed**,
  one pre-existing Starlette/httpx warning; Ruff and strict mypy for Windows/Linux pass
  (103 source files). Eighteen new regression cases cover disclosure admission, HTTP
  resource limits, scheduler finalization, stage validation, terminal controls, workspace
  configuration and DOCX encoding policy. Eleven cases reproduced failures before their
  corrections. An earlier 492-pass/one-failure run exposed a terminal test startup race;
  the operator driver now waits for the guide/selector to mount, and the whole suite was
  rerun successfully. No framework error is suppressed.
  All three historical workspaces retain exact event/record/configuration/operation/hold
  fingerprints and migration revisions; 199 referenced artifacts pass integrity checks.
  A separate complete offline investigation exports, verifies and restores exact history.
  Advisory metadata for 59 installed third-party packages has no remaining matches after
  the targeted pypdf 6.21.2 â†’ 6.21.4 security update; this is not a security guarantee.
  Source identifies as v23-dev; installed global launcher remains v17. No new live call,
  credential change, history deletion, migration, README edit, commit, push or release.
  **Not ready for open-ended execution:** durable pause/continuation, descendant cleanup
  characterization, cross-run resource policy and substantive-progress rules remain.
  See [the stabilization report](stabilization-v23.md) for findings, files, checks and limits.


- **2026-11-05 v22 live acceptance completed:** 24 real Codex CLI calls (maximum 29),
  sequential; five source-backed investigations and solo/self-correction controls completed.
  Requested gpt-6.1-sol medium for Researcher/Skeptic and high for Archivist. Across the
  investigations: 5 Researcher, 10 Skeptic and 5 Archivist responses. All main claims were
  accepted; no disputed cross-agent response was triggered. The genuine self-correction
  control committed one criticism, `qualify` response and versioned revision, exercising
  the repaired response enum. All 24 requests carry that enum; 17 process IDs were
  independently observed as the installed Codex executable. Eight private ZIP exports
  pass hashes; actual-record Textual thread/citation/replay checks and a no-inference
  inspection fork/compare passed. Reported usage: 292,265 input / 6,223 output tokens;
  wall span 526.550 seconds, unknown quota/USD cost. No DOXA retries, API fallback or publishing;
  credentials unchanged. Prior failed histories are intact.
  **Limits:** controls differ in effort/calls and retrieved passages; no intrinsic-control
  or causal quality-improvement claim. Duplicate Skeptic reassessment without a response
  remains an efficiency issue. Human correctness labels remain unset; model judgments are
  unverified. Cross-agent disputed cycles and broader features are not live-certified by this test.



- **2026-11-05 v22-dev schema correction (offline):** native response, stance and outcome
  choices derive from the canonical controller enums. Explanatory prose remains valid in
  `reason`; ambiguous prose is never silently classified as a decision. The captured-shape
  regression failed before the correction and passes afterward. 84 focused checks and all
  seven full-cycle offline rehearsals pass, with no changes to history/configuration/holds.
  Full suite: **475 passed**, one pre-existing Starlette warning; Ruff and strict mypy
  for Windows/Linux pass (99 source files). Public schemas regenerate unchanged. No new live calls, migration,
  installed replacement, README edits or publishing. A new live test requires fresh approval.



- **2026-11-05 v21 genuine live acceptance stopped after 7 calls:** Codex CLI 0.160.0
  requested gpt-6.1-sol medium for Researcher/Skeptic and high for Archivist. One four-call
  acceptance/judgment investigation completed; the next failed after three calls because
  generated prose in `respond.response` passed the permissive native string schema but
  failed the controller's disposition enum. No response/revision was committed from that
  invalid proposal. The five-per-role target and control runs were not completed. Reported
  usage: 85,176 input / 1,975 output tokens; quota/USD cost unknown. Two private exports
  are hash-verified. Seven transport-completed quota operations; prior uncertain holds
  preserved. No automatic retry, replacement calls, fallback, production-code change or
  publishing. Next fix: synchronize native response/stance/outcome enums with controller
  contracts and add captured-output regression before fresh live approval. The earlier
  470-test result predates this uncovered live contract gap.



- **2026-11-05 final offline overhaul verification:** **470 passed**, one pre-existing
  Starlette/httpx warning; Ruff and strict mypy for Windows and Linux passed (99 source
  files). Schemas reproduce exactly. Three historical ledgers/projections and 73 artifact
  hashes pass preservation/integrity checks; uncertain holds remain intact. No live call,
  SQL migration, installed replacement or publication. Native visual acceptance and a new
  frozen build remain unverified; see [the complete handoff](post-live-overhaul.md).



- **2026-11-04 post-live overhaul, source v21-dev (offline only):** shared CLI request
  accounting, required active exchanges and bounded evidence excerpts, isolated full-cycle
  stress, opt-in state-driven investigation, explicit unresolved/resource outcomes,
  threaded terminal claim/citation inspection, safe CLI milestones, procedure manifests,
  control preparation and human-label quality summaries are implemented. No new live call,
  installed upgrade, README edit or publication. Existing partial live history remains failed;
  requested model/effort are not certified effective settings. Full verification and remaining
  limits: [post-live handoff](post-live-overhaul.md). Installed global command remains v17.

- **Preserved partial research baseline:** run `8014edb0-765e-5769-aeb3-ce99cd7aa248`
  completed two genuine Codex calls (Researcher and Skeptic), then failed before the response/
  Archivist stages on input/context admission. Reported usage: 52,266 input, 451 output tokens;
  36.445 seconds run duration, unknown USD/subscription quota. A claim and actual criticism
  exist; no complete research trajectory or quality-improvement conclusion follows.


- **2026-11-04 repaired-source live smoke passed:** one explicitly authorized Codex
  CLI 0.160.0 invocation requested `gpt-6.1-sol` with reasoning effort `low`, no
  native tools and no DOXA retry. A real process was independently observed; its
  PID matched the saved response diagnostics and exit code was zero. The completed
  run persisted ten events, fourteen records and one source-linked claim. The full
  imported paper was verified in context; the claim's cited page contains the
  reported numerical finding. Reported usage: 25,706 input and 144 output tokens,
  provider latency about 16.5 seconds. CLI events did not independently report a
  resolved model identifier or effective reasoning effort. Subscription quota and
  USD cost remain unknown. Export hashes and workspace integrity passed; artifacts
  and histories remain local. The earlier failed run and uncertain hold are intact.
  This validates one CLI integration path, not a complete multi-agent research
  trajectory, provider-wide compatibility or improved research quality.

- **2026-11-04 offline startup repair:** Codex 0.160.0 rejected the adapter's reserved
  `model_providers.openai` overrides before dispatch. These overrides are removed.
  A credential-free real-CLI loopback diagnostic now reaches its local error fixture;
  no live inference was run. Sanitized process/exit diagnostics and explicit reasoning
  effort configuration were added. DOXA retries remain zero; native CLI transport retries
  remain client-managed and are disclosed before launch. The failed acceptance history
  and uncertain hold are preserved. Live model compatibility remains unverified.
  Final repaired-source Windows regression: **451 passed**, one existing Starlette
  deprecation warning. Ruff and strict mypy for Linux and Windows passed (91 source
  files each). Both affected operator workflows passed at 80x24 dark and 120x40 light
  in Textual's automated terminal harness; this is not manual Windows Terminal acceptance.

- **2026-11-04 live acceptance did not pass.** One authorized source-v20 Codex CLI
  attempt requested `gpt-6.1-sol` using the authenticated ChatGPT session. It ended
  with a sanitized transport error before any model text, reported model or usage
  was available. The failed run and uncertain quota hold were preserved; no retry,
  API fallback or multi-agent research phase followed. This is not live-model certification.
  The existing workbench displayed persisted activity while the user watched.
  The installed command remains v17; the source is v20.
- The real 17-page research PDF exposed a Windows parser-output encoding bug.
  Its JSON transport now emits UTF-8 bytes. Evidence assembly now supplies full
  authorized source text when the context budget permits, or multiple ranked
  excerpts with character/page locations and explicit partial-coverage metadata.
  The whole extracted paper was verified in both the preview and actual smoke contexts.
  Focused parser/evidence/controller/CLI regression: **97 passed**, one existing warning.
  Full subsequent Windows regression: **437 passed, 1 failed**, one existing warning.
  The failure is the previously observed headless Getting Started focus issue
  (`#guide-do` missing because focus navigated to WorkspaceScreen). Ruff and both strict
  mypy targets passed; the suite was not green at that checkpoint (fixed above).

- Account CLI work adds a first-class Codex session transport, separate quota/disclosure
  authorization and durable non-USD admissions in the same ledger. Final Windows/Python
  3.14.7 regression: **434 passed, one existing Starlette deprecation warning**, including
  55 CLI cases. Ruff and strict mypy for Linux and Windows passed (93 source files each).
  The final one-folder build passed 11 isolated frozen-command checks, including profile
  persistence, CLI preflight help, migration, integrity, backup and restore.
  Safe local probes observed Codex CLI **0.160.0** authenticated through ChatGPT, with
  required flags and response-schema support. That earlier checkpoint had no authorized
  live request; the subsequent failed acceptance attempt is reported above.
  Eligibility is not live-model compatibility.
  Other recognized account CLIs have detection/unsupported states, not executable adapters.
  See [setup and precise limitations](cli-providers.md).

- GitHub's Python 3.12 and 3.14 Ubuntu jobs each passed **370 tests with 9 skips** on
  commit `300e779`, including Ruff, Linux/Windows-targeted strict mypy and generated-schema
  consistency. One existing Starlette TestClient deprecation warning remained.
- The earlier terminal-only source checkpoint passed **376 tests on Windows/Python
  3.14.7**. The subsequent platform corrections passed 24 focused credential/document
  tests; the canonical offline study also passed through the direct pytest launcher.
  That checkpoint collected 379 tests; the later 434-test Windows result is reported above.
- Offline controls exercise persisted experiments, same-role participants, contexts,
  claims, challenges, revisions, branches, evaluations, exports and verified backup/restore.
  Synthetic or mocked responses do not measure live model quality or scientific benefit.
- Publication fixes render untrusted terminal data literally and enforce cumulative
  web-fetch deadlines, including bounded DNS resolution. Earlier binaries are unchanged.

[The verification run](https://github.com/clarezahermetica/doxa/actions/runs/41548612270)
is evidence for that commit. Later cleanup checks must be assessed on their own commits.

## Implemented boundaries and limitations

| Area | Current boundary |
| --- | --- |
| Research control | Versioned controller operations and one append-only workspace ledger. General debate conclusions remain unverified. |
| Providers | Native and compatible text transports have mocked coverage. No exact live provider/model/settings combination was verified by these checks. |
| Retrieval | Local lexical search and optional scoped Moss snapshots. Live Moss improvements and remote synchronization remain unverified. |
| Internet tools | Bounded approved fetch pathway; mocked search, with no configured live search adapter. |
| Local models | Compatible server connections and descriptive artifact registration; no automatic server startup or weight execution. |
| Code execution | Generated code remains disabled; the finite built-in cache task is not a general code-repair sandbox. |
| Distribution | Source installation is supported. Internal Windows packaging is retained; no binary release, signing or clean-machine acceptance is claimed. |
| Modalities | Streaming, multimodal generation, embeddings and automatic native tool-result loops remain unavailable. |

Current operating instructions are in the [documentation index](README.md). Historical
pass reports and copied design specifications remain in Git history, not the active
manual. Cleanup does not change workspace history, reservations, credentials or installed
applications. Tests remain public because the repository's CI depends on them; they are
excluded from application packages.
