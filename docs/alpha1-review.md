# DOXA 0.1.0 Alpha 1 review candidate

This is an unfinished proof of concept, submitted on a review branch. It is not a
published binary release, a claim of scientific correctness, or a provider-wide
compatibility certification. The user-authored README is unchanged.

## Version audit

`src/doxa/version.py` is authoritative. Python build metadata reads it through
Hatch's dynamic version configuration; `doxa.__version__` and the API use that same
value. Public terminal title, About, searchable Help and CLI version output use the
derived readable label.

| Surface | Value |
| --- | --- |
| Python/package/API version | `0.1.0a1` |
| Readable product label | DOXA 0.1.0 Alpha 1 |
| Windows description | DOXA 0.1.0 Alpha 1 |
| Windows ProductVersion/FileVersion strings | `0.1.0a1` |
| Windows numeric version | `0.1.0.1` |
| Portable archive | `DOXA-0.1.0a1-Windows.zip` |
| Diagnostic build metadata | `v30` |

The installer still owns `bin/doxa.cmd` and `versions/<build>/DOXA/doxa.exe`.
Changing these to public-version directory names would conflict with existing
ownership manifests, rollback and launcher diagnostics. Only the executable target
advances; workspace, credential and PATH locations do not change. Legacy archives
and iteration numbers in historical developer notes are retained as historical facts.

## Included fixes

- Live Council's chronological feed, claim following, expandable contributions,
  version comparison, saved-context inspection and verified checkpoint preparation.
- Correct response authorship from persisted event/turn provenance, preserving the
  original critic relationship and displaying missing/conflicting provenance honestly.
- Readable failed-run disposition, safe failure classifications, current-versus-prior
  judgments, explicit revision ancestry, select-latest and keyboard focus recovery.
- Section-aware paper evidence selection, exact cited-passage continuity, bounded
  source locations, explicit delivery gaps and Inspector agreement with saved inputs.
- Central structured-response parsing/normalization with preserved provider responses,
  recorded decisions and existing controller validation; no inferred prose actions.
- CLI transport response-byte/token distinctions, interrupted-call preflight guards,
  descriptive evaluation boundaries and incremental ledger inspection improvements.
- Existing experiment-form validation fixes, regression coverage and developer notes.

All clients retain the same controller and append-only ledger. Optional additions
to saved contracts are reflected in the generated schemas. No SQL migration or
historical-record rewrite is needed. Older executables may not understand newer
record kinds; retaining a binary is not a guarantee it can read every newer workspace.

## Verification

- Full offline suite: **611 passed**, one existing Starlette/httpx deprecation warning.
- Version and installer subset: **12 passed** (included in the full-suite count).
- Ruff and strict mypy for Windows and Linux settings pass; schemas reproduce cleanly.
- Actual wheel metadata is `0.1.0a1`; Windows executable resource fields and frozen
  CLI output match the table above.
- Portable archive CRC, 113 manifest hashes, forbidden-path and configured-secret
  scans pass. Binaries and local artifacts are excluded from the source commit.
- A real isolated legacy-to-alpha installation preserved the previous version, and
  the frozen app completed an offline demo and workspace integrity check.
- Frozen About and Help labels were observed through an 80x24 Windows terminal;
  automated version-label interactions also passed at 120x40.
- The local installed command now reports the readable Alpha 1 label. Its 1,037
  owned file hashes verify, 931 previous-version files are retained, and 24 existing
  workspace/settings/credential fingerprints remained unchanged.

## Remaining limits

No live provider inference or new scientific experiment was run for this review.
Model judgments and located citations do not establish objective correctness or
entailment. Native visual contrast, large-transcript performance, full wide-terminal
manual concurrent navigation, clean-machine installation and signing still require
separate verification. Python type checks for Linux are not Linux/macOS installer
certification. Local archives and wheels were tested, not uploaded or published.
