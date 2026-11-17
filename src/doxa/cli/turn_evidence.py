"""Read turn evidence from the saved message artifact, never rerun retrieval."""

import json

from doxa.core.models import ContextManifest
from doxa.storage.artifacts import ArtifactStore

STATUS = {
    "supplied": "supplied in this turn",
    "omitted_budget": "not supplied: context budget",
    "source_ineligible": "not supplied: source not eligible",
    "source_absent": "not supplied: source absent on this trajectory",
    "passage_unavailable": "not supplied: passage unavailable",
}


def evidence_summary(manifest: ContextManifest) -> str:
    lines = []
    if manifest.source_passages:
        lines.append("Direct source ranges recorded for this turn:")
        lines.extend(
            f"  {span.source_id}  [{span.start}:{span.end}]" for span in manifest.source_passages
        )
    elif manifest.source_ids:
        lines.append("Historical turn: exact passage ranges were not recorded.")
    else:
        lines.append("No direct source was recorded for this turn.")
    if manifest.required_passages:
        lines.append("Earlier citation references (not passage text by themselves):")
        for item in manifest.required_passages:
            span = item.passage
            lines.append(f"  {span.source_id}  [{span.start}:{span.end}] · {STATUS[item.status]}")
    return "\n".join(lines)


def describe_turn_evidence(manifest: ContextManifest, store: ArtifactStore) -> str:
    """Show the exact decoded source packet text placed in the saved user message."""
    summary = evidence_summary(manifest)
    try:
        messages = json.loads(store.get(manifest.messages))
        user = next(
            m["content"]
            for m in messages
            if isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), str)
        )
    except (OSError, ValueError, TypeError, StopIteration):
        return summary + "\n\nSaved prompt unavailable; actual text cannot be verified."
    sources = {str(source) for source in manifest.source_ids}
    packets = []
    for line in user.split("\n"):
        if not line.startswith("{"):
            continue
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if not isinstance(item, dict):
            continue
        identity = item.get("source_id", item.get("id"))
        content = item.get("untrusted_content")
        if not isinstance(identity, str) or identity not in sources or not isinstance(content, str):
            continue
        expected = [
            [span.start, span.end]
            for span in manifest.source_passages
            if str(span.source_id) == identity
        ]
        if expected and item.get("source_ranges") == expected:
            title = "Exact saved packet (range metadata matches)"
        else:
            title = "Exact saved packet (ranges unverified)"
        packets.append(f"{title} · {identity}\n{content}")
    if not packets and sources:
        packets.append(
            "This historical prompt has no identifiable source packet. "
            "Inspect the saved messages; do not infer that the full source was sent."
        )
    if packets:
        return summary + "\n\n" + "\n\n".join(packets)
    return summary
