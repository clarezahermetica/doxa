import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
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
from doxa.core.models import Contract, Event, Memory, Record, Run, Verification
from doxa.core.profiles import CouncilConfig
from doxa.core.research_commands import Command
from doxa.core.retrieval_commands import RetrievalQuery
from doxa.core.retrieval_commands import query as retrieval_query
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

    app = FastAPI(title="DOXA foundation", version="0.1.0a0", lifespan=lifespan)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )
    # No CORS: Vite proxies /api; unsolicited cross-origin JSON writes fail preflight.

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "stage": "backend-prototype", "execution": "cache-policy-v1"}

    @app.get("/api/configuration", response_model=CouncilConfig)
    def configuration() -> CouncilConfig:
        return controller.configuration()

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
        BudgetStore(controller.settings.database_path).reconcile(operation_id, command.billed_usd)

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
