import asyncio
import hashlib
import importlib
from collections.abc import Callable
from pathlib import Path
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
    name = "local_keyword"  # Compatibility name; ranking now uses SQLite FTS5 BM25.
    index_version: str | None = None

    def __init__(self, database: Path | None = None) -> None:
        self.database = database
        self.memories: tuple[Memory, ...] = ()

    async def rebuild(self, memories: tuple[Memory, ...]) -> None:
        self.memories = memories
        self.index_version = snapshot(memories)

    async def query(self, query: str, limit: int) -> tuple[UUID, ...]:
        from doxa.retrieval.lexical import lexical_rank

        if self.database is not None:
            from doxa.retrieval.persistent import PersistentSearch

            return PersistentSearch(self.database).rank(
                [(m.id, "", m.text) for m in self.memories], query, limit
            )
        return lexical_rank([(m.id, m.text) for m in self.memories], query, limit)


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
        cache_dir: Path | None = None,
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
        self.cache_dir = cache_dir.resolve() if cache_dir else None
        self._lease: Any = None

    async def rebuild(self, memories: tuple[Memory, ...]) -> None:
        if not self.authorized:
            raise PermissionError("Moss live session requires separate authorization")
        if self.session is not None and self.index_version == snapshot(memories):
            return  # Reuse only this principal-scoped, already-authorized identical snapshot.
        if self.client is not None:
            await self.close()
        if self.cache_dir:
            # OS-held lease is released after crashes; competing writers fail closed.
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._lease = (self.cache_dir / "session.lock").open("a+b")
            self._lease.seek(0)
            self._lease.write(b"0")
            self._lease.flush()
            self._lease.seek(0)
            try:
                import sys

                if sys.platform == "win32":
                    import msvcrt

                    msvcrt.locking(self._lease.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self._lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BaseException:
                self._lease.close()
                self._lease = None
                raise
        sdk = self.sdk_module or importlib.import_module("moss")
        factory = self.sdk_factory or sdk.MossClient
        self.client = factory(self.project_id, self._project_key)
        async with asyncio.timeout(self.timeout_seconds):
            self.session = await self.client.session(
                index_name=self.index_name,
                auto_load_on_init=False,
            )
            previous: dict[str, str] = {}
            marker = self.cache_dir / "snapshot.ready" if self.cache_dir else None
            if marker and marker.exists():
                # Installed SDK 1.21 supports local session snapshots. No cloud push,
                # automatic refresh, or legacy re-embedding is authorized here.
                await self.session.load_from_disk(str(self.cache_dir), rebuild_legacy=False)
                cached = await self.session.get_docs()
                previous = {str(d.id): d.text for d in cached}
                if len(previous) != len(cached):
                    raise ValueError("Duplicate cached Moss document IDs")
            current = {str(m.id): m.text for m in memories}
            removed = sorted(set(previous) - set(current))
            if removed:
                await self.session.delete_docs(removed)
            changed = [
                sdk.DocumentInfo(id=i, text=text)
                for i, text in current.items()
                if previous.get(i) != text
            ]
            if changed or self.cache_dir is None:
                await self.session.add_docs(changed)
            if self.cache_dir:
                await self.session.save_to_disk(str(self.cache_dir))
                assert marker is not None
                marker.write_text("moss-session-cache-v1", encoding="utf-8")
        self.index_version = snapshot(memories)

    async def query(self, query: str, limit: int) -> tuple[UUID, ...]:
        if self.session is None:
            raise RuntimeError("Moss index not built")
        sdk = self.sdk_module or importlib.import_module("moss")
        async with asyncio.timeout(self.timeout_seconds):
            result = await self.session.query(query, sdk.QueryOptions(top_k=limit))
        return tuple(UUID(doc.id) for doc in result.docs)

    async def close(self) -> None:
        try:
            if self.client is not None:
                async with asyncio.timeout(self.timeout_seconds):
                    await self.client.close()
        finally:
            self.client = None
            self.session = None
            self.index_version = None
            if self._lease:
                self._lease.close()
                self._lease = None
