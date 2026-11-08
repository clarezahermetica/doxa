"""Regression for the v21 live disposition/prose contract mismatch; no live calls."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from doxa.core.text_research import ReviewAssessment, ReviewDecision, ReviewResponse
from doxa.providers.cli_session import research_schema


def operation_schema(operation):
    return next(
        branch
        for branch in research_schema()["properties"]["research_action"]["anyOf"]
        if branch["properties"]["operation"]["const"] == operation
    )


@pytest.mark.parametrize(
    "operation,contract,field",
    [
        ("respond", ReviewResponse, "response"),
        ("assess", ReviewAssessment, "stance"),
        ("adjudicate", ReviewDecision, "outcome"),
    ],
)
def test_native_choice_fields_match_authoritative_controller(operation, contract, field):
    native = operation_schema(operation)["properties"][field]
    canonical = contract.model_json_schema()["properties"][field]
    assert native["enum"] == canonical["enum"]
    assert native["type"] == canonical["type"] == "string"


def response_body():
    return dict(
        operation="respond",
        challenge_id=uuid4(),
        author_id=uuid4(),
        idempotency_key="offline-captured-shape",
        reason="The original wording overlooked transition evidence.",
        revised_proposition="Aggregate decline does not imply zero individual corrections.",
    )


def test_captured_prose_in_disposition_is_not_silently_interpreted():
    # Reduced shape of the rejected real output; no private history is imported or rewritten.
    prose = (
        "I accept the narrowing. Whether intermediate reasoning errors "
        "were repaired remains uncertain."
    )
    allowed = operation_schema("respond")["properties"]["response"]["enum"]
    assert prose not in allowed
    with pytest.raises(ValidationError):
        ReviewResponse(**response_body(), response=prose)


def test_explanatory_prose_remains_valid_with_explicit_disposition():
    prose = (
        "I accept the narrowing. Whether intermediate reasoning errors "
        "were repaired remains uncertain."
    )
    body = response_body() | {"reason": prose}
    response = ReviewResponse(**body, response="qualify")
    assert response.reason == prose and response.response == "qualify"
    assert operation_schema("respond")["properties"]["reason"]["type"] == "string"
