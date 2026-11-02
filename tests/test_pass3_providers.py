"""Mock-provider contract evidence only. No request reaches a real service."""

import asyncio
import json
from uuid import uuid4

import httpx
import pytest

from doxa.core.models import ModelAssignment
from doxa.core.profiles import ModelProfile
from doxa.providers.contracts import Capabilities, ModelMessage, ModelRequest
from doxa.providers.registry import validate_profile
from doxa.providers.runpod import RunPodProvider


def profile(runtime, *, responses=False):
    return ModelProfile(
        id="contract",
        provider=runtime,
        model_id="previously-unknown-model",
        request_protocol="responses" if responses else "default",
        enabled=True,
        base_url="https://mock.example/v1" if runtime == "openai_compatible" else None,
        credential_env="TEST_API_KEY",
        capabilities=Capabilities(tool_calling="native"),
    )


def request(p):
    return ModelRequest(
        call_id=uuid4(),
        run_id=uuid4(),
        trajectory_id=uuid4(),
        agent_id=uuid4(),
        assignment=ModelAssignment(
            provider=p.provider, model_id=p.model_id, instruction_version="1"
        ),
        messages=(
            ModelMessage(role="system", content="Instructions"),
            ModelMessage(role="user", content="Evidence"),
        ),
        max_output_tokens=128,
        timeout_seconds=1,
    )


def payload(runtime, responses=False, *, tool=False):
    usage = {"input_tokens": 11, "output_tokens": 7}
    if runtime == "claude":
        blocks = [
            {"type": "thinking", "thinking": "provider supplied summary"},
            {"type": "text", "text": "Answer"},
        ]
        if tool:
            blocks.append({"type": "tool_use", "id": "tool1", "name": "lookup", "input": {}})
        return dict(
            id="answer1",
            model="reported-model",
            content=blocks,
            stop_reason="tool_use" if tool else "end_turn",
            usage=usage,
        )
    if runtime == "gemini":
        parts = [{"text": "summary", "thought": True}, {"text": "Answer"}]
        if tool:
            parts.append({"functionCall": {"name": "lookup", "args": {}}})
        return dict(
            responseId="answer1",
            modelVersion="reported-model",
            candidates=[dict(content={"parts": parts}, finishReason="STOP")],
            usageMetadata={"promptTokenCount": 11, "candidatesTokenCount": 7},
        )
    if responses:
        blocks = [{"type": "message", "content": [{"type": "output_text", "text": "Answer"}]}]
        if tool:
            blocks.append(
                {"type": "function_call", "call_id": "tool1", "name": "lookup", "arguments": "{}"}
            )
        return dict(
            id="answer1", model="reported-model", output=blocks, status="completed", usage=usage
        )
    return dict(
        id="answer1",
        model="reported-model",
        choices=[
            dict(
                message={
                    "content": "Answer",
                    "tool_calls": [
                        {"id": "tool1", "function": {"name": "lookup", "arguments": "{}"}}
                    ]
                    if tool
                    else [],
                },
                finish_reason="stop",
            )
        ],
        usage={"prompt_tokens": 11, "completion_tokens": 7},
    )


@pytest.mark.parametrize(
    "runtime,responses",
    [
        ("openai", False),
        ("openai", True),
        ("claude", False),
        ("gemini", False),
        ("openai_compatible", False),
    ],
)
@pytest.mark.parametrize("tool", [False, True])
def test_native_wire_preserves_blocks_and_usage(runtime, responses, tool):
    p = profile(runtime, responses=responses)
    command = request(p)
    if tool:
        command = command.model_copy(
            update={
                "tools": ({"name": "lookup", "parameters": {"type": "object", "properties": {}}},)
            }
        )
    env = {"TEST_API_KEY": "mock-secret-value", f"DOXA_{runtime.upper()}_ENABLED": "true"}

    def handler(req):
        body = json.loads(req.content)
        assert bool(body.get("tools")) == tool
        assert "mock-secret-value" not in req.content.decode()
        assert body.get("model", p.model_id) == p.model_id
        if runtime == "gemini":
            assert req.url.path.endswith("/models/previously-unknown-model:generateContent")
            assert body["systemInstruction"]["parts"][0]["text"] == "Instructions"
            assert req.headers["x-goog-api-key"] == env["TEST_API_KEY"]
        elif runtime == "claude":
            assert req.url.path == "/v1/messages" and body["system"] == "Instructions"
            assert req.headers["anthropic-version"] == "2023-06-01"
        elif responses:
            assert req.url.path == "/v1/responses" and not body["store"]
            assert body["max_output_tokens"] == 128 and "temperature" not in body
        return httpx.Response(
            200, json=payload(runtime, responses, tool=tool), headers={"x-request-id": "request1"}
        )

    result = asyncio.run(RunPodProvider(p, env, httpx.MockTransport(handler)).generate(command))
    assert result.error is None and result.text == "Answer"
    assert result.response_id == "answer1" and result.reported_model_id == "reported-model"
    assert result.usage.input_tokens == 11 and result.usage.output_tokens == 7
    assert result.finish_reason and result.blocks and result.raw_response
    assert bool(result.tool_requests) == tool
    assert result.completion_state == ("tool_request" if tool else "completed")


@pytest.mark.parametrize("runtime", ["openai", "claude", "gemini", "openai_compatible"])
@pytest.mark.parametrize(
    "status,category",
    [(401, "authentication"), (429, "quota"), (500, "transport"), (400, "invalid_request")],
)
def test_native_errors_remain_sanitized_and_uncertain(runtime, status, category):
    p = profile(runtime)
    env = {"TEST_API_KEY": "mock-secret-value", f"DOXA_{runtime.upper()}_ENABLED": "true"}
    result = asyncio.run(
        RunPodProvider(
            p,
            env,
            httpx.MockTransport(
                lambda req: httpx.Response(status, json={"error": "mock-secret-value"})
            ),
        ).generate(request(p))
    )
    assert result.error.category == category and result.error.billing_uncertain
    assert "mock-secret-value" not in result.model_dump_json()


def test_reasoning_and_unsupported_parameter_validation():
    p = profile("claude").model_copy(
        update={"reasoning": {"type": "enabled", "budget_tokens": 1024}}
    )
    with pytest.raises(ValueError, match="capability"):
        validate_profile(p, {})
    p = p.model_copy(
        update={
            "capabilities": Capabilities(sampling_parameters=("reasoning",)),
            "max_output_tokens": 2048,
            "omit_temperature": True,
        }
    )
    validate_profile(p, {})
    with pytest.raises(ValueError, match="Unsupported generation"):
        validate_profile(p.model_copy(update={"generation_parameters": {"unsafe": True}}), {})


@pytest.mark.parametrize("runtime", ["openai", "claude", "gemini", "openai_compatible"])
def test_usage_missing_is_unknown_and_partial_is_not_complete(runtime):
    p = profile(runtime, responses=runtime == "openai")
    body = payload(runtime, runtime == "openai")
    body.pop("usage", None)
    body.pop("usageMetadata", None)
    if runtime == "claude":
        body["stop_reason"] = "max_tokens"
    elif runtime == "gemini":
        body["candidates"][0]["finishReason"] = "MAX_TOKENS"
    elif runtime == "openai":
        body["status"] = "incomplete"
    else:
        body["choices"][0]["finish_reason"] = "length"
    env = {"TEST_API_KEY": "mock-secret-value", f"DOXA_{runtime.upper()}_ENABLED": "true"}
    result = asyncio.run(
        RunPodProvider(
            p, env, httpx.MockTransport(lambda req: httpx.Response(200, json=body))
        ).generate(request(p))
    )
    assert result.error is None and result.completion_state == "incomplete"
    assert result.usage.input_tokens is None and result.usage.billed_usd is None


@pytest.mark.parametrize("runtime", ["openai", "claude", "gemini", "openai_compatible"])
def test_missing_credentials_and_malformed_native_responses(runtime):
    p = profile(runtime)
    reached = []
    transport = httpx.MockTransport(lambda req: reached.append(req) or httpx.Response(200, json={}))
    env = {f"DOXA_{runtime.upper()}_ENABLED": "true"}
    result = asyncio.run(RunPodProvider(p, env, transport).generate(request(p)))
    assert result.error.category == "configuration" and not reached
    env["TEST_API_KEY"] = "mock-secret-value"
    result = asyncio.run(RunPodProvider(p, env, transport).generate(request(p)))
    assert result.error.category == "invalid_response" and result.error.billing_uncertain


@pytest.mark.parametrize("runtime", ["openai", "claude", "gemini", "openai_compatible"])
def test_native_cancel_stops_local_wait_without_asserting_remote_termination(runtime):
    async def scenario():
        p = profile(runtime)
        started = asyncio.Event()

        async def handler(req):
            started.set()
            await asyncio.Event().wait()

        env = {"TEST_API_KEY": "mock-secret-value", f"DOXA_{runtime.upper()}_ENABLED": "true"}
        provider = RunPodProvider(p, env, httpx.MockTransport(handler))
        command = request(p)
        pending = asyncio.create_task(provider.generate(command))
        await started.wait()
        assert await provider.cancel(command.call_id)
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert not provider.tasks

    asyncio.run(scenario())
