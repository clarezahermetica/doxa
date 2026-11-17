# Live Council

Select an experiment and open **Live Council**, or choose **Open Live Council** in
the command palette. It opens by default for live multi-agent research. A closed
run opens at the start of its saved transcript; a running run opens at the latest
committed contributions. The **Activity**, **Claim exchanges**, and **Inspect**
tabs remain available.

**Research Feed** shows structured contributions in committed order.
**All Activity** adds recorded provider milestones, calls, checkpoint saves,
run states, and response rejections. A response and the revision it creates
appear in one card when written in the same event. Human review and model
review are labeled separately. No provider prose, streaming tokens, or
private reasoning are converted into dialogue.

An agent is identified by the ID pinned to the experiment, with its recorded
display name and role. Claim and criticism prefixes refer to record IDs, not
the wording of propositions; full IDs are available in the Inspector and raw
event. Follow Claim joins recorded revisions, criticisms, responses,
reassessments, and judgments on that trajectory. The feed cannot see parent
events after the inherited cutoff, or sibling writes. No relationship is
inferred from wording or nearby timestamps. The observer's view does not
mean every participant received the same sources.

With the feed focused:

| Key | Action |
| --- | --- |
| Up / Down | Select a contribution |
| Enter or F2 | Inspect the selected contribution |
| Space | Expand or collapse that contribution |
| T | Switch between previews and full text |
| F | Follow the selected claim / restore the previous view |
| D | Compare the selected version with its predecessor or the latest visible version |
| V | Open the attached sources and citation locations |
| U | Inspect the source packets actually saved for the selected agent turn |
| B | Prepare an analysis branch from a verified checkpoint |
| L | Jump to the latest contribution and resume following |
| Page Up / Page Down | Scroll without changing the selected contribution |
| Escape | Close the Inspector, clear the followed claim, or return to the previous tab |
| Ctrl+J | Open the exact committed event |
| F1 | Live Council help; F1 again opens the full reference |

Tab and Shift+Tab reach the same operations through buttons and filters. Feed
shortcuts do not run while typing in a field. Below 136 columns, the Inspector
temporarily replaces the feed and restores its reading position when closed.
At wider sizes it sits beside the same feed. Scrolling away from the bottom
keeps the reading position and counts new matching entries; **Jump to latest**
reveals them. At most 80 cards are mounted at a time. Use **Earlier** and
**Later** to navigate long transcripts. While a separate modal is open, the
base viewer catches up after it closes; the research worker is unaffected.

## Branch preparation

Choose **Branch** on a contribution that targets a claim. DOXA checks the
selected event and lists only verified text checkpoints owned by the active
trajectory. The dialog states whether each checkpoint cursor is before, at,
or after the selected event. Inherited entries can be inspected in place; to
branch from one, select its owning trajectory. If no valid checkpoint is
available, the create button stays disabled.

To create a branch, choose a checkpoint, enter an intervention description,
and explicitly confirm. The controller checks the checkpoint again before
committing the fork. The branch inherits the prefix through that cursor, so
a checkpoint before the selected event will not include that event, and a
later checkpoint may include more than that event. The new branch is selected
for inspection. This operation creates analysis history only; it does not
continue a model run or incur provider costs.

## Verification scope

Final regression run: **593 passed**, with the existing Starlette/httpx
deprecation warning. Ruff, strict mypy for Windows and Linux, and
regeneration of both public schemas passed; the schemas were unchanged.

The restored copy of the saved four-agent run projected 192 committed events
into 25 research cards (168 cards in All Activity). In 11 warm measurements
on the Windows development machine, the median initial saved-run projection
was 1.05 ms and changing the projection filter took 0.03 ms. These measurements
exclude SQLite hydration and terminal layout. A separate 2,000-event offline
fixture exercised the 80-card render window.
On that 2,000-event fixture, the warm median was 32.91 ms for the initial
projection, 0.284 ms for appending one event, and 0.436 ms to read the All
Activity projection. These are projection timings, not repaint latency.

The actual Textual widgets were verified at 80×24 dark, 120×40 light, and
160×42 Rose Pine Dawn. The 80-column view left nine rows for the feed; the
160-column view gave 118 columns to the feed and 42 to the Inspector.
Selected-card foreground/background contrast from resolved Textual colors
was 13.05:1, 12.49:1, and 6.66:1 respectively. These checks do not certify
how a particular Windows terminal emulator renders the interface.
The restored copy opened evidence from the saved run; original ledger,
configuration and accounting fingerprints matched before and after.
Three earlier failed attempts were also projected read-only: each retained
its observed terminal state, and a recorded action rejection remained distinct
from completed provider calls. The old generic stop codes were not rewritten.
