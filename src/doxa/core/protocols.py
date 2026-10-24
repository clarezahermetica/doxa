from typing import Protocol
from uuid import UUID

from doxa.core.models import Agent, ProtocolMode


class CouncilProtocol(Protocol):
    mode: ProtocolMode

    async def execute(self, run_id: UUID, agents: tuple[Agent, ...]) -> None: ...


# Runtime implementations are currently restricted to the finite cache-policy v1 task.
PROTOCOL_STATUS = dict.fromkeys(ProtocolMode, "cache_policy_v1_prototype")
