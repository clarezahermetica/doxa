import hashlib
from decimal import Decimal
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid5

from pydantic import Field

from doxa.core.models import Contract, Memory
from doxa.core.secrets import workspace_env
from doxa.retrieval.backends import MossRetrieval
from doxa.storage.budget import BudgetStore
from doxa.systems.memory import eligible

if TYPE_CHECKING:
    from doxa.core.controller import Controller


class RetrievalQuery(Contract):
    agent_id: UUID
    query: str = Field(min_length=1, max_length=2000)
    conditions: tuple[str, ...] = ()
    backend: Literal["local", "moss"] = "local"
    authorize_paid: bool = False
    authorize_private_upload: bool = False
    upper_bound_usd: Decimal | None = Field(default=None, gt=0, le=75)
    idempotency_key: str = Field(min_length=1, max_length=200)


async def query(
    controller: "Controller", run_id: UUID, command: RetrievalQuery
) -> tuple[Memory, ...]:
    if command.backend == "local":
        return await controller.retrieve_memory(
            run_id, command.agent_id, command.query, conditions=command.conditions
        )
    controller.participant_records(run_id, command.agent_id)
    env = workspace_env(controller.settings.data_dir)
    if env.get("DOXA_MOSS_ENABLED", "false").lower() != "true" or not command.authorize_paid:
        raise PermissionError("Moss is disabled or live authorization is missing")
    if command.upper_bound_usd is None:
        raise ValueError("Moss session requires a known complete cost upper bound")
    project_id = env.get("MOSS_PROJECT_ID")
    project_key = env.get("MOSS_PROJECT_KEY")
    if not project_id or not project_key or project_key == "replace_me":
        raise ValueError("Missing Moss backend configuration")
    memories = eligible(controller.ledger, run_id, command.agent_id, command.conditions)
    if not command.authorize_private_upload and any(m.scope == "private" for m in memories):
        raise PermissionError("Private memory upload needs explicit authorization")
    budgets = BudgetStore(controller.settings.database_path)
    identity = uuid5(run_id, "moss:" + command.idempotency_key)
    budgets.reserve(
        run_id,
        identity,
        command.upper_bound_usd,
        service="moss",
        service_cap_usd=Decimal(env.get("DOXA_MOSS_ALLOWANCE_USD", "0")),
        request_hash=hashlib.sha256(command.model_dump_json().encode()).hexdigest(),
    )
    budgets.dispatch_once(identity)
    backend = MossRetrieval(
        project_id,
        project_key,
        "eligible-memories",
        authorized=True,
        cache_dir=controller.settings.data_dir
        / "retrieval-cache"
        / hashlib.sha256(f"{project_id}:{run_id}:{command.agent_id}".encode()).hexdigest(),
    )
    try:
        result = await controller.retrieve_memory(
            run_id, command.agent_id, command.query, backend, command.conditions
        )
        budgets.finish(identity, "completed")
        return result
    except BaseException:
        budgets.finish(identity, "uncertain")
        raise
    finally:
        try:
            await backend.close()
        except Exception:
            # Closing can include usage reporting; retain unknown billing, never zero it.
            pass
