import time
from uuid import UUID

from doxa.core.models import Memory, Provenance, RetrievalAudit
from doxa.retrieval.backends import LocalRetrieval, RetrievalBackend
from doxa.storage.ledger import Ledger


def latest_memories(ledger: Ledger, run_id: UUID) -> tuple[Memory, ...]:
    memories = [m for m in ledger.records("memory") if isinstance(m, Memory) and m.run_id == run_id]
    superseded = {m.revises_id for m in memories if m.revises_id}
    return tuple(m for m in memories if m.id not in superseded)


def eligible(
    ledger: Ledger,
    run_id: UUID,
    agent_id: UUID,
    conditions: tuple[str, ...] = (),
    branch_id: UUID | None = None,
) -> tuple[Memory, ...]:
    from doxa.core.models import Verification

    branch_id = branch_id or ledger.events(run_id)[-1].trajectory_id

    def validated(memory: Memory) -> bool:
        if not memory.validation_ids:
            return False
        for identity in memory.validation_ids:
            result = ledger.get(identity)
            if (
                not isinstance(result, Verification)
                or result.verdict != "valid"
                or (
                    result.provenance
                    not in {Provenance.DETERMINISTIC_VERIFIER, Provenance.TASK_ANSWER_KEY}
                )
            ):
                return False
        return True

    return tuple(
        m
        for m in latest_memories(ledger, run_id)
        if m.trust == "approved"
        and (m.scope == "shared" or m.owner_agent_id == agent_id)
        and set(m.eligibility).issubset(conditions)
        and (not m.branch_ids or branch_id in m.branch_ids)
        and validated(m)
    )


async def retrieve(
    ledger: Ledger,
    run_id: UUID,
    agent_id: UUID,
    query: str,
    backend: RetrievalBackend | None = None,
    conditions: tuple[str, ...] = (),
    limit: int = 10,
    rebuild: bool = True,
) -> tuple[tuple[Memory, ...], RetrievalAudit]:
    started = time.monotonic()
    events = ledger.events(run_id)
    if not events:
        raise KeyError(str(run_id))
    baseline = LocalRetrieval()
    chosen = backend or baseline
    fallback: str | None = None
    authorized = eligible(ledger, run_id, agent_id, conditions)
    try:
        if rebuild:
            await chosen.rebuild(authorized)
        candidates = await chosen.query(query, limit)
    except Exception:
        # External failure cannot broaden access or silently present stale index text.
        fallback = "backend_unavailable"
        chosen = baseline
        await chosen.rebuild(eligible(ledger, run_id, agent_id, conditions))
        candidates = await chosen.query(query, limit)
    # Re-read SQLite AFTER the external await. Ignore index text and authority metadata.
    current = {m.id: m for m in eligible(ledger, run_id, agent_id, conditions)}
    accepted = tuple(dict.fromkeys(i for i in candidates if i in current))
    memories = tuple(current[i] for i in accepted)
    audit = RetrievalAudit(
        experiment_id=events[0].experiment_id,
        run_id=run_id,
        trajectory_id=events[-1].trajectory_id,
        provenance=Provenance.SYSTEM_INFERENCE,
        agent_id=agent_id,
        query=query,
        backend=chosen.name,
        index_version=chosen.index_version,
        candidate_ids=candidates,
        eligible_ids=accepted,
        rejected_ids=tuple(i for i in candidates if i not in current),
        latency_seconds=time.monotonic() - started,
        cost_usd=None,
        fallback_reason=fallback,
        conditions=conditions,
    )
    return memories, audit
