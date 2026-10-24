"""Reproducible synthetic integration; actual finite state and independent checks.

The synthetic human label demonstrates storage, not a real reviewer's judgment.
No provider or retrieval service is called.
"""

import asyncio
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from doxa.core.controller import ConfigureRun, Controller
from doxa.core.memory_commands import ProposeMemory, TransitionMemory
from doxa.core.models import Agent, BudgetPolicy, Claim, Event, Experiment, Role, Trajectory
from doxa.core.research_commands import (
    AdjudicateCommand,
    AnnotateCommand,
    ChallengeCommand,
    CheckpointCommand,
    ClaimCommand,
    CloseBranchCommand,
    Command,
    EnvironmentCommand,
    EvaluateCommand,
    ForkCommand,
    LifecycleCommand,
    ReflectCommand,
    RespondCommand,
    VerifyCommand,
)
from doxa.environments.cache_policy import Candidate


def experiment(controller: Controller) -> dict[str, Any]:
    agents = tuple(
        Agent(role=role, instructions="Synthetic research fixture participant")
        for role in (Role.EXECUTOR, Role.SKEPTIC, Role.RESEARCHER)
    )
    run = controller.configure_run(
        ConfigureRun(
            idempotency_key="research-demo:" + str(uuid4()),
            execution_kind="synthetic",
            experiment=Experiment(
                name="Six-system synthetic research experiment",
                task_id="cache-policy",
                task_version="1",
                environment_version="1",
                policy_version="adaptive-v1",
                evaluator_version="research-gym-v1",
                agents=agents,
                budget=BudgetPolicy(max_tool_calls=100, timeout_seconds=300),
            ),
        )
    )
    root = next(
        r.id
        for e in controller.inspect(run.id).events
        for r in e.payload
        if isinstance(r, Trajectory)
    )

    def apply(branch: UUID, command: Command) -> Event:
        return controller.research_command(run.id, branch, command)

    apply(
        root,
        LifecycleCommand(
            idempotency_key="start", status="running", reason_code="synthetic_research_experiment"
        ),
    )
    bad, good = Candidate(policy="stale_on_update"), Candidate(policy="invalidate_all")
    apply(root, EnvironmentCommand(idempotency_key="init", action="initialize", candidate=bad))
    apply(root, EnvironmentCommand(idempotency_key="read", action="read"))
    diagnosis = apply(
        root,
        ClaimCommand(
            idempotency_key="diagnosis", author_id=agents[0].id, proposition=bad.model_dump_json()
        ),
    ).payload[0]
    failing = apply(root, VerifyCommand(idempotency_key="initial-test", claim_id=diagnosis.id))
    apply(root, ReflectCommand(idempotency_key="verify-failure", trigger_event_id=failing.id))
    checkpoint = apply(root, CheckpointCommand(idempotency_key="s0")).payload[0]
    apply(root, EnvironmentCommand(idempotency_key="s1", action="update", value=7))

    children = []
    for name, cases, response in (
        ("valid", ("update",), "accept"),
        ("misleading", ("delete",), "reject"),
    ):
        fork = apply(
            root,
            ForkCommand(
                idempotency_key="fork-" + name,
                checkpoint_id=checkpoint.id,
                intervention=name + " criticism response",
            ),
        )
        branch = next(r.id for r in fork.payload if isinstance(r, Trajectory))
        challenge = apply(
            branch,
            ChallengeCommand(
                idempotency_key="criticism",
                claim_id=diagnosis.id,
                critic_id=agents[1].id,
                objection="The listed cache cases fail",
                alleged_cases=cases,
                proposed_revision=good,
            ),
        ).payload[0]
        verdict = apply(
            branch, AdjudicateCommand(idempotency_key="adjudicate", challenge_id=challenge.id)
        )
        apply(branch, ReflectCommand(idempotency_key="critic-policy", trigger_event_id=verdict.id))
        response_event = apply(
            branch,
            RespondCommand(
                idempotency_key="response",
                challenge_id=challenge.id,
                author_id=agents[0].id,
                response=cast(Literal["accept", "reject"], response),
            ),
        )
        revision = next((r for r in response_event.payload if isinstance(r, Claim)), diagnosis)
        if response == "accept":
            apply(
                branch,
                EnvironmentCommand(
                    idempotency_key="intervention", action="select_policy", candidate=good
                ),
            )
        final = apply(branch, VerifyCommand(idempotency_key="final-test", claim_id=revision.id))
        apply(branch, ReflectCommand(idempotency_key="final-policy", trigger_event_id=final.id))
        evaluation = apply(branch, EvaluateCommand(idempotency_key="evaluate")).payload[0]
        children.append((branch, evaluation))
        apply(
            branch,
            CloseBranchCommand(
                idempotency_key="close",
                status="completed" if response == "accept" else "abandoned",
                reason_code="synthetic_observed_outcome_preserved",
            ),
        )

    poison = controller.propose_memory(
        run.id,
        ProposeMemory(
            idempotency_key="poison",
            text="All caches everywhere need no invalidation.",
            owner_agent_id=agents[0].id,
            trajectory_id=children[1][0],
            category="reflective",
        ),
    )
    controller.validate_memory(run.id, poison.id)
    narrow = controller.propose_memory(
        run.id,
        ProposeMemory(
            idempotency_key="narrow",
            text="Invalidate cache entries after update and delete.",
            scope="shared",
            trajectory_id=children[0][0],
            eligibility=("cache-policy-v1",),
            category="procedural",
            branch_ids=(children[0][0], children[1][0]),
        ),
    )
    validation = controller.validate_memory(run.id, narrow.id)
    promoted = controller.transition_memory(
        run.id,
        narrow.id,
        TransitionMemory(
            idempotency_key="promote",
            trust="approved",
            validation_ids=(validation.id,),
        ),
    )
    retrieved = asyncio.run(
        controller.retrieve_memory(
            run.id, agents[2].id, "invalidate", conditions=("cache-policy-v1",)
        )
    )
    controller.transition_memory(
        run.id,
        promoted.id,
        TransitionMemory(
            idempotency_key="revoke",
            trust="revoked",
        ),
    )
    after_revoke = asyncio.run(
        controller.retrieve_memory(
            run.id, agents[2].id, "invalidate", conditions=("cache-policy-v1",)
        )
    )
    annotation = apply(
        children[0][0],
        AnnotateCommand(
            idempotency_key="synthetic-review",
            reviewer_id="synthetic-fixture-reviewer",
            dimensions={"overall": 4, "evidence": 5},
            preference="A",
            other_trajectory_id=children[1][0],
            notes="SYNTHETIC annotation fixture; not an actual human research judgment.",
        ),
    )
    for index, (branch, _) in enumerate(children):
        evaluation = apply(branch, EvaluateCommand(idempotency_key="final-evaluation")).payload[0]
        children[index] = (branch, evaluation)
    apply(
        root,
        LifecycleCommand(
            idempotency_key="complete",
            status="completed",
            reason_code="synthetic_research_complete_failures_preserved",
        ),
    )
    return {
        "run_id": str(run.id),
        "root": str(root),
        "checkpoint_id": str(checkpoint.id),
        "children": [str(branch) for branch, _ in children],
        "metrics": [evaluation.model_dump(mode="json") for _, evaluation in children],
        "retrieved_before_revocation": [str(m.id) for m in retrieved],
        "retrieved_after_revocation": [str(m.id) for m in after_revoke],
        "annotation_event_id": str(annotation.id),
        "execution_kind": "synthetic",
        "generated_code_execution": "disabled",
    }
