"""Terminal presentation only: committed events remain the source of every row."""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, TextArea

from doxa.core.models import CouncilMessage, Event, Experiment, ModelCall, Verification


@dataclass
class Operation:
    events: list[Event] = field(default_factory=list)
    actor: str = "Controller"
    action: str = ""
    result: str = ""
    origins: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return str(self.events[0].id)

    @property
    def searchable(self) -> str:
        return (
            self.actor
            + " "
            + self.action
            + " "
            + self.result
            + " "
            + " ".join(e.model_dump_json() for e in self.events)
        ).casefold()


def operations(events: list[Event], experiment: Experiment, query: str = "") -> list[Operation]:
    names = {a.id: a.display_name or a.role.value for a in experiment.agents}
    rows: list[Operation] = []
    critical = {"challenge", "decision", "verification", "checkpoint"}
    prior_actor: UUID | None = None
    for event in events:
        actor = event.actor_id or next(
            (
                getattr(p, k)
                for p in event.payload
                for k in ("agent_id", "sender_id", "author_id")
                if getattr(p, k, None)
            ),
            None,
        )
        kinds = {p.kind for p in event.payload}
        boundary = (
            bool(kinds & critical)
            or "FAILED" in event.type
            or "REVISED" in event.type
            or any(
                isinstance(p, CouncilMessage)
                and p.message_type in {"CHALLENGE", "RESPONSE"}
                or isinstance(p, ModelCall)
                and p.status in {"failed", "uncertain"}
                for p in event.payload
            )
        )
        # Only adjacent events for one actor/turn can share a row. Objections,
        # decisions, revisions and failures always retain their own operation.
        merge = bool(
            rows
            and len(rows[-1].events) < 32
            and actor
            and actor == prior_actor
            and not boundary
            and not any(p.kind == "claim" for p in rows[-1].events[-1].payload)
            and not any(p.kind in critical or p.kind == "context_manifest" for p in event.payload)
            and not any(
                "FAILED" in e.type
                or "REVISED" in e.type
                or any(p.kind in critical for p in e.payload)
                for e in rows[-1].events
            )
        )
        if not merge:
            rows.append(
                Operation(
                    actor=names.get(actor, "Participant") if actor is not None else "Controller"
                )
            )
        row = rows[-1]
        row.events.append(event)
        labels = {
            "imported_source": "imported",
            "model_output": "model-generated",
            "human_annotation": "human-authored",
            "deterministic_verifier": "independent check",
            "task_answer_key": "answer-key check",
            "llm_evaluator": "LLM evaluation",
            "system_inference": "system",
        }
        provenance = {
            str(event.provenance),
            *(str(getattr(p, "provenance", event.provenance)) for p in event.payload),
        }
        for value in sorted(provenance):
            origin = labels.get(value, value.replace("_", " "))
            if origin not in row.origins:
                row.origins.append(origin)
        summary = []
        for p in event.payload:
            text = next(
                (
                    str(getattr(p, k))
                    for k in (
                        "proposition",
                        "objection",
                        "response",
                        "reason",
                        "title",
                        "content",
                        "description",
                        "verdict",
                        "trust",
                        "status",
                        "phase",
                    )
                    if getattr(p, k, None)
                ),
                "",
            )
            if p.kind == "evaluation":
                text = "Evaluation recorded; inspect provenance and denominators"
            if p.kind == "council_message":
                from doxa.cli.inspectors import readable_message

                text = readable_message(text)
            if text:
                text = text.replace("\n", " ")
                summary.append(text[:159] + "…" if len(text) > 160 else text)
        row.action = " / ".join(dict.fromkeys(e.type.lower().replace("_", " ") for e in row.events))
        if summary:
            row.result = " · ".join(summary)
        prior_actor = actor if not boundary else None
    term = query.casefold().strip()
    return [r for r in rows if not term or term in r.searchable]


def worker_observation(directory: Path, run_id: UUID) -> str:
    path = directory / "worker-locks" / f"{run_id}.lock"
    if not path.exists():
        return "unverified"
    try:
        with path.open("r+b") as stream:
            if sys.platform == "win32":
                import msvcrt

                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:
                    return "owned"
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                try:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return "owned"
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    except OSError:
        return "unverified"
    return "unowned"


def operation_details(row: Operation, controller: Any) -> str:
    from doxa.cli.inspectors import describe_record, readable_fields

    lines = [row.actor + " · " + row.action, "Origin: " + ", ".join(row.origins)]
    for event in row.events:
        lines += [
            f"\n{event.timestamp:%Y-%m-%d %H:%M:%S} · {event.type}",
            f"Event: {event.id}",
            "Causal parents: " + (", ".join(map(str, event.parent_event_ids)) or "none"),
        ]
        if event.model:
            lines += readable_fields(
                {"exact model assignment": event.model.model_dump(mode="json")}
            )
        for record in event.payload:
            lines.append(f"Record: {record.kind} · {record.id}")
            lines.append(describe_record(controller, record))
            if isinstance(record, Verification):
                lines.append("Verdict: " + str(record.verdict))
            if isinstance(record, ModelCall):
                lines += readable_fields(
                    {
                        "exact call assignment": record.assignment.model_dump(mode="json"),
                        "request settings": record.request_settings,
                        "billing uncertain": record.billing_uncertain,
                        "accounting basis": record.accounting_basis,
                    }
                )
                if record.accounting_basis == "subscription_quota":
                    lines.append("Subscription quota consumption unknown; USD billing unavailable.")
    return "\n".join(lines)


class OperationDetails(ModalScreen[None]):
    BINDINGS = [("escape", "close", "Close operation")]
    CSS = """
    OperationDetails { align: center middle; }
    #operation-dialog { width: 96%; height: 96%; }
    #operation-text { height: 1fr; border: none; }
    #operation-buttons { height: 3; }
    """

    def __init__(self, row: Operation, controller: Any, *, raw: bool = False):
        super().__init__()
        self.row = row
        self.controller = controller
        self.raw = raw

    def compose(self) -> ComposeResult:
        with Vertical(id="operation-dialog"):
            yield Label(
                f"{self.row.actor} · {len(self.row.events):,} committed events", markup=False
            )
            yield TextArea(read_only=True, id="operation-text")
            with Horizontal(id="operation-buttons"):
                yield Button("Original typed events", id="operation-raw")
                yield Button("Close", id="operation-close")

    async def on_mount(self) -> None:
        import asyncio
        import json

        if self.raw:
            self.query_one(TextArea).load_text(
                json.dumps([e.model_dump(mode="json") for e in self.row.events], indent=2)
            )
            self.query_one("#operation-raw", Button).label = "Readable detail"
        else:
            self.query_one(TextArea).load_text(
                await asyncio.to_thread(operation_details, self.row, self.controller)
            )

    def action_close(self) -> None:
        self.dismiss(None)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "operation-close":
            self.dismiss(None)
        else:
            import asyncio
            import json

            self.raw = not self.raw
            text = (
                json.dumps([e.model_dump(mode="json") for e in self.row.events], indent=2)
                if self.raw
                else await asyncio.to_thread(operation_details, self.row, self.controller)
            )
            self.query_one(TextArea).load_text(text)
            self.query_one("#operation-raw", Button).label = (
                "Readable detail" if self.raw else "Original typed events"
            )
