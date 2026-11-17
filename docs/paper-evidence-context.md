# Paper evidence in a Council turn

Run `2d066696` stored the 17-page PDF and its 58,101-character extraction.
The 20 saved prompts all included the opening of page 1; three turns
contained no other page. All pages were in the source; the prompts instead
reflected section-agnostic ranking and the request budget. Ranking
used the question and current claims; discussion was packed first and
evidence received at most half of the remaining room.

## Current selection

For an extracted PDF with recognizable methods and results headings, the
assembler reserves up to 4,096 serialized input bytes for evidence, plus
room for an availability notice, before deciding how much discussion prose
to retain. The reservation is bounded by available request space and the
configured evidence limit. The selector packs excerpts from detected
methods, results, and limitations together before filling space by lexical
relevance. It shortens the group when necessary. It never alters the source
text or invents sections, and it falls back to ordinary retrieval when it
cannot detect a section pair or fit the group. Text documents keep their
previous ranking and budget policy.

For a Skeptic or Archivist reviewing a selected claim with a located PDF
citation, DOXA prioritizes the exact cited range, alongside any available
ranges needed for a related criticism. It estimates the wire cost before
trimming discussion. The final packet is measured with its source IDs,
coordinates, and prompt escaping; the configured input and output limits
still apply. An earlier citation link in discussion is not direct evidence
unless the actual range is included in a source packet for this turn.
Unavailable ranges are reported with the saved reason: budget omission,
source ineligible or absent, or passage unavailable. The agent receives a
gap notice without disclosing an ineligible source identity.

## Inspect the turn

Use **Turn input** or **U** in Live Council to open the explicitly linked saved
prompt's source packets. It distinguishes directly supplied ranges from
earlier citation references and their availability. It displays the
decoded packet verbatim (with terminal controls escaped); a clipped packet
stays clipped. **Citations** and **Full source** answer different questions.
The old **Inspect → Contexts** view still exposes saved messages. Historical
turns with no explicit context link or no authoritative passage ranges are
labeled accordingly.

## Read-only comparison

The saved prompts were read without modifying the original workspace. The
new assembler was then run offline against a restored copy, at the same
history cutoff and with the same remaining budget at each compared turn.
The new packets were not sent to a model.

| Turn | Saved packet | Offline reassembly |
| --- | --- | --- |
| Initial Researcher | Excerpts from pages 1, 4, 8, and 17 | Explicit methods at `9239:10239`, results at `12320:13320` (including the intrinsic self-correction scores), and limitations at `30828:31828`, plus ranked excerpts |
| Third-round Skeptic | Ranges `0:1000`, `9000:10000`, and `14000:15000` | All three ranges actually cited by the target claim: `0:1000`, `14000:15000`, and the previously absent `27000:28000` on page 8 |
| Final Skeptic | Clipped opening, `0:922` | Exact cited opening, `0:915`; that target did not cite a later passage |

The final example is intentional: direct access to the passage under review
matters more than a paper-wide coverage percentage. A located citation and
a supplied packet still do not establish that the passage entails the claim.

Final verification: 599 tests passed (one existing Starlette/httpx warning).
The focused paper, retrieval, investigation, and terminal set passed all 56
tests. Ruff, strict mypy on Windows and Linux, and public schema comparison
passed. The original ledger and accounting fingerprints were unchanged.
