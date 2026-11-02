from pathlib import Path
from uuid import UUID, uuid5

from doxa.retrieval.persistent import PersistentSearch


def evidence_excerpt(database: Path, source_id: UUID, text: str, query: str) -> str:
    """Deterministic bounded source excerpts; full original remains a canonical artifact."""
    if len(text) <= 1200:
        return text
    chunks: list[str] = []
    for paragraph in text.split("\n\n"):
        chunks.extend(
            paragraph[offset : offset + 1000] for offset in range(0, len(paragraph), 1000)
        )
    chunks = [chunk for chunk in chunks if chunk.strip()]
    if not chunks:
        return text[:1000]
    documents = [(uuid5(source_id, f"excerpt-v1:{i}"), "", chunk) for i, chunk in enumerate(chunks)]
    order = PersistentSearch(database).rank(documents, query, 1)
    chosen = next((i for i, (identity, _, _) in enumerate(documents) if identity in order), 0)
    return (
        f"[Excerpt {chosen + 1}/{len(chunks)}; full source retained separately]\n" + chunks[chosen]
    )
