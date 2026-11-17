import json
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid5

from doxa.core.models import SourcePassage
from doxa.retrieval.persistent import PersistentSearch


@dataclass(frozen=True)
class EvidencePacket:
    text: str
    passages: tuple[SourcePassage, ...] = ()


@dataclass(frozen=True)
class PaperSection:
    name: str
    start: int
    end: int


def paper_sections(text: str, parser: str) -> tuple[PaperSection, ...]:
    """Recognize a paper conservatively; unrecognized PDFs keep ordinary ranking."""
    if not parser.startswith("pypdf-text-"):
        return ()
    headings = []
    for match in re.finditer(r"(?m)^[^\n]{1,100}$", text):
        line = match[0].strip()
        numbered = re.match(r"^\d+(?:\.\d+)*\.?\s+(.+)$", line)
        label = numbered[1] if numbered else line
        heading_case = label.isupper()
        # PDF small caps can extract "R ESULTS". Normalize labels only, never evidence.
        label = re.sub(r"\b([A-Z]) (?=[A-Z]{2,}\b)", r"\1", label).casefold()
        prefix = label.split(":", 1)[0].strip()
        name = next(
            (
                kind
                for kind, pattern in (
                    (
                        "Methods",
                        r"methods?(?: and materials)?|materials and methods|methodology|"
                        r"experimental (?:setup|design)|study (?:design|methods)|"
                        r"implementation details",
                    ),
                    (
                        "Results",
                        r"(?:experimental |main |empirical )?results(?: and discussion)?|findings",
                    ),
                    ("Limitations", r"limitations(?: and broader impact)?|threats to validity"),
                    ("Introduction", r"introduction"),
                    (
                        "Other",
                        r"abstract|background(?: and related work)?|"
                        r"related work|conclusions?(?: and discussion)?|discussion|references",
                    ),
                )
                if re.fullmatch(pattern, prefix)
            ),
            None,
        )
        if name or (numbered and heading_case):
            headings.append((match.start(), name))
    introduction = next((start for start, kind in headings if kind == "Introduction"), -1)
    sections: dict[str, PaperSection] = {}
    for index, (start, name) in enumerate(headings):
        end = headings[index + 1][0] if index + 1 < len(headings) else len(text)
        if name in {"Methods", "Results", "Limitations"} and start > introduction:
            if end - start < 80:
                continue
            sections.setdefault(name, PaperSection(name, start, end))
    if (
        "Methods" not in sections
        or "Results" not in sections
        or sections["Methods"].start >= sections["Results"].start
    ):
        return ()
    return tuple(
        sections[name] for name in ("Methods", "Results", "Limitations") if name in sections
    )


def evidence_excerpt(
    database: Path, source_id: UUID, text: str, query: str, max_bytes: int = 1200
) -> str:
    return select_passages(database, source_id, text, query, max_bytes).text


def select_passages(
    database: Path,
    source_id: UUID,
    text: str,
    query: str,
    max_bytes: int,
    *,
    required: tuple[SourcePassage, ...] = (),
    sections: tuple[PaperSection, ...] = (),
) -> EvidencePacket:
    """Return controller-derived ranges, never offsets parsed from imported text."""

    def size(value: str) -> int:
        return len(json.dumps(value).encode("utf-8"))

    if not required and text and size(text) <= max_bytes:
        return EvidencePacket(text, (SourcePassage(source_id=source_id, start=0, end=len(text)),))
    if max_bytes < 160:
        return EvidencePacket("")

    if required:
        retained: list[SourcePassage] = []
        packet = "[Partial source; omitted text remains in the full source artifact]"
        for span in required:
            if span.source_id != source_id or span.end > len(text):
                raise ValueError("Required evidence range is outside the source")
            if any(s.start <= span.start and s.end >= span.end for s in retained):
                continue
            suffix = (
                f"\n\n[Required passage; characters {span.start}:{span.end}]\n"
                f"{text[span.start : span.end]}"
            )
            if size(packet + suffix) <= max_bytes:
                packet += suffix
                retained.append(span)
        return EvidencePacket(packet, tuple(retained)) if retained else EvidencePacket("")
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
    section_windows: list[tuple[int, int, str]] = []

    def render(values: dict[int, str]) -> str:
        parts = ["[Partial source; omitted text remains in the full source artifact]"]
        windows = section_windows[:]
        for i in sorted(values):
            start = chunks[i][0]
            windows.append((start, start + len(values[i]), f"Excerpt {i + 1}/{len(chunks)}"))
        for start, end, label in sorted(windows):
            locations = [page for position, page in pages if position <= start]
            end_locations = [page for position, page in pages if position < end]
            page = ""
            if locations:
                first, last = locations[-1], end_locations[-1]
                page = f"; PDF page {first}" if first == last else f"; PDF pages {first}-{last}"
            parts.append(f"[{label}{page}; characters {start}:{end}]\n{text[start:end]}")
        return "\n\n".join(parts)

    if sections:
        # Try a substantive opening from each recognized section together.
        # Shorten the set evenly rather than allowing the abstract to consume it.
        for width in (1000, 800, 640, 480, 360, 240, 160, 100):
            section_windows[:] = [(s.start, min(s.end, s.start + width), s.name) for s in sections]
            if size(render({})) <= max_bytes:
                break
        else:
            section_windows.clear()

    for i in order:
        chunk = chunks[i][1]
        start = chunks[i][0]
        if any(start < end and start + len(chunk) > left for left, end, _ in section_windows):
            continue
        if not chunk.strip():
            continue
        trial = {**chosen, i: chunk}
        if size(render(trial)) <= max_bytes:
            chosen = trial
        elif not chosen and not section_windows:
            low, high = 0, len(chunk)
            while low < high:
                middle = (low + high + 1) // 2
                if size(render({i: chunk[:middle]})) <= max_bytes:
                    low = middle
                else:
                    high = middle - 1
            if low:
                chosen[i] = chunk[:low]
    return EvidencePacket(
        render(chosen) if chosen or section_windows else "",
        tuple(
            SourcePassage(source_id=source_id, start=start, end=end)
            for start, end in sorted(
                [
                    *((start, end) for start, end, _ in section_windows),
                    *((chunks[i][0], chunks[i][0] + len(part)) for i, part in chosen.items()),
                ]
            )
        ),
    )
