"""Interactive local setup and text-review forms. All writes use Controller operations."""

from decimal import Decimal
from typing import Literal, cast
from uuid import UUID, uuid4

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
    Collapsible,
    Input,
    Label,
    Select,
    SelectionList,
    TextArea,
)

from doxa.cli.navigation import ClientModal
from doxa.core.controller import Controller
from doxa.core.models import (
    BudgetPolicy,
    Challenge,
    CouncilLimits,
    ProtocolMode,
    Role,
    TaskSpecification,
)
from doxa.core.profiles import AgentDefinition
from doxa.core.text_research import review_adapter
from doxa.core.workbench import (
    NewAgent,
    NewExperiment,
    ParticipantGroup,
    add_agent,
    create_experiment,
)


class SetupScreen(ClientModal[bool]):
    CSS = """
    SetupScreen { align: center middle; background: $background 70%; }
    #setup-shell { width: 88%; height: 94%; background: $surface; padding: 0 1; }
    #setup-dialog { width: 100%; height: 1fr; }
    #setup-actions { height: 3; }
    SetupScreen Input, SetupScreen Select { margin-bottom: 1; }
    SetupScreen TextArea { height: 6; }
    SetupScreen Label { height: auto; }
    #setup-tools { height: 4; }
    """

    def __init__(
        self,
        controller: Controller,
        kind: str,
        definition: AgentDefinition | None = None,
        *,
        execution_kind: str | None = None,
    ):
        super().__init__()
        self.controller = controller
        self.kind = kind
        self.definition = definition
        self.execution_kind = execution_kind
        self.created_run_id: UUID | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="setup-shell"):
            with VerticalScroll(id="setup-dialog"):
                yield Label(
                    "Create a research experiment"
                    if self.kind == "experiment"
                    else "Add an agent template"
                )
                yield Label("Experiment name" if self.kind == "experiment" else "Agent name")
                yield Input(
                    placeholder="Name",
                    id="setup-name",
                    value=self.definition.display_name if self.definition else "",
                )
                if self.kind == "experiment":
                    yield Label("Execution mode — choose explicitly; saving never starts a run")
                    yield Select(
                        [("Model-backed research", "live"), ("Offline demonstration", "synthetic")],
                        value=self.execution_kind if self.execution_kind else Select.NULL,
                        prompt="Choose execution mode",
                        id="setup-execution",
                    )
                    yield Label(
                        "Model-backed: compatible assigned models + authorization; may cost money. "
                        "Offline: fixed responses, no model/key; cannot establish model behavior."
                    )
                    yield Label("Research question")
                    yield TextArea(id="setup-text", tab_behavior="focus")
                    yield Label("Council: enter template names and counts separated by semicolons")
                    yield Input(placeholder="Researcher:1; Skeptic:3", id="setup-members")
                    names = ", ".join(
                        a.display_name for a in self.controller.configuration().agents
                    )
                    yield Label(
                        "Available templates: " + (names or "Add agent templates first"),
                        markup=False,
                    )
                    with Collapsible(title="Protocol and limits", collapsed=True):
                        yield Select(
                            [(p.value, p.value) for p in ProtocolMode],
                            value="adversarial_multi_agent",
                            allow_blank=False,
                            id="setup-protocol",
                        )
                        yield Select(
                            [("Sequential", "sequential"), ("Round parallel", "round_parallel")],
                            value="sequential",
                            allow_blank=False,
                            id="setup-schedule",
                        )
                        yield Input(value="2", placeholder="Rounds", id="setup-rounds")
                        yield Input(
                            value="1", placeholder="Concurrent calls", id="setup-concurrency"
                        )
                        yield Input(value="20", placeholder="Maximum model calls", id="setup-calls")
                        yield Input(
                            value="16384",
                            placeholder="Per-agent token cap",
                            id="setup-agent-tokens",
                        )
                        yield Input(
                            value="65536",
                            placeholder="Aggregate token cap",
                            id="setup-total-tokens",
                        )
                        yield Input(
                            value="120", placeholder="Run timeout seconds", id="setup-timeout"
                        )
                        yield Input(
                            value="8192", placeholder="Context token cap", id="setup-context"
                        )
                        yield Input(value="1024", placeholder="Output token cap", id="setup-output")
                        yield Input(
                            value="1", placeholder="Run spending ceiling USD", id="setup-run-cap"
                        )
                        yield Checkbox(
                            "Structured claims / criticism / responses / model adjudication",
                            id="setup-structured",
                        )
                        yield Checkbox(
                            "Staged research cycle (requires structured actions and 3+ rounds)",
                            id="setup-staged",
                        )
                else:
                    yield Label("Instructions — what this participant should do")
                    yield TextArea(
                        self.definition.agent.instructions if self.definition else "",
                        id="setup-text",
                        tab_behavior="focus",
                    )
                    yield Label("Role — select a research function, not a model")
                    yield Select(
                        [
                            (r.value, r.value)
                            for r in (Role.EXECUTOR, Role.SKEPTIC, Role.RESEARCHER, Role.ARCHIVIST)
                        ],
                        value=self.definition.agent.role.value if self.definition else "researcher",
                        allow_blank=False,
                        id="setup-role",
                    )
                    yield Label("Model assignment — select a saved model connection")
                    yield Label(
                        "Role and model are separate. Many agents may share a role or model."
                    )
                    profiles = self.controller.configuration().profiles
                    yield Select(
                        [("Offline / unassigned", "")]
                        + [(f"{p.id} v{p.version}", p.id) for p in profiles],
                        value=self.definition.model_profile_id or "" if self.definition else "",
                        allow_blank=False,
                        id="setup-profile",
                    )
                    yield Label("Enabled status — available for future experiment composition")
                    yield Checkbox(
                        "Template enabled",
                        value=self.definition.enabled if self.definition else True,
                        id="setup-enabled",
                    )
                    with Collapsible(
                        title="Memory scope and tool permissions (expand)", collapsed=False
                    ):
                        yield Label("Memory scope — choose private or shared")
                        yield Label(
                            "Private: only its owner may retrieve it. Shared: other eligible "
                            "participants may retrieve it. Approval and branch rules still apply."
                        )
                        yield Select(
                            [("Private memory", "private"), ("Shared memory", "shared")],
                            value=self.definition.agent.memory_scope
                            if self.definition
                            else "private",
                            allow_blank=False,
                            id="setup-memory",
                        )
                        yield Label("Tool permissions — Space toggles; new templates start offline")
                        yield Label(
                            "Permission only allows requests. A configured tool and explicit run "
                            "authorization are also required; checking these grants no "
                            "network access."
                        )
                        yield SelectionList(
                            *[
                                (
                                    name,
                                    name,
                                    self.definition is not None
                                    and name in self.definition.agent.permissions.allowed_tools,
                                )
                                for name in ("web_search", "web_fetch")
                            ],
                            id="setup-tools",
                        )
            yield Label("", id="setup-error")
            with Horizontal(id="setup-actions"):
                yield Button(
                    "Save version" if self.definition else "Create",
                    id="setup-save",
                    variant="primary",
                )
                yield Button("Cancel", id="setup-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "setup-cancel":
            self.dismiss(False)
        elif event.button.id == "setup-save":
            try:
                name = self.query_one("#setup-name", Input).value
                text = self.query_one("#setup-text", TextArea).text
                if self.kind == "experiment":
                    execution = self.query_one("#setup-execution", Select).value
                    if execution not in {"live", "synthetic"}:
                        raise ValueError("Choose an execution mode explicitly")
                    groups = []
                    for raw in self.query_one("#setup-members", Input).value.split(";"):
                        display, _, count = raw.strip().rpartition(":")
                        matches = [
                            a
                            for a in self.controller.configuration().agents
                            if a.display_name == display
                        ]
                        if len(matches) != 1:
                            raise ValueError(
                                "Choose a unique existing template name for each group"
                            )
                        groups.append(ParticipantGroup(agent_id=matches[0].id, count=int(count)))
                    created = create_experiment(
                        self.controller,
                        NewExperiment(
                            name=name,
                            task=TaskSpecification(
                                question=text,
                                staged_research=self.query_one("#setup-staged", Checkbox).value,
                                structured_actions=self.query_one(
                                    "#setup-structured", Checkbox
                                ).value,
                                council=CouncilLimits(
                                    rounds=int(self.query_one("#setup-rounds", Input).value),
                                    concurrency=int(
                                        self.query_one("#setup-concurrency", Input).value
                                    ),
                                    max_calls=int(self.query_one("#setup-calls", Input).value),
                                    per_agent_tokens=int(
                                        self.query_one("#setup-agent-tokens", Input).value
                                    ),
                                    total_tokens=int(
                                        self.query_one("#setup-total-tokens", Input).value
                                    ),
                                    timeout_seconds=float(
                                        self.query_one("#setup-timeout", Input).value
                                    ),
                                    scheduling=cast(
                                        Literal["sequential", "round_parallel"],
                                        self.query_one("#setup-schedule", Select).value,
                                    ),
                                ),
                            ),
                            mode=ProtocolMode(str(self.query_one("#setup-protocol", Select).value)),
                            execution_kind=cast(Literal["live", "synthetic"], execution),
                            participants=tuple(groups),
                            budget=BudgetPolicy(
                                max_model_calls=int(self.query_one("#setup-calls", Input).value),
                                max_context_tokens=int(
                                    self.query_one("#setup-context", Input).value
                                ),
                                max_output_tokens=int(self.query_one("#setup-output", Input).value),
                                timeout_seconds=float(
                                    self.query_one("#setup-timeout", Input).value
                                ),
                                run_cap_usd=Decimal(self.query_one("#setup-run-cap", Input).value),
                            ),
                            idempotency_key=str(uuid4()),
                        ),
                    )
                    self.created_run_id = created.id
                else:
                    profile_id = str(self.query_one("#setup-profile", Select).value)
                    profile = next(
                        (p for p in self.controller.configuration().profiles if p.id == profile_id),
                        None,
                    )
                    # UI models are validated by the same immutable contract as the API.
                    command = NewAgent.model_validate(
                        dict(
                            id=self.definition.id if self.definition else uuid4(),
                            version=self.definition.version + 1 if self.definition else 1,
                            enabled=self.query_one("#setup-enabled", Checkbox).value,
                            memory_scope=str(self.query_one("#setup-memory", Select).value),
                            allowed_tools=self.query_one("#setup-tools", SelectionList).selected,
                            display_name=name,
                            role=str(self.query_one("#setup-role", Select).value),
                            instructions=text,
                            profile_id=profile.id if profile else None,
                            profile_version=profile.version if profile else None,
                            remote_inference=bool(profile),
                        )
                    )
                    add_agent(self.controller, command)
                self.dismiss(True)
            except (ValueError, KeyError):
                self.query_one("#setup-error", Label).update(
                    "Choose an execution mode and check fields, template names, models and limits."
                )


class ReviewScreen(ClientModal[bool]):
    CSS = """
    ReviewScreen { align: center middle; background: $background 70%; }
    #review-dialog { width: 90%; height: 95%; padding: 1 2; background: $surface; }
    Input, Select, TextArea { margin-bottom: 1; }
    TextArea { height: 7; }
    """

    def __init__(self, controller: Controller, run_id: UUID, branch_id: UUID):
        super().__init__()
        self.controller = controller
        self.run_id = run_id
        self.branch_id = branch_id
        self.view = controller.review_workspace(run_id, branch_id)

    def compose(self) -> ComposeResult:
        from doxa.core.models import Experiment

        exp = self.controller.ledger.get(self.controller.inspect(self.run_id).run.experiment_id)
        assert isinstance(exp, Experiment)
        with VerticalScroll(id="review-dialog"):
            yield Label("Append human review · no independent truth verdict")
            yield Select(
                [
                    (v.title(), v)
                    for v in (
                        "claim",
                        "challenge",
                        "respond",
                        "adjudicate",
                        "annotate",
                        "checkpoint",
                        "fork",
                        "evaluate",
                    )
                ],
                value="challenge",
                allow_blank=False,
                id="review-action",
            )
            yield Select(
                [("This branch / new claim", "")], value="", allow_blank=False, id="review-target"
            )
            yield Select(
                [("Choose attributed participant", "")]
                + [(Text(a.display_name or a.role.value), str(a.id)) for a in exp.agents],
                value="",
                allow_blank=False,
                id="review-actor",
            )
            yield Label("Proposition / objection / reason / intervention / annotation notes")
            yield TextArea(id="review-text")
            yield Select(
                [
                    (o, o)
                    for o in (
                        "accept",
                        "reject",
                        "qualify",
                        "investigate",
                        "defer",
                        "retain",
                        "revise",
                        "abstain",
                    )
                ],
                value="investigate",
                allow_blank=False,
                id="review-outcome",
            )
            with Collapsible(title="Evidence and optional revision", collapsed=True):
                yield Label("Optional revised proposition (accept / qualify response)")
                yield TextArea(id="review-replacement")
                sources = [
                    p
                    for e in self.view.events
                    for p in e.payload
                    if getattr(p, "kind", None) == "source_document"
                ]
                yield Label("Evidence sources (Space selects; permission checked on submit)")
                yield SelectionList(
                    *[(Text(getattr(p, "title", "Source")), str(p.id), False) for p in sources],
                    id="review-sources",
                )
            yield Input(value="local-operator", placeholder="Reviewer name", id="review-name")
            yield Label("", id="review-error")
            yield Button("Append operation", id="review-save", variant="primary")
            yield Button("Close", id="review-cancel")

    def on_mount(self) -> None:
        self.targets("challenge")

    def targets(self, action: str) -> None:
        options = [("This branch / new claim", "")]
        if action == "respond":
            options += [(c.objection[:80], str(c.id)) for c in self.view.unresolved_challenges]
        elif action == "adjudicate":
            pending = {c.id for c in self.view.unresolved_challenges}
            options += [
                (
                    ("Awaiting response: " if c.id in pending else "Responded: ")
                    + c.objection[:60],
                    str(c.id),
                )
                for event in self.view.events
                for c in event.payload
                if isinstance(c, Challenge) and not c.responds_to_id
            ]
        elif action == "fork":
            options += [
                ("Checkpoint " + str(i + 1), str(c.id))
                for i, c in enumerate(self.view.checkpoints)
                if c.trajectory_id == self.branch_id
            ]
        else:
            options += [(c.proposition[:80], str(c.id)) for c in self.view.current_claims]
        self.query_one("#review-target", Select).set_options(
            [(Text(label), value) for label, value in options]
        )
        self.query_one("#review-target", Select).value = ""

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "review-action":
            self.targets(str(event.value))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "review-cancel":
            self.dismiss(False)
        elif event.button.id == "review-save":
            action = str(self.query_one("#review-action", Select).value)
            target = str(self.query_one("#review-target", Select).value)
            actor = str(self.query_one("#review-actor", Select).value)
            text = self.query_one("#review-text", TextArea).text
            outcome = str(self.query_one("#review-outcome", Select).value)
            body: dict[str, object] = dict(
                operation=action,
                idempotency_key=str(uuid4()),
                reviewer_id=self.query_one("#review-name", Input).value,
            )
            if action == "claim":
                body.update(
                    author_id=actor,
                    proposition=text,
                    revises_id=target or None,
                    source_ids=self.query_one("#review-sources", SelectionList).selected,
                )
            elif action == "challenge":
                body.update(
                    claim_id=target,
                    critic_id=actor,
                    objection=text,
                    source_ids=self.query_one("#review-sources", SelectionList).selected,
                )
            elif action == "respond":
                body.update(
                    challenge_id=target,
                    author_id=actor,
                    response=outcome,
                    reason=text,
                    revised_proposition=self.query_one("#review-replacement", TextArea).text
                    or None,
                )
            elif action == "adjudicate":
                body.update(challenge_id=target, outcome=outcome, reason=text)
            elif action == "annotate":
                body.update(subject_id=target or str(self.branch_id), notes=text)
            elif action == "fork":
                body.update(checkpoint_id=target, intervention=text)
            try:
                self.controller.review_command(
                    self.run_id, self.branch_id, review_adapter.validate_python(body)
                )
                self.dismiss(True)
            except (ValueError, PermissionError, KeyError):
                self.query_one("#review-error", Label).update(
                    "Operation rejected. Check target, attributed author and required text."
                )
