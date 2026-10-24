import asyncio
import hashlib
import importlib
from collections.abc import Callable
from typing import Any, Protocol
from uuid import UUID

from doxa.core.models import Memory


def snapshot(memories: tuple[Memory, ...]) -> str:
    return hashlib.sha256("\n".join(m.model_dump_json() for m in memories).encode()).hexdigest()


class RetrievalBackend(Protocol):
    name: str
    index_version: str | None

    async def rebuild(self, memories: tuple[Memory, ...]) -> None: ...
    async def query(self, query: str, limit: int) -> tuple[UUID, ...]: ...


class LocalRetrieval:
    name = "local_keyword"
    index_version: str | None = None

    def __init__(self) -> None:
        self.memories: tuple[Memory, ...] = ()

    async def rebuild(self, memories: tuple[Memory, ...]) -> None:
        self.memories = memories
        self.index_version = snapshot(memories)

    async def query(self, query: str, limit: int) -> tuple[UUID, ...]:
        words = set(query.lower().split())
        ranked = sorted(
            self.memories,
            key=lambda m: (-len(words.intersection(m.text.lower().split())), str(m.id)),
        )
        return tuple(m.id for m in ranked if words.intersection(m.text.lower().split()))[:limit]


class MossRetrieval:
    """Lazy official Python SDK. No cloud synchronization or paid call at import.

    Each instance is scoped to one run/agent; never reuse a session across principals.
    The caller must authorize and reserve the complete session before calling rebuild.
    """

    name = "moss"
    index_version: str | None = None

    def __init__(
        self,
        project_id: str,
        project_key: str,
        index_name: str,
        *,
        authorized: bool = False,
        sdk_factory: Callable[..., Any] | None = None,
        timeout_seconds: float = 30,
        sdk_module: Any = None,
    ):
        self.project_id = project_id
        self._project_key = project_key
        self.index_name = index_name
        self.authorized = authorized
        self.sdk_factory = sdk_factory
        self.timeout_seconds = timeout_seconds
        self.sdk_module = sdk_module
        self.client: Any = None
        self.session: Any = None

    async def rebuild(self, memories: tuple[Memory, ...]) -> None:
        if not self.authorized:
            raise PermissionError("Moss live session requires separate authorization")
        sdk = self.sdk_module or importlib.import_module("moss")
        factory = self.sdk_factory or sdk.MossClient
        self.client = factory(self.project_id, self._project_key)
        async with asyncio.timeout(self.timeout_seconds):
            self.session = await self.client.session(
                index_name=self.index_name,
                auto_load_on_init=False,
            )
            await self.session.add_docs(
                [sdk.DocumentInfo(id=str(m.id), text=m.text) for m in memories]
            )
        self.index_version = snapshot(memories)

    async def query(self, query: str, limit: int) -> tuple[UUID, ...]:
        if self.session is None:
            raise RuntimeError("Moss index not built")
        sdk = self.sdk_module or importlib.import_module("moss")
        async with asyncio.timeout(self.timeout_seconds):
            result = await self.session.query(query, sdk.QueryOptions(top_k=limit))
        return tuple(UUID(doc.id) for doc in result.docs)

    async def close(self) -> None:
        if self.client is not None:
            async with asyncio.timeout(self.timeout_seconds):
                await self.client.close()
