import asyncio
import json
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import typer
from pydantic import TypeAdapter

from doxa.core.config import Settings
from doxa.core.controller import ConfigureRun, Controller
from doxa.core.execution import ExecuteTask
from doxa.core.memory_commands import ProposeMemory, TransitionMemory
from doxa.core.profiles import CouncilConfig
from doxa.core.research_commands import Command
from doxa.core.retrieval_commands import RetrievalQuery
from doxa.core.retrieval_commands import query as retrieval_query
from doxa.storage.budget import BudgetStore

app = typer.Typer(no_args_is_help=True)


@app.command("research-demo")
def research_demo(data_dir: Path = Path(".doxa")) -> None:
    from doxa.core.research_demo import experiment

    instance = controller(data_dir)
    instance.initialize()
    typer.echo(json.dumps(experiment(instance), indent=2))


@app.command("compare-branches")
def compare_branches_command(
    run_id: UUID, baseline: UUID, treatment: UUID, data_dir: Path = Path(".doxa")
) -> None:
    from doxa.core.comparison import compare_branches

    result = compare_branches(controller(data_dir), run_id, baseline, treatment)
    typer.echo(result.model_dump_json())


@app.command("research-command")
def research_command(
    run_id: UUID, branch_id: UUID, config: Path, data_dir: Path = Path(".doxa")
) -> None:
    adapter: TypeAdapter[Command] = TypeAdapter(Command)  # type: ignore[arg-type]
    command = adapter.validate_json(config.read_text(encoding="utf-8"))
    typer.echo(controller(data_dir).research_command(run_id, branch_id, command).model_dump_json())


@app.command("export-jsonl")
def export_jsonl(run_id: UUID, output: Path, data_dir: Path = Path(".doxa")) -> None:
    bundle = controller(data_dir).inspect(run_id)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(
            json.dumps(
                {
                    "kind": "export_manifest",
                    "schema_version": 1,
                    "run": bundle.run.model_dump(mode="json"),
                    "accounting": bundle.accounting,
                }
            )
            + "\n"
        )
        for event in bundle.events:
            stream.write(event.model_dump_json() + "\n")


@app.command("compare")
def compare_runs(baseline: UUID, treatment: UUID, data_dir: Path = Path(".doxa")) -> None:
    from doxa.core.comparison import compare

    typer.echo(compare(controller(data_dir), baseline, treatment).model_dump_json(indent=2))


@app.command("profile-from-env")
def profile_from_env(version: int = 1, data_dir: Path = Path(".doxa")) -> None:
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
def config_import(config: Path, data_dir: Path = Path(".doxa")) -> None:
    controller(data_dir).save_configuration(
        CouncilConfig.model_validate_json(config.read_text(encoding="utf-8"))
    )
    typer.echo("Saved immutable agent/model configuration versions (no credential values).")


@app.command("config-list")
def config_list(data_dir: Path = Path(".doxa")) -> None:
    typer.echo(controller(data_dir).configuration().model_dump_json(indent=2))


@app.command("run-task")
def run_task(run_id: UUID, config: Path, data_dir: Path = Path(".doxa")) -> None:
    command = ExecuteTask.model_validate_json(config.read_text(encoding="utf-8"))
    typer.echo(
        asyncio.run(controller(data_dir).execute_task(run_id, command)).model_dump_json(indent=2)
    )


@app.command()
def cancel(run_id: UUID, data_dir: Path = Path(".doxa")) -> None:
    typer.echo(controller(data_dir).cancel(run_id).model_dump_json(indent=2))


@app.command("memory-propose")
def memory_propose(run_id: UUID, config: Path, data_dir: Path = Path(".doxa")) -> None:
    command = ProposeMemory.model_validate_json(config.read_text(encoding="utf-8"))
    typer.echo(controller(data_dir).propose_memory(run_id, command).model_dump_json(indent=2))


@app.command("memory-validate")
def memory_validate(run_id: UUID, memory_id: UUID, data_dir: Path = Path(".doxa")) -> None:
    typer.echo(controller(data_dir).validate_memory(run_id, memory_id).model_dump_json(indent=2))


@app.command("memory-transition")
def memory_transition(
    run_id: UUID, memory_id: UUID, config: Path, data_dir: Path = Path(".doxa")
) -> None:
    command = TransitionMemory.model_validate_json(config.read_text(encoding="utf-8"))
    typer.echo(
        controller(data_dir).transition_memory(run_id, memory_id, command).model_dump_json(indent=2)
    )


@app.command("memory-query")
def memory_query(run_id: UUID, config: Path, data_dir: Path = Path(".doxa")) -> None:
    command = RetrievalQuery.model_validate_json(config.read_text(encoding="utf-8"))
    results = asyncio.run(retrieval_query(controller(data_dir), run_id, command))
    typer.echo(json.dumps([r.model_dump(mode="json") for r in results], indent=2))


@app.command()
def accounting(data_dir: Path = Path(".doxa")) -> None:
    typer.echo(
        json.dumps(BudgetStore(controller(data_dir).settings.database_path).operations(), indent=2)
    )


@app.command()
def reconcile(operation_id: UUID, billed_usd: str, data_dir: Path = Path(".doxa")) -> None:
    BudgetStore(controller(data_dir).settings.database_path).reconcile(
        operation_id, Decimal(billed_usd)
    )
    typer.echo("Operator-reported charge recorded; no external balance was inferred.")


def controller(data_dir: Path) -> Controller:
    return Controller(Settings(data_dir=data_dir))


@app.command()
def init(data_dir: Path = Path(".doxa")) -> None:
    controller(data_dir).initialize()
    typer.echo("Initialized local canonical ledger. No experiment executed.")


@app.command()
def configure(config: Path, data_dir: Path = Path(".doxa")) -> None:
    command = ConfigureRun.model_validate_json(config.read_text(encoding="utf-8"))
    typer.echo(controller(data_dir).configure_run(command).model_dump_json(indent=2))


@app.command()
def runs(data_dir: Path = Path(".doxa")) -> None:
    for run in controller(data_dir).list_runs():
        typer.echo(run.model_dump_json())


@app.command()
def inspect(run_id: UUID, data_dir: Path = Path(".doxa")) -> None:
    typer.echo(controller(data_dir).inspect(run_id).model_dump_json(indent=2))


@app.command()
def export(run_id: UUID, output: Path, data_dir: Path = Path(".doxa")) -> None:
    content = controller(data_dir).inspect(run_id).model_dump_json(indent=2)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(content)
    typer.echo(str(output.resolve()))


@app.command()
def serve(data_dir: Path = Path(".doxa"), port: int = 8000) -> None:
    import uvicorn

    from doxa.api.app import create_app

    settings = Settings(data_dir=data_dir, api_port=port)
    uvicorn.run(create_app(settings), host=settings.api_host, port=settings.api_port)
