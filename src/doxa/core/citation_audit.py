"""Source/link/span checks only: neither citation entailment nor argument correctness."""

import re
from collections.abc import Mapping
from typing import TYPE_CHECKING
from uuid import UUID

from doxa.core.models import Claim, Evidence, Record, SourceDocument
from doxa.storage.artifacts import ArtifactStore

if TYPE_CHECKING:
    from doxa.core.controller import Controller


def citation_counts(
    controller: "Controller", claims: tuple[Claim, ...], records: Mapping[UUID, Record]
) -> dict[str, int]:
    counts = dict(
        document_links=0,
        other_evidence_links=0,
        invalid_links=0,
        located_spans=0,
        unlocated_links=0,
        invalid_spans=0,
    )
    store = ArtifactStore(controller.settings.data_dir / "artifacts")
    lengths: dict[UUID, int] = {}
    for claim in claims:
        for identity in claim.evidence_ids:
            evidence = records.get(identity)
            if not isinstance(evidence, Evidence):
                counts["invalid_links"] += 1
                continue
            if not evidence.source.startswith("source-document:"):
                counts["other_evidence_links"] += 1
                continue
            counts["document_links"] += 1
            try:
                source = records.get(UUID(evidence.source.split(":", 1)[1]))
            except ValueError:
                source = None
            if not isinstance(source, SourceDocument) or source.content not in evidence.artifacts:
                counts["invalid_links"] += 1
                continue
            if not evidence.source_location:
                counts["unlocated_links"] += 1
                continue
            match = re.fullmatch(r"unicode_characters:(\d+):(\d+)", evidence.source_location)
            if match:
                if source.id not in lengths:
                    lengths[source.id] = len(store.get(source.content).decode("utf-8"))
                start, end = map(int, match.groups())
                if 0 <= start < end <= lengths[source.id]:
                    counts["located_spans"] += 1
                    continue
            counts["invalid_spans"] += 1
    return counts
