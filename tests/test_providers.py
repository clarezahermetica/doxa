from uuid import uuid4

import pytest
from pydantic import ValidationError

from doxa.core.models import ModelAssignment
from doxa.providers.contracts import Capabilities, ModelResponse, ProviderError


def test_provider_capabilities_default_to_unknown_not_assumed_support():
    capabilities = Capabilities()
    assert capabilities.structured_output == "unknown"
    assert capabilities.context_limit is None
    assert capabilities.streaming is False


def test_response_has_one_result_channel_and_unknown_usage():
    args = dict(
        call_id=uuid4(),
        execution_kind="synthetic",
        assignment=ModelAssignment(provider="test", model_id="synthetic", instruction_version="1"),
    )
    with pytest.raises(ValidationError):
        ModelResponse(**args)
    error = ProviderError(category="timeout", retryable=True, safe_message="Timed out")
    with pytest.raises(ValidationError):
        ModelResponse(**args, text="test", error=error)
    response = ModelResponse(**args, text="synthetic test response")
    assert response.usage.billed_usd is None
    assert response.usage.input_tokens is None
