"""Interactive local setup and text-review forms. All writes use Controller operations."""

from decimal import Decimal
from typing import Literal, cast
from uuid import UUID, uuid4

from pydantic import ValidationError
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
from doxa.core.research_criteria import REVIEW_DISPUTES
from doxa.core.text_research import review_adapter
from doxa.core.workbench import (
    NewAgent,
    NewExperiment,
    ParticipantGroup,
    add_agent,
    create_experiment,
)


class SetupInputError(ValueError):
    """An instruction the setup form can safely show to the user."""


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
                        yield Label(
                            "Investigation requires structured actions and sequential scheduling. "
                            "Fixed rounds remain available for legacy protocols."
                        )
                        yield Select(
                            [
                                ("Fixed rounds (legacy)", "fixed_rounds"),
                                (
                                    "Investigation: claim, criticism, response, judgment",
                                    "investigation",
                                ),
                            ],
                            value="fixed_rounds",
                            allow_blank=False,
                            id="setup-research-protocol",
                        )
                        yield Checkbox(
                            "Investigation: require criticism and reviewer follow-up before "
                            "a supported conclusion",
                            id="setup-review-disputes",
                            tooltip="Select Investigation above. All configured resource limits "
                            "still apply; unresolved disputes may stop at a limit.",
                        )
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
                        for field, label, default in (
                            ("rounds", "Rounds", "2"),
                            ("concurrency", "Concurrent calls", "1"),
                            ("calls", "Maximum model calls", "20"),
                            ("agent-tokens", "Per-agent token cap", "16384"),
                            ("total-tokens", "Aggregate token cap", "65536"),
                            ("timeout", "Run timeout (seconds)", "120"),
                            ("context", "Context token cap", "8192"),
                            ("output", "Output token cap", "1024"),
                            ("run-cap", "Run spending ceiling (USD)", "1"),
                        ):
                            yield Label(label)
                            yield Input(value=default, id=f"setup-{field}")
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
            yield Label("", id="setup-error", markup=False)
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
                        raise SetupInputError("Choose an execution mode.")
                    if not name.strip():
                        raise SetupInputError("Enter an experiment name.")
                    if not text.strip():
                        raise SetupInputError("Enter a research question.")
                    protocol = cast(
                        Literal["fixed_rounds", "investigation"],
                        self.query_one("#setup-research-protocol", Select).value,
                    )
                    schedule = cast(
                        Literal["sequential", "round_parallel"],
                        self.query_one("#setup-schedule", Select).value,
                    )
                    structured = self.query_one("#setup-structured", Checkbox).value
                    staged = self.query_one("#setup-staged", Checkbox).value
                    review = self.query_one("#setup-review-disputes", Checkbox).value
                    try:
                        rounds = int(self.query_one("#setup-rounds", Input).value)
                    except ValueError:
                        raise SetupInputError("Enter a whole number for Rounds.") from None
                    if staged and (not structured or rounds < 3):
                        raise SetupInputError(
                            "Staged research needs Structured claims and at least 3 rounds. "
                            "Turn off Staged research cycle to keep your current settings."
                        )
                    if protocol == "investigation" and (not structured or schedule != "sequential"):
                        raise SetupInputError(
                            "Investigation needs Structured claims and Sequential scheduling."
                        )
                    if review and protocol != "investigation":
                        raise SetupInputError(
                            "Reviewer follow-up requires Investigation. Select it or turn off "
                            "the reviewer follow-up checkbox."
                        )
                    templates = self.controller.configuration().agents
                    if not templates:
                        raise SetupInputError("Add an agent template before creating a run.")
                    members = self.query_one("#setup-members", Input).value
                    if not members.strip():
                        raise SetupInputError("Enter at least one Council template and count.")
                    groups = []
                    roles = set()
                    for raw in members.split(";"):
                        display, separator, count = raw.strip().rpartition(":")
                        if not separator or not display.strip() or not count.strip().isdecimal():
                            raise SetupInputError(
                                "Enter each Council entry as a template name and count, "
                                "for example Researcher:1."
                            )
                        matches = [a for a in templates if a.display_name == display]
                        if not matches:
                            matches = [
                                a for a in templates if a.display_name.strip() == display.strip()
                            ]
                        if len(matches) != 1 or not matches[0].enabled:
                            raise SetupInputError(
                                "Each Council entry must match one enabled agent template."
                            )
                        groups.append(ParticipantGroup(agent_id=matches[0].id, count=int(count)))
                        roles.add(matches[0].agent.role)
                    if protocol == "investigation" and (
                        not {Role.SKEPTIC, Role.ARCHIVIST} <= roles
                        or not roles & {Role.RESEARCHER, Role.EXECUTOR}
                    ):
                        raise SetupInputError(
                            "Investigation needs an Archivist, a Skeptic, and a Researcher or "
                            "Executor. Check the roles on the selected templates."
                        )
                    created = create_experiment(
                        self.controller,
                        NewExperiment(
                            name=name,
                            task=TaskSpecification(
                                question=text,
                                evaluation_criteria=("citation coverage", "explicit uncertainty")
                                + ((REVIEW_DISPUTES,) if review else ()),
                                research_protocol=protocol,
                                staged_research=staged,
                                structured_actions=structured,
                                council=CouncilLimits(
                                    rounds=rounds,
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
                                    scheduling=schedule,
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
            except SetupInputError as exc:
                self.query_one("#setup-error", Label).update(str(exc))
            except ValidationError as exc:
                fields = ", ".join(
                    str(error["loc"][-1]).replace("_", " ")
                    for error in exc.errors(include_input=False)
                    if error["loc"]
                )
                self.query_one("#setup-error", Label).update(
                    f"Check the value for {fields}." if fields else
                    "Check the Council composition and the selected protocol and limits."
                )
            except (ValueError, KeyError, ArithmeticError):
                self.query_one("#setup-error", Label).update(
                    "DOXA could not save this setup. Check the model assignments and limits."
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
