"""Inspect a DOXA history ZIP using only Python's standard library and no workspace.

Usage: python -I -S inspect_research_archive.py condition-C.zip
This verifies preserved bytes and structural references, not model truth or entailment.
No archive entry is extracted or executed. Resource limits intentionally bound inspection.
"""

import argparse
import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any


def inspect_archive(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if (
            len(entries) > 4096
            or len(set(names)) != len(names)
            or sum(entry.file_size for entry in entries) > 128 * 1024 * 1024
            or any(entry.file_size > 32 * 1024 * 1024 for entry in entries)
        ):
            raise ValueError("Duplicate entries or archive inspection limit exceeded")
        for name in names:
            if (
                PurePosixPath(name).is_absolute()
                or ".." in PurePosixPath(name).parts
                or "\\" in name
                or ":" in name
            ):
                raise ValueError("Unsafe archive entry name")
        manifest = json.loads(archive.read("manifest.json"))
        expected = manifest["files"]
        if set(names) != set(expected) | {"manifest.json"}:
            raise ValueError("Manifest membership differs from the archive")
        for name, properties in expected.items():
            content = archive.read(name)
            if hashlib.sha256(content).hexdigest() != properties["sha256"]:
                raise ValueError("Artifact/history hash mismatch")
        history = json.loads(archive.read("history.json"))
        events = history["events"]
        records = [record for event in events for record in event["payload"]]
        event_ids = {event["id"] for event in events}
        by_id = {record["id"]: record for record in records}
        if len(event_ids) != len(events) or len(by_id) != len(records):
            raise ValueError("Event or record identities are duplicated")
        run_id = history["run"]["id"]
        if any(event["run_id"] != run_id for event in events):
            raise ValueError("Cross-run event found")
        if any(parent not in event_ids for event in events for parent in event["parent_event_ids"]):
            raise ValueError("Missing causal parent")
        experiments = [record for record in records if record["kind"] == "experiment"]
        if len(experiments) != 1:
            raise ValueError("Exactly one experiment is required")
        agents = {agent["id"] for agent in experiments[0]["agents"]}
        branches = {record["id"]: record for record in records if record["kind"] == "trajectory"}
        for branch in branches.values():
            visited = {branch["id"]}
            parent = branch["parent_id"]
            while parent is not None:
                if parent not in branches or parent in visited:
                    raise ValueError("Missing or cyclic branch ancestry")
                visited.add(parent)
                parent = branches[parent]["parent_id"]
        valid_spans = 0
        claim_ids = []
        context_ids = []
        for record in records:
            kind = record["kind"]
            if "run_id" in record and record["run_id"] != run_id:
                raise ValueError("Cross-run record found")
            if kind == "claim":
                claim_ids.append(record["id"])
                if record["author_id"] is not None and record["author_id"] not in agents:
                    raise ValueError("Unknown claim author")
                if record["revises_id"] and record["revises_id"] not in by_id:
                    raise ValueError("Missing claim ancestor")
                if any(identity not in by_id for identity in record["evidence_ids"]):
                    raise ValueError("Missing claim evidence")
            elif kind == "context_manifest":
                context_ids.append(record["id"])
                if record["agent_id"] not in agents:
                    raise ValueError("Unknown context recipient")
                for identity in (
                    *record["source_ids"],
                    *record["history_ids"],
                    *record["memory_ids"],
                ):
                    if identity not in by_id:
                        raise ValueError("Missing supplied-context record")
            elif kind == "checkpoint" and record["event_cursor"] not in event_ids:
                raise ValueError("Missing checkpoint cursor")
            elif kind == "evidence" and record["source_location"]:
                match = re.fullmatch(r"unicode_characters:(\d+):(\d+)", record["source_location"])
                if match:
                    sha = record["artifacts"][0]["sha256"]
                    if not re.fullmatch(r"[0-9a-f]{64}", sha):
                        raise ValueError("Invalid citation artifact identifier")
                    text = archive.read(f"artifacts/sha256/{sha[:2]}/{sha}").decode()
                    start, end = map(int, match.groups())
                    if not 0 <= start < end <= len(text):
                        raise ValueError("Invalid citation character span")
                    valid_spans += 1
        return {
            "run_id": run_id,
            "events": len(events),
            "records": len(records),
            "event_ids": [event["id"] for event in events],
            "claim_ids": claim_ids,
            "context_ids": context_ids,
            "agent_ids": sorted(agents),
            "branch_ids": sorted(branches),
            "source_hashes": sorted(
                record["content"]["sha256"]
                for record in records
                if record["kind"] == "source_document"
            ),
            "record_kinds": dict(Counter(record["kind"] for record in records)),
            "files_verified": len(expected),
            "valid_citation_spans": valid_spans,
            "truth_or_entailment_verified": False,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect_archive(args.archive), indent=2))


if __name__ == "__main__":
    main()
