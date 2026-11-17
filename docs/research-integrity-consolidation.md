# Research integrity consolidation

This pass uses the existing controller, SQLite ledger and Textual client. It does
not update an installed binary or change existing claims, citations, workspaces,
credentials or reservations.

## Diagnosis

| Classification | Finding | Disposition |
| --- | --- | --- |
| Confirmed bug | Context assembly could prioritize the source document but lose the exact range behind a criticism after re-ranking its passages. The manifest had document IDs and the prompt artifact, but no typed record of supplied ranges. | Carry forward validated ranges with their source version and record exact delivery or the reason for omission. |
| Confirmed bug | The claim viewer keyed the citation picker by source, collapsing distinct locations in the same paper. The revision label action could only address the latest claim. | Select individual evidence records and label the revision currently selected. |
| Expected behavior, unclear in the terminal | A fixed-round study can finish without an epistemic outcome, model agreement cannot independently verify a claim, and unlabeled revisions have unknown correction quality. | Show execution and research outcomes separately, with judgment currency and explicit unknowns. |
| Expected behavior, unclear in the terminal | Failed attempts leave immutable history; a successful provider turn can still be rejected as an invalid research action. | Show distinct attempts, timestamps, a recorded stop reason and the last observable provider stage. |
| Design limitation | Search and context have hard budgets. A paper in the workspace, a paper sent in part, and a passage received are different. | Separate source absence, ineligibility, unavailable passage bytes, and budget omission. The record says what the agent received, not what it understood. |
| Optional improvement, measured | Idle polls hydrated a full bundle repeatedly, and claim inspection repeated the event read even when the terminal already had the bundle. | Use the committed event head to detect changes and reuse loaded events for projection. |
| Untested in this pass | Live serving-model verification, structured citation behavior on real providers, clean-machine/manual Windows Terminal acceptance, and security certification. | Keep the results explicitly offline. |

### Completed experiment and prior failures

The reviewed completed run was a five-round fixed-round adversarial Council
with four agents, 192 events and 20 model calls. The evidence check used the
original stored source and each persisted prompt. Excerpt numbers are labels
for 1,000-character windows specific to that source version.

| Turn | Direct access to excerpts 14–16 |
| --- | --- |
| Round 2 Skeptic | 14, 15 and 16 |
| Round 2 Archivist | 14 and 15; excerpt 16 appeared only in reported history |
| Round 3 Executor | 14 and 15 |
| Round 3 Skeptic | None of 14–16 |
| Round 3 and final Archivist | 15 |

Across the 20 turns, excerpt 14 was sent three times, 15 fourteen times, and 16
once. The same paper stayed eligible. Query ranking and budget packing explain
the observed changes; there is no evidence of source revocation. A later
reference to an omitted excerpt can be an accurate account of a peer's report,
but cannot establish firsthand access. The access asymmetry could have affected
reviews or revisions; the saved run does not establish that it did. It reported
known-source citations and a located span rate of 0.0. No historical citations
or human assessments were added.

The observed adapter was Codex CLI. There were 20 completed subscription
operations, with no reported serving-model identity or USD total. The
trajectory includes 13 claim records, eight revisions, one criticism, one
checkpoint (no fork), two evaluation records, and five reflection decisions
or skips. It has no Memory Tribunal retrieval or independent verification
records. The eight revisions remain unlabeled by a human, so net justified
correction is unknown.

Three earlier attempts stopped at different stages: a completed model response
used a singleton operations wrapper that the then-current parser did not
accept; a later response used a claim ID where a source ID was required; and a
third attempt completed 16 turns before the fifth round could not fit active
history within the request's byte bound. These histories were inspected without
retrying or reconciling anything. The checkout already contained related
normalization and request-sizing work before this pass.

## Passage and citation contract

- Character positions are Unicode code-point indices into the exact extracted
  source artifact, with an exclusive end. They are not PDF byte positions,
  visual page coordinates, or reconstructed offsets.
- An action can declare `citation_ranges` as a list of objects with
  `source_id`, `start`, and `end`. Each source must also be in the action's
  `source_ids`. Generated ranges must be contained in a range from that
  participant's actual turn manifest. User annotations can cite eligible
  source text independently.
- Controller-derived ranges appear outside imported text in the prompt.
  Imported text cannot grant itself a larger range by imitating a label.
  Identical ranges are deduplicated. Partial windows retain their real end.
- Criticisms and their evidence links are read on the current branch. An exact
  passage used by a relevant criticism is packed ahead of ordinary excerpts.
  An out-of-scope, superseded, missing or unaffordable passage is not replaced
  with a different part of the paper. The manifest retains the location and
  reason for inspection. A model's gap notice omits unavailable source identities.
- The stored range means a location was validated. It does not judge whether
  the passage entails the claim or independently verifies it. Imported documents
  and observed model responses remain different types of evidence.
- The new fields are additive. Old manifests have no authoritative typed
  ranges; inspect their recorded prompt instead. There is no SQL migration.

## Operator workflow

Open **Read claim exchanges** to select a current or earlier claim, criticism,
response, reassessment or judgment. The picker also includes the full exact
exchange and a word-change view when a revision exists. **Sources** opens the
evidence attached to the selected section. **Label revision** records optional
human review of the selected version. It does not require a label to complete
an experiment.

The terminal's automated interaction harness opened the saved run's longest
exchange at 80×24 in dark mode and 120×40 in light mode. It selected the
original version with the keyboard, exposed all five versions in the full
53-line view, paged through the text and retained that selection on resize.
This is an interaction check, not manual Windows Terminal visual acceptance.

Use **Inspect run summary and coverage**, or
`doxa run summary RUN_ID --data-dir WORKSPACE`, to see recorded limits, assignments,
reported model identity where available, usage, stop reason, current judgments,
and the six-system record coverage. This describes the selected trajectory,
not certification of a subsystem. Synthetic fixture coverage is labeled
separately. Replay, exports and the synthetic CLI are retained. Getting
Started now leads to opening or setting up actual research.

## Performance method and remaining work

Run `python scripts/benchmark_workbench.py WORKSPACE RUN_ID` in the development
environment. The harness uses warm medians and makes no changes to stored
records. It compares full and head-only polling and reuse of the same loaded
event set. This does not measure all of Textual rendering, cold startup, PDF
extraction, export or worker performance. Event search still serializes the
records on each changed query; no performance improvement is claimed for it.

For the 192-event Council on the development Windows machine, the matched
measurements were:

| Workload | Previous path | Revised path |
| --- | ---: | ---: |
| Unchanged viewer poll, including fresh accounting | 24.09 ms | 4.99 ms |
| Claim projection with the run already loaded | 17.32 ms | 1.93 ms |

Both paths were timed in one process against the same committed data, using
the old full-read path as the control. These are backend read/projection
costs, not whole-screen latencies. Event search took 40.08 ms for 192 events and
289.17 ms for a 1,920-event in-memory stress workload; those measurements are
baselines for a later search optimization.

Additional spot baselines used a 21-event isolated synthetic workspace:
integrity loading 22 ms, context assembly 95 ms, warm lexical retrieval
1.8 ms, ZIP export 284 ms, and 295,270 bytes of peak Python allocations for a
small run inspection (not total process RSS). On this machine, source CLI
help startup was 4.41 s, a frozen version check was 2.51 s, and the paper's
isolated parser took 3.28 s. Across three detached synthetic runs, elapsed
time from launch to observed start event was 3.95 s and from observed final
event to process exit was 0.43 s. These are separate workloads, not claims
of speedup.

The wider runtime review reuses the existing tests for concurrent sequence
allocation, immutable idempotency, branch ancestry, stale revisions,
independent continuation, interrupted worker ownership, held reservations,
and archive/path validation. No isolation, retention, or recovery guarantee
is extended beyond the existing contracts. User-owned historical runs were
checked read-only, and restore acceptance uses isolated data. The current pass
does not implement a general security redesign, live provider certification,
automatic retries of ambiguous calls, broad workflow redesign, or a new
research scheduler.

The passage boundary is treated as an input validation boundary: a declared
offset in model output cannot expand what was sent, a source cannot authorize
its own metadata, and a judgment or another agent's account cannot convert
remote or private material into authorized source text. The publication
scanner checks known credential values and excluded paths without echoing
them. A zero-result scan and passing tests are not a dependency vulnerability
audit or proof that every untrusted document, endpoint, terminal renderer or
OS process-cleanup path is safe on all platforms.

The main changes are in `core/workbench.py`, `core/text_research.py`,
`core/action_output.py` and `retrieval/excerpts.py` for research integrity;
`cli/research_view.py`, `cli/console.py` and `core/run_overview.py` for
inspection; and `cli/onboarding.py` for navigation. The controller and ledger
read paths now support the cached terminal projection without caching
accounting. Existing provider/session and normalization work in the checkout
was preserved.

## Acceptance

- Final full pytest suite: **587 passed**. The existing Starlette/httpx
  deprecation warning remains.
- Ruff, strict mypy for Windows and Linux (106 files), regenerated schema
  checks, and dependency consistency checks passed. The repository's secret
  and excluded-path check found no findings in 209 publishable files.
- A separate Windows PyInstaller one-folder build initialized a new
  workspace, completed a synthetic experiment, displayed its run summary and
  verified all 21 events, 32 records and 11 referenced artifacts. The
  installed v25 command was not replaced. No installer was run on the
  real user profile.
- The saved research workspace still verifies 378 events, 504 records and
  130 referenced artifacts. No historical data, credentials or reservations
  were corrected as part of the investigation. No live providers were
  contacted, and no changes were published.
