from typing import Protocol
from uuid import UUID

from doxa.core.models import Evaluation


class Evaluator(Protocol):
    version: str

    async def evaluate(self, run_id: UUID) -> Evaluation: ...
