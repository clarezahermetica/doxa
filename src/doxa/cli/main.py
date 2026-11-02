import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import typer
from pydantic import BaseModel, TypeAdapter

from doxa.cli.workbench import install as install_workbench
from doxa.core.config import Settings
from doxa.core.controller import ConfigureRun, Controller
from doxa.core.execution import ExecuteTask
from doxa.core.memory_commands import ProposeMemory, TransitionMemory
from doxa.core.profiles import CouncilConfig
from doxa.core.research_commands import Command
from doxa.core.retrieval_commands import RetrievalQuery
from doxa.core.retrieval_commands import query as retrieval_query
from doxa.storage.budget import BudgetStore

DEFAULT_DATA_DIR = Settings().data_dir

app = typer.Typer(
    invoke_without_command=True, no_args_is_help=False, pretty_exceptions_show_locals=False
)


def read_contract[Model: BaseModel](model: type[Model], path: Path) -> Model:
    from doxa.core.secrets import reject_secrets

    try:
        raw = path.read_text(encoding="utf-8-sig")
        reject_secrets(raw)
        return model.model_validate_json(raw)
    except (ValueError, OSError):
        raise typer.BadParameter(
            "Configuration file is unreadable, secret-bearing or invalid"
        ) from None


@app.command("doctor")
def doctor(
    data_dir: Path = DEFAULT_DATA_DIR, json_output: bool = typer.Option(False, "--json")
) -> None:
    """Inspect local readiness without probing external services."""
    from doxa.core.readiness import inspect_readiness

    report = inspect_readiness(controller(data_dir))
    if json_output:
        typer.echo(report.model_dump_json(indent=2))
        return
    typer.echo("DOXA local installation · no external probe performed")
    typer.echo(f"Configuration: {'valid' if report.configuration.valid else 'needs attention'}")
    typer.echo(f"Model profiles: {len(report.configuration.profiles)}")
    for profile in report.configuration.profiles:
        typer.echo(f"  {profile.profile_id}: {profile.status}")
    typer.echo("Generated-code execution: disabled")
    typer.echo("Use --json for the full diagnostic record.")


@app.command("validate-config")
def validate_config(config: Path | None = None, data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Validate a configuration file or the saved model/agent configuration."""
    instance = controller(data_dir)
    report = instance.validate_configuration(
        read_contract(CouncilConfig, config) if config else None
    )
    typer.echo(report.model_dump_json(indent=2))
    if not report.valid:
        raise typer.Exit(1)


@app.command("providers")
def providers(data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Inspect registered adapters and offline configuration readiness."""
    instance = controller(data_dir)
    typer.echo(
        json.dumps(
            {
                "adapters": [p.model_dump(mode="json") for p in instance.provider_catalog()],
                "profiles": [
                    p.model_dump(mode="json") for p in instance.validate_configuration().profiles
                ],
            },
            indent=2,
        )
    )


@app.command("agents")
def agents(
    data_dir: Path = DEFAULT_DATA_DIR, json_output: bool = typer.Option(False, "--json")
) -> None:
    """List versioned agent templates; use --json for exact metadata."""
    records = controller(data_dir).configuration().agents
    if json_output:
        typer.echo(json.dumps([a.model_dump(mode="json") for a in records], indent=2))
    else:
        for agent in records:
            typer.echo(
                f"{agent.display_name} v{agent.version} · {agent.agent.role.value} · "
                f"{agent.model_profile_id or 'offline / unassigned'}"
            )
        if not records:
            typer.echo(
                "No agent templates. Open doxa and choose Add agent template, or use agent-add."
            )


@app.command("profiles")
def profiles(
    data_dir: Path = DEFAULT_DATA_DIR, json_output: bool = typer.Option(False, "--json")
) -> None:
    """List saved model profiles without making inference calls."""
    records = controller(data_dir).configuration().profiles
    if json_output:
        typer.echo(json.dumps([p.model_dump(mode="json") for p in records], indent=2))
    else:
        for profile in records:
            typer.echo(
                f"{profile.id} v{profile.version} · {profile.provider} · {profile.model_id} · "
                f"{'enabled' if profile.enabled else 'disabled'}"
            )
        if not records:
            typer.echo("No model profiles. Open doxa and choose Choose model and connection.")


@app.command("recover")
def recover(run_id: UUID, data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Recover interrupted call states after cancellation; retain uncertain reservations."""
    typer.echo(controller(data_dir).recover_run(run_id).model_dump_json(indent=2))


@app.command("research-demo")
def research_demo(
    data_dir: Path = DEFAULT_DATA_DIR, json_output: bool = typer.Option(False, "--json")
) -> None:
    """Run the synthetic cache-policy research demonstration without model calls."""
    from doxa.core.research_demo import experiment

    instance = controller(data_dir)
    instance.initialize()
    result = experiment(instance)
    if json_output:
        typer.echo(json.dumps(result, indent=2))
    else:
        typer.echo("Synthetic cache-policy research demonstration completed.")
        typer.echo(f"Created {len(result['children'])} child trajectories; no live inference.")
        typer.echo(
            f"Memories retrieved before revocation: {len(result['retrieved_before_revocation'])}; "
            f"after revocation: {len(result['retrieved_after_revocation'])}."
        )
        for index, record in enumerate(result["metrics"], 1):
            typer.echo(
                f"Branch {index}: "
                + ", ".join(f"{name}={value}" for name, value in record["metrics"].items())
            )
        typer.echo(f"Run: {result['run_id']}. Use --json for full records.")


@app.command("compare-branches")
def compare_branches_command(
    run_id: UUID, baseline: UUID, treatment: UUID, data_dir: Path = DEFAULT_DATA_DIR
) -> None:
    """Compare two persisted trajectories in one run."""
    from doxa.core.comparison import compare_branches

    result = compare_branches(controller(data_dir), run_id, baseline, treatment)
    typer.echo(result.model_dump_json())


@app.command("research-command")
def research_command(
    run_id: UUID, branch_id: UUID, config: Path, data_dir: Path = DEFAULT_DATA_DIR
) -> None:
    """Apply a validated typed JSON research command to a selected run and branch."""
    adapter: TypeAdapter[Command] = TypeAdapter(cast(Any, Command))
    from doxa.core.secrets import reject_secrets

    try:
        raw = config.read_text(encoding="utf-8-sig")
        reject_secrets(raw)
        command = adapter.validate_json(raw)
    except (ValueError, OSError):
        raise typer.BadParameter("Research command file is invalid or secret-bearing") from None
    typer.echo(controller(data_dir).research_command(run_id, branch_id, command).model_dump_json())


@app.command("export-jsonl")
def export_jsonl(run_id: UUID, output: Path, data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Export the run manifest and original events as a new JSONL file."""
    from doxa.core.exports import export_jsonl as write_export

    write_export(controller(data_dir), run_id, output)


@app.command("compare")
def compare_runs(
    baseline: UUID,
    treatment: UUID,
    data_dir: Path = DEFAULT_DATA_DIR,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Compare persisted runs with explicit descriptive evaluation limitations."""
    from doxa.core.comparison import compare

    result = compare(controller(data_dir), baseline, treatment)
    if json_output:
        typer.echo(result.model_dump_json(indent=2))
    else:
        typer.echo(result.caveat)
        typer.echo(
            f"Added commitments: {len(result.added_commitments)}; "
            f"removed: {len(result.removed_commitments)}"
        )
        for label, metrics in (
            ("Baseline", result.baseline_metrics),
            ("Treatment", result.treatment_metrics),
        ):
            typer.echo(label + ": " + ", ".join(f"{k}={v}" for k, v in metrics.items()))


@app.command("profile-from-env")
def profile_from_env(version: int = 1, data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Register existing RunPod endpoint metadata from environment references; no inference."""
    from doxa.core.profiles import ModelProfile
    from doxa.core.secrets import local_env
    from doxa.providers.runpod import endpoint_url

    env = local_env()
    model = env.get("RUNPOD_MODEL_ID", "")
    if not model or model == "replace_me":
        raise typer.BadParameter("Set RUNPOD_MODEL_ID to the exact served model ID")
    profile = ModelProfile(
        id="runpod-profile",
        version=version,
        provider="runpod",
        model_id=model,
        endpoint_id=env.get("RUNPOD_ENDPOINT_ID"),
        base_url=env.get("RUNPOD_BASE_URL") or None,
        enabled=env.get("DOXA_RUNPOD_ENABLED", "false").lower() == "true",
    )
    endpoint_url(profile, env)
    controller(data_dir).save_configuration(CouncilConfig(profiles=(profile,)))
    typer.echo("Pinned RunPod model/endpoint metadata. No inference was requested.")


@app.command("config-import")
def config_import(config: Path, data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Import validated immutable agent/model configuration versions from JSON."""
    instance = controller(data_dir)
    command = read_contract(CouncilConfig, config)
    report = instance.validate_configuration(command)
    if not report.valid:
        typer.echo(report.model_dump_json(indent=2))
        raise typer.Exit(1)
    instance.save_configuration(command)
    typer.echo("Saved immutable agent/model configuration versions (no credential values).")


@app.command("config-list")
def config_list(data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Inspect the saved agent/model configuration as JSON; credentials remain references."""
    typer.echo(controller(data_dir).configuration().model_dump_json(indent=2))


@app.command("run-task")
def run_task(run_id: UUID, config: Path, data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Execute a configured finite cache task using a typed JSON execution contract."""
    command = read_contract(ExecuteTask, config)
    typer.echo(
        asyncio.run(controller(data_dir).execute_task(run_id, command)).model_dump_json(indent=2)
    )


@app.command()
def cancel(run_id: UUID, data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Record cancellation without claiming remote termination or a known final bill."""
    typer.echo(controller(data_dir).cancel(run_id).model_dump_json(indent=2))


@app.command("memory-propose")
def memory_propose(run_id: UUID, config: Path, data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Propose a quarantined memory using a typed JSON contract."""
    command = read_contract(ProposeMemory, config)
    typer.echo(controller(data_dir).propose_memory(run_id, command).model_dump_json(indent=2))


@app.command("memory-validate")
def memory_validate(run_id: UUID, memory_id: UUID, data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Run the registered deterministic validation for a memory proposal."""
    typer.echo(controller(data_dir).validate_memory(run_id, memory_id).model_dump_json(indent=2))


@app.command("memory-transition")
def memory_transition(
    run_id: UUID, memory_id: UUID, config: Path, data_dir: Path = DEFAULT_DATA_DIR
) -> None:
    """Apply an authorized typed JSON memory eligibility transition."""
    command = read_contract(TransitionMemory, config)
    typer.echo(
        controller(data_dir).transition_memory(run_id, memory_id, command).model_dump_json(indent=2)
    )


@app.command("memory-query")
def memory_query(run_id: UUID, config: Path, data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Query authorized memories using a typed JSON retrieval contract."""
    command = read_contract(RetrievalQuery, config)
    results = asyncio.run(retrieval_query(controller(data_dir), run_id, command))
    typer.echo(json.dumps([r.model_dump(mode="json") for r in results], indent=2))


@app.command()
def accounting(data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Inspect durable operation states, reservations and reported billing."""
    typer.echo(
        json.dumps(BudgetStore(controller(data_dir).settings.database_path).operations(), indent=2)
    )


@app.command()
def reconcile(operation_id: UUID, billed_usd: str, data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Record an operator-reported final charge; never infer zero from an error."""
    controller(data_dir).reconcile_charge(operation_id, Decimal(billed_usd))
    typer.echo("Operator-reported charge recorded; no external balance was inferred.")


def controller(data_dir: Path) -> Controller:
    instance = Controller(Settings(data_dir=data_dir))
    if not instance.settings.database_path.is_file():
        typer.echo(
            "Workspace missing. Select one with doxa, or run doxa init --data-dir PATH.",
            err=True,
        )
        raise typer.Exit(2)
    try:
        instance.initialize()
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from None
    return instance


@app.command()
def init(data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Explicitly initialize or migrate a workspace without replacing existing history."""
    Controller(Settings(data_dir=data_dir)).initialize(allow_create=True)
    typer.echo("Initialized local canonical ledger. No experiment executed.")


@app.command()
def configure(config: Path, data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Create a run from a typed JSON experiment configuration."""
    command = read_contract(ConfigureRun, config)
    typer.echo(controller(data_dir).configure_run(command).model_dump_json(indent=2))


@app.command()
def runs(
    data_dir: Path = DEFAULT_DATA_DIR, json_output: bool = typer.Option(False, "--json")
) -> None:
    """List persisted experiments/runs from the selected workspace."""
    instance = controller(data_dir)
    records = instance.list_runs()
    if json_output:
        typer.echo(json.dumps([r.model_dump(mode="json") for r in records]))
        return
    for run in records:
        experiment = instance.ledger.get(run.experiment_id)
        typer.echo(
            f"{getattr(experiment, 'name', 'Experiment')} · {run.status} · "
            f"{run.execution_kind} · {run.id}"
        )
    if not records:
        typer.echo(
            "No runs. Open doxa and choose Create experiment, "
            "or run doxa demo for an offline demonstration."
        )


@app.command()
def inspect(
    run_id: UUID,
    data_dir: Path = DEFAULT_DATA_DIR,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Inspect one persisted run and its event history."""
    instance = controller(data_dir)
    bundle = instance.inspect(run_id)
    if json_output:
        typer.echo(bundle.model_dump_json(indent=2))
        return
    experiment = instance.ledger.get(bundle.run.experiment_id)
    typer.echo(
        f"{getattr(experiment, 'name', 'Experiment')} · {bundle.run.status} · "
        f"{bundle.run.execution_kind}"
    )
    typer.echo(f"{len(bundle.events)} committed events. Run: {bundle.run.id}")
    typer.echo(
        "Use --json for exact records, or open doxa and choose Review branch and revise claims."
    )


@app.command()
def export(run_id: UUID, output: Path, data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Export exact run history to a new JSON file without overwriting existing files."""
    from doxa.core.exports import export_run

    typer.echo(str(export_run(controller(data_dir), run_id, output)))


@app.command()
def serve(data_dir: Path = DEFAULT_DATA_DIR, port: int = 8000) -> None:
    """Start the retained local loopback API for development; no inference is implicit."""
    import uvicorn

    from doxa.api.app import create_app

    settings = Settings(data_dir=data_dir, api_port=port)
    instance = Controller(settings)
    instance.initialize()
    if not instance.validate_configuration().valid:
        typer.echo(
            "Some provider profiles need attention; use validate-config. "
            "Inspection remains available."
        )
    uvicorn.run(create_app(settings), host=settings.api_host, port=settings.api_port)


install_workbench(app)


def version_callback(value: bool) -> None:
    if value:
        from doxa.version import version_string

        typer.echo(version_string())
        raise typer.Exit()


@app.callback()
def default_console(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show the application and terminal build version.",
    ),
) -> None:
    if ctx.invoked_subcommand is None:
        from doxa.cli.console import ResearchConsole

        ResearchConsole(Settings().data_dir).run()


@app.command("workspace-path")
def workspace_path(
    data_dir: Path = DEFAULT_DATA_DIR, json_output: bool = typer.Option(False, "--json")
) -> None:
    """Show the canonical workspace path and recent selections without creating a ledger."""
    from doxa.core.workspaces import recent_workspaces

    path = data_dir.expanduser().resolve()
    result = {
        "workspace": str(path),
        "ledger_exists": (path / "ledger.sqlite3").is_file(),
        "recent": [str(p) for p in recent_workspaces()],
    }
    typer.echo(
        json.dumps(result, indent=2)
        if json_output
        else f"Workspace: {path}\nLedger present: {result['ledger_exists']}"
    )


@app.command("workspace-open")
def workspace_open(path: Path) -> None:
    """Select a validated existing workspace; never merge unrelated histories."""
    from doxa.core.workspaces import remember_workspace

    try:
        remember_workspace(path)
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from None
    typer.echo(
        f"Workspace selected: {path.expanduser().resolve()}. Existing histories remain separate."
    )


@app.command("check-workspace")
def check_workspace(data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Verify SQLite, event/index projections and referenced artifact integrity."""
    from doxa.storage.integrity import verify_workspace

    typer.echo(json.dumps(verify_workspace(data_dir), indent=2))


@app.command("backup-workspace")
def backup_workspace_command(destination: Path, data_dir: Path = DEFAULT_DATA_DIR) -> None:
    """Create a verified private workspace snapshot without credentials."""
    from doxa.storage.backup import backup_workspace

    typer.echo(json.dumps(backup_workspace(data_dir, destination), indent=2))


@app.command("restore-workspace")
def restore_workspace_command(backup: Path, destination: Path) -> None:
    """Restore a verified snapshot into a new destination; never overwrite or merge."""
    from doxa.storage.backup import restore_workspace

    typer.echo(json.dumps(restore_workspace(backup, destination), indent=2))


@app.command("reconcile-local")
def reconcile_local(
    call_id: UUID, evidence: Path, confirm_stopped: bool = False, data_dir: Path = DEFAULT_DATA_DIR
) -> None:
    """Record explicit stopped-process evidence for an ambiguous local call."""
    controller(data_dir).reconcile_local_call(
        call_id,
        evidence=evidence.read_text(encoding="utf-8-sig"),
        confirmed_stopped=confirm_stopped,
    )
    typer.echo(
        "Local stop attestation recorded. This does not replay a call or claim a model result."
    )
