import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_runtime_stage import setup_run

from doxa.core.memory_commands import ProposeMemory, TransitionMemory
from doxa.core.models import Memory, RetrievalAudit
from doxa.retrieval.backends import MossRetrieval
from doxa.systems.memory import eligible


def promoted(controller, run, owner, key, scope="private", text=None):
    memory = controller.propose_memory(
        run.id,
        ProposeMemory(
            text=text or "Invalidate cache entries after update and delete.",
            scope=scope,
            owner_agent_id=owner,
            idempotency_key=key,
        ),
    )
    validation = controller.validate_memory(run.id, memory.id)
    return controller.transition_memory(
        run.id,
        memory.id,
        TransitionMemory(
            trust="approved", validation_ids=(validation.id,), idempotency_key=key + ":promote"
        ),
    )


def two_agent_fixture(controller):
    run, agents = setup_run(controller)
    a, b = agents[:2]
    private_a = promoted(controller, run, a.id, "a")
    private_b = promoted(controller, run, b.id, "b")
    shared = promoted(controller, run, None, "shared", "shared")
    false = controller.propose_memory(
        run.id,
        ProposeMemory(
            text="Cache entries never need invalidation.", scope="shared", idempotency_key="false"
        ),
    )
    revoked = promoted(controller, run, None, "revoked", "shared")
    controller.transition_memory(
        run.id, revoked.id, TransitionMemory(trust="revoked", idempotency_key="revoke")
    )
    old = promoted(controller, run, None, "old", "shared")
    correction = controller.propose_memory(
        run.id,
        ProposeMemory(
            text="Repeated reads without writes return the same cached value.",
            scope="shared",
            revises_id=old.id,
            idempotency_key="corrected",
        ),
    )
    check = controller.validate_memory(run.id, correction.id)
    corrected = controller.transition_memory(
        run.id,
        correction.id,
        TransitionMemory(
            trust="approved", validation_ids=(check.id,), idempotency_key="corrected:promote"
        ),
    )
    return run, a, b, (private_a, private_b, shared, false, revoked, old, corrected)


def test_local_baseline_isolation_revocation_supersession_reload(controller):
    run, a, b, memories = two_agent_fixture(controller)
    controller.initialize()
    result_a = asyncio.run(controller.retrieve_memory(run.id, a.id, "cache reads"))
    result_b = asyncio.run(controller.retrieve_memory(run.id, b.id, "cache reads"))
    assert {m.id for m in result_a} == {memories[i].id for i in (0, 2, 6)}
    assert {m.id for m in result_b} == {memories[i].id for i in (1, 2, 6)}
    assert {
        m.id for m in controller.participant_records(run.id, a.id) if isinstance(m, Memory)
    } == ({m.id for m in result_a})
    with pytest.raises(PermissionError):
        asyncio.run(controller.retrieve_memory(run.id, uuid4(), "cache"))
    verification = controller.validate_memory(run.id, memories[3].id)
    assert verification.verdict == "unverified"
    with pytest.raises(ValueError):
        controller.transition_memory(
            run.id,
            memories[3].id,
            TransitionMemory(
                trust="approved", validation_ids=(verification.id,), idempotency_key="bad-promotion"
            ),
        )


def test_hostile_stale_moss_results_are_filtered_against_sqlite(controller):
    run, a, b, memories = two_agent_fixture(controller)

    class Hostile:
        name = "mock_moss_stale"
        index_version = "stale-test-snapshot"

        async def rebuild(self, documents):
            assert {m.id for m in documents} == {memories[i].id for i in (0, 2, 6)}

        async def query(self, query, limit):
            # Index returns a peer's private record, revoked, quarantined and old IDs.
            return tuple(m.id for m in memories) + (uuid4(),)

    result = asyncio.run(controller.retrieve_memory(run.id, a.id, "cache", Hostile()))
    assert {m.id for m in result} == {memories[i].id for i in (0, 2, 6)}
    audit = controller.inspect(run.id).events[-1].payload[0]
    assert isinstance(audit, RetrievalAudit)
    assert memories[1].id in audit.rejected_ids
    assert audit.cost_usd is None


def test_revocation_during_remote_await_wins(controller):
    run, a, b, memories = two_agent_fixture(controller)

    class RevokeDuringQuery:
        name = "mock_moss"
        index_version = "test"

        async def rebuild(self, documents):
            pass

        async def query(self, query, limit):
            controller.transition_memory(
                run.id,
                memories[0].id,
                TransitionMemory(trust="revoked", idempotency_key="revoke-in-flight"),
            )
            return (memories[0].id,)

    result = asyncio.run(controller.retrieve_memory(run.id, a.id, "cache", RevokeDuringQuery()))
    assert result == ()


def test_unavailable_backend_falls_back_locally(controller):
    run, a, b, _ = two_agent_fixture(controller)

    class Unavailable:
        name = "mock_moss"
        index_version = None

        async def rebuild(self, documents):
            raise OSError("synthetic transport failure")

        async def query(self, query, limit):
            raise AssertionError

    result = asyncio.run(controller.retrieve_memory(run.id, a.id, "cache", Unavailable()))
    assert {m.id for m in result} == {
        m.id for m in eligible(controller.ledger, run.id, a.id) if "cache" in m.text.lower().split()
    }
    assert controller.inspect(run.id).events[-1].payload[0].fallback_reason == "backend_unavailable"


def test_official_moss_adapter_api_shape_mocked_without_sdk_or_network():
    calls = []

    class Session:
        async def add_docs(self, documents):
            calls.append(("add", documents))

        async def query(self, text, options):
            return SimpleNamespace(docs=[SimpleNamespace(id=str(uuid4()))])

    class Client:
        def __init__(self, *args):
            calls.append(("constructed", True))

        async def session(self, **kwargs):
            assert kwargs["auto_load_on_init"] is False
            return Session()

        async def close(self):
            calls.append(("close", True))

    sdk = SimpleNamespace(
        MossClient=Client,
        DocumentInfo=lambda **kwargs: kwargs,
        QueryOptions=lambda **kwargs: kwargs,
    )
    backend = MossRetrieval("synthetic-project", "synthetic-key", "test", sdk_module=sdk)
    with pytest.raises(PermissionError):
        asyncio.run(backend.rebuild(()))
    assert calls == []
    backend.authorized = True

    async def scenario():
        await backend.rebuild(())
        await backend.rebuild(())
        assert sum(kind == "constructed" for kind, _ in calls) == 1
        assert len(await backend.query("cache", 3)) == 1
        await backend.close()
        assert backend.session is None
        await backend.rebuild(())
        assert sum(kind == "constructed" for kind, _ in calls) == 2
        await backend.close()

    asyncio.run(scenario())


def test_moss_disk_sessions_incrementally_add_and_remove_without_cloud_push(controller):
    import json
    from pathlib import Path

    run, agent, _, memories = two_agent_fixture(controller)
    calls = []

    class Session:
        def __init__(self):
            self.docs = {}

        async def add_docs(self, docs):
            calls.append(("add", tuple(d["id"] for d in docs)))
            self.docs.update({d["id"]: d["text"] for d in docs})

        async def delete_docs(self, ids):
            calls.append(("delete", tuple(ids)))
            for identity in ids:
                self.docs.pop(identity)

        async def get_docs(self):
            return [SimpleNamespace(id=i, text=t) for i, t in self.docs.items()]

        async def save_to_disk(self, directory):
            (Path(directory) / "fixture.json").write_text(json.dumps(self.docs))

        async def load_from_disk(self, directory, *, rebuild_legacy):
            assert rebuild_legacy is False
            calls.append(("load", ()))
            self.docs = json.loads((Path(directory) / "fixture.json").read_text())

    class Client:
        def __init__(self, *args):
            pass

        async def session(self, **kwargs):
            assert kwargs == {"index_name": "scoped", "auto_load_on_init": False}
            return Session()

        async def close(self):
            pass

    sdk = SimpleNamespace(MossClient=Client, DocumentInfo=lambda **kw: kw)
    directory = controller.settings.data_dir / "scoped-cache"

    def backend():
        return MossRetrieval(
            "fixture-project",
            "fixture-key",
            "scoped",
            authorized=True,
            sdk_module=sdk,
            cache_dir=directory,
        )

    async def scenario():
        initial = backend()
        await initial.rebuild((memories[0], memories[2]))
        # Another same-principal session cannot race the current cache writer.
        competing = backend()
        with pytest.raises(OSError):
            await competing.rebuild((memories[0],))
        await competing.close()
        await initial.close()
        resumed = backend()
        await resumed.rebuild((memories[2], memories[6]))
        assert set(resumed.session.docs) == {str(memories[2].id), str(memories[6].id)}
        await resumed.close()
        unchanged = backend()
        await unchanged.rebuild((memories[2], memories[6]))
        await unchanged.close()

    asyncio.run(scenario())
    assert ("delete", (str(memories[0].id),)) in calls
    assert ("add", (str(memories[6].id),)) in calls
    assert sum(action == "add" for action, _ in calls) == 2
    assert sum(action == "load" for action, _ in calls) == 2
