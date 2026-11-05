# Status

DOXA is an unfinished terminal-first proof of concept. The published application uses
Textual and the CLI; React Studio and the native graphical desktop are retired.

## Observed verification

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
