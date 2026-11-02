import asyncio
from uuid import UUID

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, Checkbox, Input, Label, Select, TextArea

from doxa.cli.navigation import ClientModal
from doxa.core.controller import Controller
from doxa.core.models import Experiment, Trajectory


class ResearchToolScreen(ClientModal[None]):
    CSS = """
    ResearchToolScreen { align: center middle; }
    #tool-dialog { width: 94%; height: 94%; padding: 1; }
    #tool-result { height: 12; min-height: 6; }
    """

    def __init__(self, controller: Controller, operation: str, run_id: UUID | None):
        super().__init__()
        self.controller, self.operation, self.run_id = controller, operation, run_id

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="tool-dialog"):
            yield Label(
                {
                    "compare": "Compare recorded trajectories — no inference",
                    "memory": (
                        "Query eligible memory — retrieval permissions and spending limits apply"
                    ),
                    "connection": (
                        "Check endpoint metadata — authorize network access; no generation"
                    ),
                    "preflight": "Check launch readiness — no network or model calls",
                }.get(self.operation, self.operation.title())
            )
            if self.operation == "compare" and self.run_id:
                records = [
                    p for e in self.controller.inspect(self.run_id).events for p in e.payload
                ]
                branches = [p for p in records if isinstance(p, Trajectory)]
                options = [(Text(b.intervention or "Main trajectory"), str(b.id)) for b in branches]
                yield Label("Baseline / treatment branches")
                yield Select(options, id="tool-left")
                yield Select(options, id="tool-right")
            elif self.operation == "memory" and self.run_id:
                experiment = self.controller.ledger.get(
                    self.controller.inspect(self.run_id).run.experiment_id
                )
                assert isinstance(experiment, Experiment)
                yield Label("Participant whose eligibility/visibility applies")
                yield Select(
                    [(Text(a.display_name or a.role.value), str(a.id)) for a in experiment.agents],
                    id="tool-agent",
                )
                yield Input(placeholder="Memory query", id="tool-query")
            elif self.operation == "connection":
                yield Label("Profile to inspect/discover (no inference request)")
                yield Select(
                    [
                        (Text(p.id + f" v{p.version}"), p.id)
                        for p in self.controller.configuration().profiles
                    ],
                    id="tool-profile",
                )
                yield Checkbox("Authorize this endpoint metadata request", id="tool-authorize")
            yield TextArea(read_only=True, id="tool-result")
            yield Button(
                {
                    "compare": "Compare trajectories",
                    "memory": "Search eligible memory",
                    "connection": "Request metadata",
                    "preflight": "Check readiness",
                }.get(self.operation, "Run operation"),
                id="tool-run",
            )
            yield Button("Close", id="tool-close")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "tool-close":
            self.dismiss(None)
        elif event.button.id == "tool-run":
            result = self.query_one("#tool-result", TextArea)
            self.query_one("#tool-run", Button).disabled = True
            try:
                if self.operation == "compare" and self.run_id:
                    from doxa.core.comparison import compare_branches

                    comparison = await asyncio.to_thread(
                        compare_branches,
                        self.controller,
                        self.run_id,
                        UUID(str(self.query_one("#tool-left", Select).value)),
                        UUID(str(self.query_one("#tool-right", Select).value)),
                    )
                    lines = [comparison.caveat]
                    lines.extend(f"{change}" for change in comparison.commitments)
                    for index, evaluation in enumerate(comparison.evaluations):
                        lines.append(
                            f"Branch {index + 1}: "
                            f"{evaluation.metrics if evaluation else 'No evaluation recorded'}"
                        )
                    result.load_text("\n".join(lines))
                elif self.operation == "memory" and self.run_id:
                    agent = UUID(str(self.query_one("#tool-agent", Select).value))
                    memories = await self.controller.retrieve_memory(
                        self.run_id, agent, self.query_one("#tool-query", Input).value
                    )
                    result.load_text(
                        "\n\n".join(m.text for m in memories)
                        or "No eligible match; revoked and invisible records are excluded."
                    )
                elif self.operation == "connection":
                    from doxa.core.secrets import workspace_env
                    from doxa.providers.discovery import discover_models

                    profile = next(
                        p
                        for p in self.controller.configuration().profiles
                        if p.id == self.query_one("#tool-profile", Select).value
                    )
                    report = await discover_models(
                        profile,
                        workspace_env(self.controller.settings.data_dir),
                        authorize_network=self.query_one("#tool-authorize", Checkbox).value,
                    )
                    result.load_text(
                        report.status + "\n" + report.detail + "\n" + "\n".join(report.model_ids)
                    )
                elif self.operation == "preflight" and self.run_id:
                    from doxa.core.preflight import format_preflight, preflight

                    launch_report = await asyncio.to_thread(preflight, self.controller, self.run_id)
                    result.load_text(format_preflight(launch_report))
            except (ValueError, KeyError, PermissionError, StopIteration):
                result.load_text(
                    "Rejected: check selections and authorization. No inference was dispatched."
                )
            finally:
                self.query_one("#tool-run", Button).disabled = False
