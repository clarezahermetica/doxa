from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from doxa.core.models import (
    Annotation,
    Event,
    EventType,
    Memory,
    Provenance,
    Trajectory,
    Usage,
    Verification,
)


def scope():
    return dict(experiment_id=uuid4(), run_id=uuid4(), trajectory_id=uuid4())


def test_invalid_ancestry_and_unknown_fields():
    with pytest.raises(ValidationError):
        Trajectory(run_id=uuid4(), parent_id=uuid4())
    with pytest.raises(ValidationError):
        Usage(unknown_field="secret")
    assert Usage().input_tokens is None
    assert Usage().billed_usd is None


def test_provenance_cannot_turn_model_consensus_into_verification():
    with pytest.raises(ValidationError, match="independent validity"):
        Verification(
            **scope(),
            provenance=Provenance.LLM_EVALUATOR,
            subject_id=uuid4(),
            evaluator_id="test-model",
            evaluator_version="1",
            verdict="valid",
        )
    with pytest.raises(ValidationError):
        Annotation(
            **scope(),
            provenance=Provenance.MODEL_OUTPUT,
            reviewer_id="test",
            rubric_version="1",
            subject_id=uuid4(),
        )


def test_memory_validation_and_owner_are_required():
    args = dict(**scope(), provenance=Provenance.MODEL_OUTPUT, text="test", source_event_id=uuid4())
    with pytest.raises(ValidationError, match="owner"):
        Memory(**args)
    memory = Memory(**args, owner_agent_id=uuid4())
    assert memory.trust == "quarantined"
    with pytest.raises(ValidationError, match="validation"):
        Memory(**args, owner_agent_id=uuid4(), trust="approved")


def test_event_utc_and_schema_version():
    args = dict(**scope(), sequence=1, type=EventType.RUN_CREATED, idempotency_key="test")
    with pytest.raises(ValidationError, match="UTC"):
        Event(**args, timestamp=datetime(2026, 1, 1))
    with pytest.raises(ValidationError):
        Event(**args, schema_version=2)


def test_task_version_cannot_silently_drop_oracle_cases():
    from doxa.environments.cache_policy import CacheFixture

    with pytest.raises(ValidationError):
        CacheFixture(cases=())
