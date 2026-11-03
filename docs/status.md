# Status

DOXA is an unfinished terminal-first proof of concept. The published application uses
Textual and the CLI; React Studio and the native graphical desktop are retired.

## Observed verification

- GitHub's Python 3.12 and 3.14 Ubuntu jobs each passed **370 tests with 9 skips** on
  commit `300e779`, including Ruff, Linux/Windows-targeted strict mypy and generated-schema
  consistency. One existing Starlette TestClient deprecation warning remained.
- The earlier terminal-only source checkpoint passed **376 tests on Windows/Python
  3.14.7**. The subsequent platform corrections passed 24 focused credential/document
  tests; the canonical offline study also passed through the direct pytest launcher.
  The complete suite now collects 379 tests. Those are separate observations, not a
  claim that all 379 have been rerun on Windows.
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
