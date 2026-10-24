"""Concrete IndependentVerifier for finite policies, never generated source execution."""

import json
from uuid import UUID, uuid4

from doxa.core.models import ArtifactRef, Evidence, Provenance, Verification
from doxa.environments.cache_policy import CacheFixture, Candidate, verify
from doxa.environments.contracts import TaskSpec
from doxa.storage.artifacts import ArtifactStore


class CacheIndependentVerifier:
    def __init__(
        self,
        store: ArtifactStore,
        experiment_id: UUID,
        run_id: UUID,
        trajectory_id: UUID,
        subject_id: UUID,
    ):
        self.store = store
        self.experiment_id = experiment_id
        self.run_id = run_id
        self.trajectory_id = trajectory_id
        self.subject_id = subject_id
        self.evidence: Evidence | None = None

    @staticmethod
    def check(candidate: Candidate) -> dict[str, bool]:
        return verify(CacheFixture(), candidate)

    async def verify(self, task: TaskSpec, artifact: ArtifactRef) -> Verification:
        if (task.id, task.version, task.environment) != ("cache-policy", "1", "1"):
            raise ValueError("Unsupported independent verifier task")
        fixture = CacheFixture.model_validate_json(self.store.get(task.fixture))
        candidate = Candidate.model_validate_json(self.store.get(artifact))
        results = verify(fixture, candidate)
        self.evidence = Evidence(
            experiment_id=self.experiment_id,
            run_id=self.run_id,
            trajectory_id=self.trajectory_id,
            provenance=Provenance.DETERMINISTIC_VERIFIER,
            description=json.dumps(results),
            source="cache-independent-verifier-v2",
            artifacts=(self.store.put(json.dumps(results).encode(), "application/json"),),
        )
        # Caller persists evidence and verdict atomically. This port does not write history.
        return Verification(
            id=uuid4(),
            experiment_id=self.experiment_id,
            run_id=self.run_id,
            trajectory_id=self.trajectory_id,
            subject_id=self.subject_id,
            provenance=Provenance.DETERMINISTIC_VERIFIER,
            evaluator_id="cache-oracle",
            evaluator_version="2",
            verdict="valid" if all(results.values()) else "invalid",
            evidence_ids=(self.evidence.id,),
        )
