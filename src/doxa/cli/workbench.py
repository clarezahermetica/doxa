"""Ergonomic workbench CLI; compatibility commands remain in main.py."""

import asyncio
import json
import time
from pathlib import Path
from typing import Annotated, Any, Literal, cast
from uuid import UUID, uuid4

import typer

from doxa.core.config import Settings
from doxa.core.controller import Controller
from doxa.core.models import BudgetPolicy, CouncilLimits, Role, TaskSpecification
from doxa.core.workbench import (
    DebateExecution,
    DebateRuntime,
    ImportDocument,
    NewAgent,
    NewExperiment,
    ParticipantGroup,
    add_agent,
    create_experiment,
    import_document,
)

DEFAULT_DATA_DIR = Settings().data_dir
experiment_app = typer.Typer()
run_app = typer.Typer()


@run_app.command("preflight")
def run_preflight(
    run_id: UUID,
    json_output: bool = typer.Option(False, "--json"),
    data_dir: Path = DEFAULT_DATA_DIR,
) -> None:
    """Inspect pinned launch eligibility without network access or spending."""
    from doxa.core.preflight import format_preflight, preflight

    report = preflight(instance(data_dir), run_id)
    typer.echo(report.model_dump_json(indent=2) if json_output else format_preflight(report))


@run_app.command("new-attempt")
def run_new_attempt(
    run_id: UUID, criticism_strategy: str | None = None, data_dir: Path = DEFAULT_DATA_DIR
) -> None:
    """Create another configured attempt; prior records remain immutable. Import its evidence."""
    from doxa.core.attempts import new_attempt

    if criticism_strategy not in {None, "evidence_gaps", "counterexamples", "source_conflicts"}:
        raise typer.BadParameter("Choose evidence_gaps, counterexamples or source_conflicts")
    run = new_attempt(
        instance(data_dir),
        run_id,
        criticism_strategy=cast(Any, criticism_strategy),
        idempotency_key=str(uuid4()),
    )
    typer.echo(
        f"Configured attempt {run.id}. Import evidence, inspect preflight, then authorize launch."
    )


def instance(data_dir: Path) -> Controller:
    if not (data_dir / "ledger.sqlite3").is_file():
        raise typer.BadParameter(
            "Workspace ledger not found; open an existing workspace or use init"
        )
    controller = Controller(Settings(data_dir=data_dir))
    try:
        controller.initialize()
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from None
    return controller


@experiment_app.command("new")
def experiment_new(
    name: str = typer.Option(..., prompt=True),
    question: str = typer.Option(..., prompt=True),
    member: Annotated[list[str] | None, typer.Option()] = None,
    rounds: int = 2,
    live: bool = False,
    structured: bool = False,
    staged: bool = False,
    data_dir: Path = DEFAULT_DATA_DIR,
) -> None:
    """Create an offline experiment with a question and configured Council templates."""
    controller = instance(data_dir)
    groups = []
    for value in member or []:
        display_name, _, count = value.rpartition(":")
        matches = [a for a in controller.configuration().agents if a.display_name == display_name]
        if len(matches) != 1:
            raise typer.BadParameter("Use --member 'Unique agent name:count'")
        groups.append(ParticipantGroup(agent_id=matches[0].id, count=int(count)))
    run = create_experiment(
        controller,
        NewExperiment(
            name=name,
            task=TaskSpecification(
                question=question,
                structured_actions=structured,
                staged_research=staged,
                council=CouncilLimits(rounds=rounds),
            ),
            participants=tuple(groups),
            execution_kind="live" if live else "synthetic",
            budget=BudgetPolicy(max_model_calls=20),
            idempotency_key=str(uuid4()),
        ),
    )
    typer.echo(f"Created {name} ({run.execution_kind}). Run: {run.id}")


@run_app.command("start")
def run_start(
    run_id: UUID,
    authorize_paid: bool = False,
    authorize_external: bool = False,
    upper_bound: str | None = None,
    data_dir: Path = DEFAULT_DATA_DIR,
) -> None:
    """Start a configured debate; live inference requires applicable explicit authorization."""
    from decimal import Decimal

    controller = instance(data_dir)
    bundle = asyncio.run(
        DebateRuntime(controller, run_id).execute_debate(
            DebateExecution(
                authorize_paid=authorize_paid,
                authorize_external=authorize_external,
                upper_bound_usd_per_attempt=Decimal(upper_bound) if upper_bound else None,
            )
        )
    )
    typer.echo(
        f"{bundle.run.execution_kind} run {bundle.run.status}: "
        f"{len(bundle.events)} committed events"
    )


@run_app.command("watch")
def run_watch(run_id: UUID, once: bool = False, data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Follow committed run events; --once prints one persisted snapshot."""
    controller = instance(data_dir)
    cursor = 0
    while True:
        bundle = controller.inspect(run_id)
        for event in bundle.events[cursor:]:
            typer.echo(f"{event.timestamp:%H:%M:%S}  {event.type}  {event.provenance}")
        cursor = len(bundle.events)
        if once or bundle.run.status in {"completed", "failed", "cancelled"}:
            return
        time.sleep(0.5)


@run_app.command("cancel")
def run_cancel(run_id: UUID, data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Record run cancellation while retaining unknown remote billing and call outcomes."""
    instance(data_dir).cancel(run_id)
    typer.echo("Cancellation recorded. Remote billing may remain unknown.")


def install(app: typer.Typer) -> None:
    app.add_typer(experiment_app, name="experiment")
    app.add_typer(run_app, name="run")

    @app.command("agent-add")
    def agent_add(
        name: str = typer.Option(..., prompt=True),
        role: Role = Role.RESEARCHER,
        instructions: str = typer.Option(..., prompt=True),
        profile: str | None = None,
        profile_version: int | None = None,
        remote: bool = False,
        data_dir: Path = DEFAULT_DATA_DIR,
    ) -> None:
        """Create a named agent template with instructions and optional pinned model assignment."""
        if role not in {Role.EXECUTOR, Role.SKEPTIC, Role.RESEARCHER, Role.ARCHIVIST}:
            raise typer.BadParameter("Verifier and orchestrator are outside the LLM Council")
        result = add_agent(
            instance(data_dir),
            NewAgent(
                display_name=name,
                role=cast(
                    Literal[Role.EXECUTOR, Role.SKEPTIC, Role.RESEARCHER, Role.ARCHIVIST], role
                ),
                instructions=instructions,
                profile_id=profile,
                profile_version=profile_version,
                remote_inference=remote,
            ),
        )
        typer.echo(f"Saved {result.display_name} v{result.version} ({role.value})")

    @app.command("claims")
    def claims(
        run_id: UUID,
        branch: UUID | None = None,
        json_output: bool = typer.Option(False, "--json"),
        data_dir: Path = DEFAULT_DATA_DIR,
    ) -> None:
        """Inspect branch-visible claims, including immutable versions and provenance."""
        from doxa.core.models import Claim, Trajectory
        from doxa.systems.research import branch_events

        controller = instance(data_dir)
        events = list(controller.inspect(run_id).events)
        root = next(
            p.id
            for e in events
            for p in e.payload
            if isinstance(p, Trajectory) and p.parent_id is None
        )
        records = [
            p
            for e in branch_events(events, branch or root)
            for p in e.payload
            if isinstance(p, Claim)
        ]
        if json_output:
            typer.echo(json.dumps([p.model_dump(mode="json") for p in records]))
        else:
            for index, record in enumerate(records, 1):
                typer.echo(f"{index}. {record.proposition} ({record.status}; {record.provenance})")
            if not records:
                typer.echo("No claims recorded on this branch.")

    @app.command("models")
    def models(
        json_output: bool = typer.Option(False, "--json"), data_dir: Path = DEFAULT_DATA_DIR
    ) -> None:
        """List saved model identities and runtime assignments without contacting endpoints."""
        config = instance(data_dir).configuration()
        if json_output:
            typer.echo(json.dumps([p.model_dump(mode="json") for p in config.profiles]))
        else:
            for profile in config.profiles:
                typer.echo(
                    f"{profile.id} v{profile.version} · {profile.provider} · {profile.model_id}"
                )
            if not config.profiles:
                typer.echo(
                    "No model profiles. Open doxa and choose Choose model and connection. "
                    "Credentials stay local; saving a profile does not verify inference."
                )

    @app.command("evidence-import")
    def evidence_import(run_id: UUID, path: Path, data_dir: Path = DEFAULT_DATA_DIR) -> None:
        """Import a bounded local research document into a configured experiment."""
        import base64

        from doxa.retrieval.documents import MAX_FILE_BYTES

        if path.stat().st_size > MAX_FILE_BYTES:
            raise typer.BadParameter("Choose a document up to 10 MB")
        doc = import_document(
            instance(data_dir),
            run_id,
            ImportDocument(
                filename=path.name,
                data_base64=base64.b64encode(path.read_bytes()).decode(),
                idempotency_key=str(uuid4()),
            ),
        )
        typer.echo(f"Imported {doc.title} · SHA-256 {doc.content.sha256}")

    @app.command("console")
    def console(data_dir: Path = DEFAULT_DATA_DIR) -> None:
        """Open DOXA's research console in the selected workspace."""
        from doxa.cli.console import ResearchConsole

        ResearchConsole(data_dir).run()

    @app.command("demo")
    def demo(
        data_dir: Path = DEFAULT_DATA_DIR, json_output: bool = typer.Option(False, "--json")
    ) -> None:
        """Run the explicitly synthetic evidence/Council demonstration without model calls."""
        from doxa.core.workbench_demo import demonstrate

        if not (data_dir / "ledger.sqlite3").exists():
            if data_dir.exists() and (not data_dir.is_dir() or any(data_dir.iterdir())):
                raise typer.BadParameter("A new demo workspace must be an empty directory")
            # Explicit synthetic demo creation remains compatible. A missing
            # remembered workspace is still refused by controller initialization.
            Controller(Settings(data_dir=data_dir)).initialize()
        result = asyncio.run(demonstrate(instance(data_dir)))
        typer.echo(
            json.dumps(result)
            if json_output
            else f"Offline debate completed: {result['participants']} participants, "
            f"{result['contexts']} recorded contexts. Synthetic fixtures; no paid calls. "
            f"Run: {result['run_id']}"
        )
