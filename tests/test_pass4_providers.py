"""Official partial-response states must survive normalization, even with tool blocks."""

import pytest
from test_pass3_providers import payload, profile

from doxa.providers.wire import normalize


@pytest.mark.parametrize(
    "runtime,responses,tool,reason,state",
    [
        ("claude", False, False, "model_context_window_exceeded", "incomplete"),
        ("gemini", False, False, "CONTINUATION", "incomplete"),
        ("claude", False, True, "max_tokens", "incomplete"),
        ("openai", True, True, "incomplete", "incomplete"),
        ("openai", False, True, "content_filter", "refused"),
    ],
)
def test_partial_or_refused_output_is_not_reclassified_as_a_usable_tool_request(
    runtime, responses, tool, reason, state
):
    p = profile(runtime, responses=responses)
    body = payload(runtime, responses, tool=tool)
    if runtime == "claude":
        body["stop_reason"] = reason
    elif runtime == "gemini":
        body["candidates"][0]["finishReason"] = reason
    elif responses:
        body["status"] = reason
    else:
        body["choices"][0]["finish_reason"] = reason
    result = normalize(p, body)
    assert result["completion_state"] == state
    assert result["finish_reason"] == reason
    assert result["raw_response"] == body
    assert result["usage"] == {"input_tokens": 11, "output_tokens": 7}
