import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import cast
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import Field

from doxa.core.comparison import BranchComparison, Comparison, compare, compare_branches
from doxa.core.config import Settings
from doxa.core.controller import CapabilityUnavailable, ConfigureRun, Controller, RunBundle
from doxa.core.execution import ExecuteTask
from doxa.core.memory_commands import ProposeMemory, TransitionMemory
from doxa.core.models import (
    Claim,
    Contract,
    Event,
    Memory,
    Record,
    Run,
    SourceDocument,
    Verification,
)
from doxa.core.profiles import AgentDefinition, CouncilConfig
from doxa.core.readiness import InstallationReadiness, inspect_readiness
from doxa.core.research_commands import Command
from doxa.core.retrieval_commands import RetrievalQuery
from doxa.core.retrieval_commands import query as retrieval_query
from doxa.providers.registry import ConfigurationReport, ProviderDescriptor
from doxa.storage.budget import BudgetStore
from doxa.storage.ledger import LedgerConflict


class MemoryQuery(Contract):
    agent_id: UUID
    query: str = Field(min_length=1, max_length=2000)
    conditions: tuple[str, ...] = ()


class ReconcileCharge(Contract):
    billed_usd: Decimal = Field(ge=0)


def create_app(settings: Settings | None = None) -> FastAPI:
    controller = Controller(settings or Settings())
    tasks: dict[UUID, asyncio.Task[RunBundle]] = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        controller.initialize()
        yield
        # Closing the local API cancels its waits and persists cancellation; this
        # is not a claim that remote jobs/billing have been canceled.
        active = list(tasks.items())
        for run_id, task in active:
            if controller.inspect(run_id).run.status == "running":
                controller.cancel(run_id)
            task.cancel()
        if active:
            await asyncio.gather(*(task for _, task in active), return_exceptions=True)

    app = FastAPI(title="DOXA foundation", version="0.1.0a0", lifespan=lifespan)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )
    # No CORS: Vite proxies /api; unsolicited cross-origin JSON writes fail preflight.

    from fastapi.responses import StreamingResponse
    from starlette.middleware.base import RequestResponseEndpoint
    from starlette.responses import Response

    from doxa.core.workbench import (
        DebateExecution,
        DebateRuntime,
        ImportDocument,
        ImportSource,
        NewAgent,
        NewExperiment,
        ReviseClaim,
        add_agent,
        create_experiment,
        import_document,
        import_source,
        revise_claim,
    )

    @app.middleware("http")
    async def local_origin(request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Browser requests from another origin cannot read or mutate local research state.
        origin = request.headers.get("origin")
        expected = str(request.base_url).rstrip("/")
        allowed_origins = {expected}
        if controller.settings.development_studio:
            allowed_origins.add("http://127.0.0.1:5173")
        if origin and origin not in allowed_origins:
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=403, content={"detail": "Cross-origin request refused"})
        return await call_next(request)

    from doxa.core.models import ToolAudit
    from doxa.core.web_tools import ToolRequest, use_tool

    @app.post("/api/workbench/runs/{run_id}/tools", response_model=ToolAudit)
    async def web_tool(run_id: UUID, command: ToolRequest) -> ToolAudit:
        return await use_tool(controller, run_id, command)

    from doxa.core.text_research import ReviewCommand, ReviewWorkspace

    @app.get("/api/workbench/runs/{run_id}/branches/{branch_id}", response_model=ReviewWorkspace)
    def review_workspace(run_id: UUID, branch_id: UUID) -> ReviewWorkspace:
        return controller.review_workspace(run_id, branch_id)

    @app.post("/api/workbench/runs/{run_id}/branches/{branch_id}/commands", response_model=Event)
    def review_command(run_id: UUID, branch_id: UUID, command: ReviewCommand) -> Event:
        return controller.review_command(run_id, branch_id, command)

    @app.post("/api/workbench/demo")
    async def offline_demo() -> dict[str, str | int]:
        from doxa.core.workbench_demo import demonstrate

        return await demonstrate(controller)

    @app.post("/api/workbench/agents", response_model=AgentDefinition)
    def new_agent(command: NewAgent) -> AgentDefinition:
        return add_agent(controller, command)

    @app.post("/api/workbench/experiments", response_model=Run, status_code=201)
    def new_experiment(command: NewExperiment) -> Run:
        return create_experiment(controller, command)

    @app.post("/api/workbench/runs/{run_id}/sources")
    def ingest_source(run_id: UUID, command: ImportSource) -> SourceDocument:
        return import_source(controller, run_id, command)

    @app.post("/api/workbench/runs/{run_id}/documents", response_model=SourceDocument)
    def ingest_document(run_id: UUID, command: ImportDocument) -> SourceDocument:
        return import_document(controller, run_id, command)

    @app.get("/api/workbench/runs/{run_id}/sources/{source_id}")
    def source_content(run_id: UUID, source_id: UUID) -> dict[str, str]:
        from doxa.storage.artifacts import ArtifactStore

        source = controller.ledger.get(source_id)
        if not isinstance(source, SourceDocument) or source.run_id != run_id:
            raise KeyError("Source not found")
        text = (
            ArtifactStore(controller.settings.data_dir / "artifacts").get(source.content).decode()
        )
        return {"title": source.title, "text": text, "source": source.source}

    @app.get("/api/workbench/runs/{run_id}/contexts/{manifest_id}")
    def context_content(run_id: UUID, manifest_id: UUID) -> list[dict[str, str]]:
        import json

        from doxa.core.models import ContextManifest
        from doxa.storage.artifacts import ArtifactStore

        record = controller.ledger.get(manifest_id)
        if not isinstance(record, ContextManifest) or record.run_id != run_id:
            raise KeyError("Context not found")
        return cast(
            list[dict[str, str]],
            json.loads(
                ArtifactStore(controller.settings.data_dir / "artifacts").get(record.messages)
            ),
        )

    @app.post("/api/workbench/runs/{run_id}/claims/revise")
    def revise(run_id: UUID, command: ReviseClaim) -> Claim:
        return revise_claim(controller, run_id, command)

    @app.post("/api/workbench/runs/{run_id}/start", status_code=202)
    async def start_debate(run_id: UUID, command: DebateExecution) -> dict[str, str]:
        runtime = DebateRuntime(controller, run_id)
        if run_id in tasks or runtime.run.status != "configured":
            raise HTTPException(409, "Run already started")
        if runtime.run.execution_kind == "live" and not (
            command.authorize_paid and command.authorize_external
        ):
            raise PermissionError("Explicit paid and disclosure authorization required")
        if (
            runtime.experiment.task is None
            or runtime.experiment.task.task_type != "research_debate"
        ):
            raise ValueError("Research-debate task required")
        task = asyncio.create_task(runtime.execute_debate(command))
        tasks[run_id] = task

        def done(finished: asyncio.Task[RunBundle]) -> None:
            tasks.pop(run_id, None)
            if not finished.cancelled():
                finished.exception()  # Failures are recorded; avoid unobserved task exceptions.

        task.add_done_callback(done)
        return {"run_id": str(run_id), "status": "accepted"}

    @app.get("/api/runs/{run_id}/events")
    async def events(
        run_id: UUID, request: Request, after: str | None = None, follow: bool = True
    ) -> StreamingResponse:
        bundle = controller.inspect(run_id)
        cursor = after or request.headers.get("last-event-id")
        ids = [str(e.id) for e in bundle.events]
        if cursor and cursor not in ids:
            raise HTTPException(409, "Cursor is not in this run")
        start = ids.index(cursor) + 1 if cursor else 0

        async def committed_events() -> AsyncIterator[str]:
            offset = start
            while True:
                current = controller.inspect(run_id)
                for event in current.events[offset:]:
                    yield f"id: {event.id}\nevent: ledger\ndata: {event.model_dump_json()}\n\n"
                    offset += 1
                if not follow or getattr(request.app.state, "closing", False):
                    return
                if await request.is_disconnected():
                    return
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(
            committed_events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "stage": "backend-prototype", "execution": "cache-policy-v1"}

    @app.get("/api/configuration", response_model=CouncilConfig)
    def configuration() -> CouncilConfig:
        return controller.configuration()

    @app.get("/api/readiness", response_model=InstallationReadiness)
    def readiness() -> InstallationReadiness:
        return inspect_readiness(controller)

    @app.get("/api/providers", response_model=list[ProviderDescriptor])
    def providers() -> list[ProviderDescriptor]:
        return list(controller.provider_catalog())

    @app.post("/api/configuration/validate", response_model=ConfigurationReport)
    def validate_configuration(config: CouncilConfig | None = None) -> ConfigurationReport:
        return controller.validate_configuration(config)

    @app.post("/api/configuration", status_code=204)
    def save_configuration(config: CouncilConfig) -> None:
        controller.save_configuration(config)

    @app.post("/api/runs", response_model=Run, status_code=201)
    def configure_run(command: ConfigureRun) -> Run:
        try:
            return controller.configure_run(command)
        except (LedgerConflict, ValueError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/runs", response_model=list[Run])
    def runs() -> list[Run]:
        return controller.list_runs()

    @app.post("/api/runs/{run_id}/branches/{branch_id}/commands", response_model=Event)
    def research_command(run_id: UUID, branch_id: UUID, command: Command) -> Event:
        return controller.research_command(run_id, branch_id, command)

    @app.get("/api/compare", response_model=Comparison)
    def compare_runs(baseline: UUID, treatment: UUID) -> Comparison:
        return compare(controller, baseline, treatment)

    @app.get("/api/runs/{run_id}/compare-branches", response_model=BranchComparison)
    def branch_comparison(run_id: UUID, baseline: UUID, treatment: UUID) -> BranchComparison:
        return compare_branches(controller, run_id, baseline, treatment)

    @app.get("/api/runs/{run_id}", response_model=RunBundle)
    def inspect(run_id: UUID) -> RunBundle:
        try:
            return controller.inspect(run_id)
        except KeyError as exc:
            raise HTTPException(404, "Run not found") from exc

    @app.get("/api/runs/{run_id}/export", response_model=RunBundle)
    def export(run_id: UUID) -> RunBundle:
        return inspect(run_id)

    @app.post("/api/runs/{run_id}/execute")
    async def execute(run_id: UUID, command: ExecuteTask | None = None) -> RunBundle | None:
        try:
            if run_id in tasks:
                raise HTTPException(409, "Run already has an active local executor")
            if command is None:
                controller.execute(run_id)
                return None
            task = asyncio.create_task(controller.execute_task(run_id, command))
            tasks[run_id] = task
            try:
                return await task
            finally:
                if tasks.get(run_id) is task:
                    tasks.pop(run_id, None)
        except asyncio.CancelledError as exc:
            raise HTTPException(409, "Run cancelled; remote billing may remain unknown") from exc
        except KeyError as exc:
            raise HTTPException(404, "Run not found") from exc
        except CapabilityUnavailable as exc:
            raise HTTPException(501, str(exc)) from exc

    @app.post("/api/runs/{run_id}/cancel", response_model=RunBundle)
    async def cancel(run_id: UUID) -> RunBundle:
        bundle = controller.cancel(run_id)
        task = tasks.get(run_id)
        if task:
            task.cancel()
        return bundle

    @app.post("/api/runs/{run_id}/recover", response_model=RunBundle)
    def recover(run_id: UUID) -> RunBundle:
        return controller.recover_run(run_id)

    @app.get("/api/runs/{run_id}/participants/{agent_id}/records", response_model=list[Record])
    def participant_records(run_id: UUID, agent_id: UUID) -> list[Record]:
        return list(controller.participant_records(run_id, agent_id))

    @app.post("/api/runs/{run_id}/memories", response_model=Memory)
    def propose_memory(run_id: UUID, command: ProposeMemory) -> Memory:
        return controller.propose_memory(run_id, command)

    @app.post("/api/runs/{run_id}/memories/{memory_id}/validate", response_model=Verification)
    def validate_memory(run_id: UUID, memory_id: UUID) -> Verification:
        return controller.validate_memory(run_id, memory_id)

    @app.post("/api/runs/{run_id}/memories/{memory_id}/transition", response_model=Memory)
    def transition_memory(run_id: UUID, memory_id: UUID, command: TransitionMemory) -> Memory:
        return controller.transition_memory(run_id, memory_id, command)

    @app.post("/api/runs/{run_id}/memories/query", response_model=list[Memory])
    async def query_memory(run_id: UUID, command: RetrievalQuery) -> list[Memory]:
        return list(await retrieval_query(controller, run_id, command))

    @app.get("/api/accounting")
    def accounting() -> list[dict[str, str | int | None]]:
        return BudgetStore(controller.settings.database_path).operations()

    @app.post("/api/accounting/{operation_id}/reconcile", status_code=204)
    def reconcile(operation_id: UUID, command: ReconcileCharge) -> None:
        controller.reconcile_charge(operation_id, command.billed_usd)

    # Local operator API; participant views constrain context, not authentication identity.
    from fastapi.responses import JSONResponse

    @app.exception_handler(ValueError)
    async def invalid_command(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=409, content={"detail": "Command rejected by contract/state validation"}
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422, content={"detail": "Request does not match the typed contract"}
        )

    @app.exception_handler(PermissionError)
    async def forbidden(request: Request, exc: PermissionError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": "Operation not authorized"})

    @app.exception_handler(KeyError)
    async def missing(request: Request, exc: KeyError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Record not found"})

    @app.exception_handler(RuntimeError)
    async def operation_failed(request: Request, exc: RuntimeError) -> JSONResponse:
        return JSONResponse(
            status_code=502, content={"detail": "Operation failed; inspect persisted run"}
        )

    return app
