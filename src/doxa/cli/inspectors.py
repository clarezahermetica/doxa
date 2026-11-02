from pathlib import Path
from typing import Any
from uuid import UUID

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, Input, Label, TextArea

from doxa.cli.navigation import ClientModal
from doxa.core.controller import Controller
from doxa.core.models import ArtifactRef
from doxa.storage.artifacts import ArtifactStore


def readable_fields(values: dict[str, Any], indent: int = 0) -> list[str]:
    lines = []
    for name, value in values.items():
        label = " " * indent + str(name).replace("_", " ")
        if isinstance(value, dict):
            lines.append(label + ":")
            lines.extend(readable_fields(value, indent + 2))
        elif isinstance(value, (list, tuple)):
            lines.append(label + ": " + ", ".join(str(item) for item in value))
        else:
            lines.append(f"{label}: {'unknown' if value is None else value}")
    return lines


def readable_message(content: str) -> str:
    import json

    try:
        body = json.loads(content)
    except (ValueError, TypeError):
        return content
    action = body.get("research_action") if isinstance(body, dict) else None
    if isinstance(action, dict):
        return "\n".join(readable_fields(action))
    return content


def record_summary(record: Any) -> tuple[str, str]:
    values = record.model_dump(mode="json")
    label = next(
        (
            str(values[k])
            for k in (
                "proposition",
                "objection",
                "title",
                "display_name",
                "model_id",
                "text",
                "phase",
                "evaluator_version",
            )
            if values.get(k)
        ),
        values.get("kind", type(record).__name__),
    )
    state = " · ".join(
        str(values[k])
        for k in (
            "status",
            "trust",
            "scope",
            "visibility",
            "role",
            "provider",
            "model_profile_id",
            "provenance",
        )
        if values.get(k) is not None
    )
    if hasattr(record, "model_id") and hasattr(record, "enabled"):
        state += " · " + ("connection unverified" if record.enabled else "disabled")
    return label, state


def describe_record(controller: Controller, record: Any) -> str:
    label, state = record_summary(record)
    lines = [label, state, ""]
    values = record.model_dump(mode="json")
    for name in (
        "adapter",
        "base_url",
        "local",
        "authentication",
        "credential_env",
        "enabled",
        "capabilities",
        "max_context_tokens",
        "max_output_tokens",
        "temperature",
        "timeout_seconds",
        "concurrency",
        "artifact",
        "repository_id",
        "instructions",
        "model_profile_id",
        "model_profile_version",
        "model_id",
        "permissions",
        "metrics",
        "denominators",
        "reason",
        "response",
        "notes",
        "validation_ids",
        "evidence_ids",
        "dependency_ids",
        "revises_id",
        "source_ids",
        "history_ids",
        "memory_ids",
        "input_token_upper_bound",
    ):
        if values.get(name) is not None:
            lines.extend(readable_fields({name: values[name]}))
    for name in ("content", "messages", "workspace"):
        artifact = getattr(record, name, None)
        if isinstance(artifact, ArtifactRef):
            raw = ArtifactStore(controller.settings.data_dir / "artifacts").get(artifact)
            if name == "messages":
                import json

                messages = json.loads(raw)
                lines += [f"\n{m['role']}:\n{m['content']}" for m in messages]
            elif artifact.media_type.startswith("text/"):
                lines.append(raw.decode("utf-8")[:200000])
            else:
                lines.append(f"{name}: {artifact.media_type} · SHA-256 {artifact.sha256}")
    for identity in getattr(record, "evidence_ids", ()):
        evidence = controller.ledger.get(identity)
        lines.append(f"\nEvidence: {getattr(evidence, 'description', '')}")
        for artifact in getattr(evidence, "artifacts", ()):
            if artifact.media_type.startswith("text/"):
                lines.append(
                    ArtifactStore(controller.settings.data_dir / "artifacts")
                    .get(artifact)
                    .decode("utf-8")[:200000]
                )
    return "\n".join(lines)


class DetailScreen(ClientModal[None]):
    CSS = """
    DetailScreen { align: center middle; }
    #detail-dialog { width: 94%; height: 94%; }
    #detail-text { height: 1fr; border: none; }
    """

    def __init__(self, title: str, content: str):
        super().__init__()
        self.heading, self.content = title, content

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="detail-dialog"):
            yield Label(self.heading)
            yield TextArea(self.content, read_only=True, id="detail-text")
            yield Button("Close", id="detail-close")

    def on_button_pressed(self) -> None:
        self.dismiss(None)


class ExportScreen(ClientModal[None]):
    def __init__(self, controller: Controller, run_id: UUID):
        super().__init__()
        self.controller, self.run_id = controller, run_id

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(
                "Export to a new .json history or .zip with verified artifacts and configuration"
            )
            yield Input(placeholder="Destination path", id="export-path")
            yield Label("", id="export-result", markup=False)
            yield Button("Export", id="export-save")
            yield Button("Close", id="export-close")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export-close":
            self.dismiss(None)
        elif event.button.id == "export-save":
            from doxa.core.exports import export_run

            try:
                import asyncio

                destination = await asyncio.to_thread(
                    export_run,
                    self.controller,
                    self.run_id,
                    Path(self.query_one("#export-path", Input).value),
                )
                self.query_one("#export-result", Label).update(f"Saved {destination}")
            except (OSError, ValueError):
                self.query_one("#export-result", Label).update(
                    "Export failed: choose a new writable file. Existing files are preserved."
                )
