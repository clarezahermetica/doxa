import json
import re
from pathlib import Path
from uuid import UUID, uuid5

from doxa.retrieval.persistent import PersistentSearch


def evidence_excerpt(
    database: Path, source_id: UUID, text: str, query: str, max_bytes: int = 1200
) -> str:
    """Full text when it fits; otherwise located excerpts within a JSON-byte budget."""

    def size(value: str) -> int:
        return len(json.dumps(value).encode("utf-8"))

    if size(text) <= max_bytes:
        return text
    if max_bytes < 160:
        return ""
    chunks = [(offset, text[offset : offset + 1000]) for offset in range(0, len(text), 1000)]
    documents = [
        (uuid5(source_id, f"excerpt-v2:{i}"), "", chunk)
        for i, (_, chunk) in enumerate(chunks)
        if chunk.strip()
    ]
    ranked = PersistentSearch(database).rank(documents, query, len(documents))
    indices = {
        identity: i
        for i, (offset, _) in enumerate(chunks)
        for identity in (uuid5(source_id, f"excerpt-v2:{i}"),)
    }
    order = list(dict.fromkeys([*(indices[i] for i in ranked), *range(len(chunks))]))
    pages = [(m.start(), m.group(1)) for m in re.finditer(r"(?m)^\[Page (\d+)\]", text)]
    chosen: dict[int, str] = {}

    def render(values: dict[int, str]) -> str:
        parts = ["[Partial source; omitted text remains in the full source artifact]"]
        for i in sorted(values):
            start = chunks[i][0]
            end = start + len(values[i])
            locations = [page for position, page in pages if position <= start]
            end_locations = [page for position, page in pages if position < end]
            page = ""
            if locations:
                first, last = locations[-1], end_locations[-1]
                page = f"; PDF page {first}" if first == last else f"; PDF pages {first}-{last}"
            parts.append(
                f"[Excerpt {i + 1}/{len(chunks)}{page}; characters {start}:{end}]\n{values[i]}"
            )
        return "\n\n".join(parts)

    for i in order:
        chunk = chunks[i][1]
        if not chunk.strip():
            continue
        trial = {**chosen, i: chunk}
        if size(render(trial)) <= max_bytes:
            chosen = trial
        elif not chosen:
            low, high = 0, len(chunk)
            while low < high:
                middle = (low + high + 1) // 2
                if size(render({i: chunk[:middle]})) <= max_bytes:
                    low = middle
                else:
                    high = middle - 1
            if low:
                chosen[i] = chunk[:low]
    return render(chosen) if chosen else ""
