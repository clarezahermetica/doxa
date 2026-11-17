# v28 playtest corrections

These are source corrections, not a replacement of the installed frozen executable.
No historical record is rewritten and no provider call is required.

Subsequent local installation: these corrections were packaged as terminal v29.
The installed command now selects v29; v28 and earlier owned binaries were retained.
Manifest/ZIP checks, eight installation tests, an offline packaged run, read-only
historical diagnostics, and 80x24 terminal startup/exit passed. Twenty-four existing
workspace, settings and credential fingerprints remained unchanged. No public release
was created.

## Response authorship

Live Council uses the persisted event actor and matching accepted normalization/context
provenance. The response's `critic_id` still identifies the original critic. Missing or
conflicting authorship displays an unknown responder, rather than guessing from the
critic or claim author.

Read-only acceptance of event 86 in a disposable copy of `cb8eb61d`, at 80x24 and
160x45, checked the feed, Inspector, agent filters and replay. Executor produced the
response and its atomic revision; Skeptic remains the original critic. The Executor
filter includes both records and the Skeptic filter excludes that response.

## Failure disposition

Live Council exposes the recorded failure reason and a **Run status** action. The
shared summary gives the last committed provider and controller stages, last research
contribution, completed work, accounting states and supported inspection, export and
new-attempt actions. A failed attempt cannot resume in place. Creating a new attempt
does not authorize execution, replay an uncertain call, or release a reservation.

The precise exception for historical `cb8eb61d` was never recorded. Its generic reason
remains unchanged. Sixteen calls and accounting operations completed; eleven claim
versions and 152 events remain. Its last research contribution is adjudication 150;
reflection 151 preceded failure 152. The current claim still lacks a current judgment.

Future failures use fixed classifications in the existing reason field, never raw
exception messages or arbitrary exception class names. Dedicated provider, reply-format,
invalid-action and context-limit classifications remain distinct. This is not a
complete traceback, a billing determination or a claim that retrying is safe.

## Navigation

- L selects the newest contribution in the current filtered feed. Enter and Space
  immediately act on it.
- Revision cards say **v5, revises v4**. Diffs remain ordered older to newer.
- Focus and pending arrivals appear before long run details in the footer. Focused
  feed and Inspector borders supplement textual cues.
- Ctrl+G returns from workspace controls, filters or the Inspector to the feed. It
  does not dismiss a modal or hijack typing in a separate form. F1 explains the route.
- A fresh 80x24 startup correctly opened the experiment picker with Enter. No startup
  dispatch change was justified. Its regression waits for mounting and focus, rather
  than assuming startup completes within a fixed fraction of a second.

## Paced offline playtest

The normal development CLI opened a disposable fixture in Windows ConPTY at 80x24.
A separate producer delayed each synthetic runtime turn by five seconds. While event
6 remained in the Inspector, three unseen contributions arrived. Ctrl+G restored the
older reading viewport; the count subsequently reached four and six. L reset the count
and selected the then-newest event 23; Space expanded it and Enter inspected event 23.
The synthetic run completed ten turns and 33 committed events, with zero model calls.

Private terminal-cell captures and raw VT streams preserve this interaction. On
return, older passages stayed in the same viewport; only elapsed/status text and
scrollbar glyphs differed. Deterministic interaction tests at 80x24 and 160x45 check
selection, numeric scroll position, exact unseen counts, no duplicates and inspection
during paced commits.

A wide terminal also showed growing data, but initial workspace-tab focus prevented
the intended feed commands. This motivated the workspace-level Ctrl+G route. The full
manual wide concurrent-reading sequence is not claimed as completed; wide functional
acceptance is covered by the deterministic interaction tests.

## Boundaries

No paid inference, research-network access, reservation settlement, README edit,
commit, push, release or installation is performed. Schemas and stored record formats
are unchanged, with no migration. Original histories are compared read-only against
the verified pre-playtest backup.

Native Windows visual contrast and large-transcript performance still need separate
verification. Terminal-cell capture does not certify native pink-theme rendering or
performance at scale. See the private acceptance report for final regression results.

Verification: the full suite passed 607 tests with the existing Starlette/httpx
deprecation warning. After the final explicit latest-button focus correction, all
14 Live Council tests passed again; the entire suite was not rerun after that
one-line correction. Final Ruff and strict mypy (110 files) pass, and public schema
comparisons and diff whitespace checks are unchanged/clean.
