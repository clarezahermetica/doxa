"""Offline bounded workflow + two-agent memory fixture. No credentials or paid APIs.

Run from repository root: python scripts/demo_backend.py --data-dir .doxa/demo
Every answer below is supplied synthetic input, not inferred by a real model.
"""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from doxa.core.config import Settings
from doxa.core.controller import ConfigureRun, Controller
from doxa.core.execution import ExecuteTask
from doxa.core.memory_commands import ProposeMemory, TransitionMemory
from doxa.core.models import Evaluation, Experiment, ProtocolMode
from doxa.core.profiles import CouncilConfig
from doxa.environments.cache_policy import Candidate


async def main(data_dir: Path) -> None:
    ctrl = Controller(Settings(data_dir=data_dir))
    ctrl.initialize()
    config = CouncilConfig.model_validate_json(Path("examples/council.json").read_text())
    ctrl.save_configuration(config)
    run_ids: dict[str, str] = {}
    for mode in ProtocolMode:
        run = ctrl.configure_run(
            ConfigureRun(
                idempotency_key="offline-demo-v1:" + mode.value,
                execution_kind="synthetic",
                mode=mode,
                agent_ids=tuple(a.id for a in config.agents),
                experiment=Experiment(
                    id=uuid5(NAMESPACE_URL, "doxa:demo:" + mode.value),
                    name="Synthetic bounded cache-policy " + mode.value,
                    task_id="cache-policy",
                    task_version="1",
                    environment_version="1",
                    policy_version="1",
                    evaluator_version="1",
                ),
            )
        )
        result = await ctrl.execute_task(
            run.id,
            ExecuteTask(
                synthetic_answers={
                    "executor": Candidate(policy="stale_on_update"),
                    "skeptic": Candidate(policy="invalidate_all"),
                    "researcher": Candidate(policy="invalidate_all"),
                    "defender": Candidate(policy="invalidate_all"),
                }
            ),
        )
        score = next(
            r.metrics["task_success"]
            for e in result.events
            for r in e.payload
            if isinstance(r, Evaluation)
        )
        run_ids[mode.value] = str(run.id)
        print(
            json.dumps(
                {
                    "mode": mode.value,
                    "run_id": str(run.id),
                    "status": result.run.status,
                    "task_success": score,
                    "input_kind": "synthetic",
                }
            )
        )
    run_id = UUID(run_ids[ProtocolMode.SOLO_DIRECT.value])
    a, b = config.agents[:2]

    def approve(key: str, owner: UUID | None, shared: bool = False):
        proposal = ctrl.propose_memory(
            run_id,
            ProposeMemory(
                text="Invalidate cache entries after update and delete.",
                scope="shared" if shared else "private",
                owner_agent_id=owner,
                idempotency_key=key,
            ),
        )
        checked = ctrl.validate_memory(run_id, proposal.id)
        return ctrl.transition_memory(
            run_id,
            proposal.id,
            TransitionMemory(
                trust="approved", validation_ids=(checked.id,), idempotency_key=key + ":promote"
            ),
        )

    private_a = approve("private-a", a.id)
    private_b = approve("private-b", b.id)
    shared = approve("shared", None, True)
    false = ctrl.propose_memory(
        run_id,
        ProposeMemory(
            text="Cache entries never require invalidation.",
            scope="shared",
            idempotency_key="false",
        ),
    )
    revoked = approve("revoked", None, True)
    ctrl.transition_memory(
        run_id, revoked.id, TransitionMemory(trust="revoked", idempotency_key="revoke")
    )
    old = approve("superseded", None, True)
    correction = ctrl.propose_memory(
        run_id,
        ProposeMemory(
            text="Repeated reads without writes return the same cached value.",
            scope="shared",
            revises_id=old.id,
            idempotency_key="correction",
        ),
    )
    checked = ctrl.validate_memory(run_id, correction.id)
    corrected = ctrl.transition_memory(
        run_id,
        correction.id,
        TransitionMemory(
            trust="approved", validation_ids=(checked.id,), idempotency_key="correction:promote"
        ),
    )
    result_a = await ctrl.retrieve_memory(run_id, a.id, "cache reads")
    result_b = await ctrl.retrieve_memory(run_id, b.id, "cache reads")
    assert {m.id for m in result_a} == {private_a.id, shared.id, corrected.id}
    assert {m.id for m in result_b} == {private_b.id, shared.id, corrected.id}
    excluded = {false.id, revoked.id, old.id}
    assert not excluded.intersection(m.id for m in (*result_a, *result_b))
    (data_dir / "demo-summary.json").write_text(
        json.dumps(
            {
                "execution_kind": "synthetic",
                "runs": run_ids,
                "memory_isolation_checks": "passed",
                "agent_a_eligible": [str(m.id) for m in result_a],
                "agent_b_eligible": [str(m.id) for m in result_b],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Two-agent memory fixture passed; no remote services were called.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path(".doxa/demo"))
    asyncio.run(main(parser.parse_args().data_dir))
