"""Pure request accounting shared by context selection and offline stress planning."""

import json
from dataclasses import dataclass
from typing import Any

from doxa.providers.contracts import ModelMessage


def cli_prompt(messages: tuple[ModelMessage, ...]) -> bytes:
    return (
        "DOXA text research. Tools are disabled. Return only the requested final response.\n"
        + json.dumps([m.model_dump() for m in messages], ensure_ascii=False)
    ).encode()


def input_size(messages: tuple[ModelMessage, ...], schema: dict[str, Any] | None, cli: bool) -> int:
    envelope = (
        len(cli_prompt(messages)) if cli else sum(len(m.content.encode()) + 32 for m in messages)
    )
    return envelope + len(json.dumps(schema or {}).encode())


@dataclass(frozen=True)
class ContextBudget:
    context: int
    input_bytes: int
    output: int
    schema: dict[str, Any] | None = None
    cli: bool = False
    agent_remaining: int | None = None
    total_remaining: int | None = None

    def measure(self, system: str, user: str) -> int:
        return input_size(
            (ModelMessage(role="system", content=system), ModelMessage(role="user", content=user)),
            self.schema,
            self.cli,
        )

    def ceiling(self) -> int:
        return min(
            self.context,
            self.agent_remaining if self.agent_remaining is not None else self.context,
            self.total_remaining if self.total_remaining is not None else self.context,
        )

    def fits(self, system: str, user: str) -> bool:
        size = self.measure(system, user)
        return size <= self.input_bytes and size + self.output <= self.ceiling()

    def require(self, system: str, user: str, component: str) -> None:
        if not self.fits(system, user):
            raise ValueError(
                f"Context budget cannot fit {component}: "
                f"serialized_input={self.measure(system, user)}, "
                f"schema={len(json.dumps(self.schema or {}).encode())}, "
                f"reserved_output={self.output}, input_byte_limit={self.input_bytes}, "
                f"context_limit={self.context}, agent_remaining={self.agent_remaining}, "
                f"aggregate_remaining={self.total_remaining}"
            )
