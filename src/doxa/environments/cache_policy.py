"""Versioned finite-policy task. No user code, shell, eval, or subprocess execution."""

import hashlib
import json
from typing import Literal, Self

from pydantic import Field, model_validator

from doxa.core.models import Contract


class Candidate(Contract):
    policy: Literal["invalidate_all", "stale_on_update", "stale_on_delete"]


class CacheFixture(Contract):
    id: Literal["cache-policy"] = "cache-policy"
    version: Literal["1"] = "1"
    cases: tuple[Literal["update", "delete", "read"], ...] = ("read", "update", "delete")

    @model_validator(mode="after")
    def pinned_v1_oracle(self) -> Self:
        if self.cases != ("read", "update", "delete"):
            raise ValueError(
                "cache-policy v1 requires the full fixed oracle; use a new version for changes"
            )
        return self


class CacheState(Contract):
    policy: Candidate
    values: dict[str, int] = Field(default_factory=lambda: {"x": 1})
    cache: dict[str, int | None] = Field(default_factory=dict)


class CacheEnvironment:
    def __init__(self, candidate: Candidate):
        self.state = CacheState(policy=candidate)

    def read(self, key: str) -> int | None:
        if key not in self.state.cache:
            self.state.cache[key] = self.state.values.get(key)
        return self.state.cache[key]

    def update(self, key: str, value: int) -> None:
        self.state.values[key] = value
        if self.state.policy.policy != "stale_on_update":
            self.state.cache.pop(key, None)

    def delete(self, key: str) -> None:
        self.state.values.pop(key, None)
        if self.state.policy.policy != "stale_on_delete":
            self.state.cache.pop(key, None)

    def snapshot(self) -> bytes:
        return self.state.model_dump_json().encode()

    @classmethod
    def restore(cls, data: bytes) -> "CacheEnvironment":
        state = CacheState.model_validate_json(data)
        restored = cls(state.policy)
        restored.state = state
        if restored.snapshot() != data:
            raise ValueError("Restored observable state differs from checkpoint")
        return restored


def verify(fixture: CacheFixture, candidate: Candidate) -> dict[str, bool]:
    """Fresh environment for each test; oracle expectations never come from a model."""
    results: dict[str, bool] = {}
    for case in fixture.cases:
        env = CacheEnvironment(candidate)
        first = env.read("x")
        if case == "update":
            env.update("x", 2)
            results[case] = first == 1 and env.read("x") == 2
        elif case == "delete":
            env.delete("x")
            results[case] = first == 1 and env.read("x") is None
        else:
            results[case] = first == 1 and env.read("x") == 1
    return results


def fixture_hash(fixture: CacheFixture) -> str:
    return hashlib.sha256(json.dumps(fixture.model_dump(), sort_keys=True).encode()).hexdigest()
