"""Bounded text protocols. Provider blocks are observations, never executable authority."""

import json
from typing import Any
from urllib.parse import quote

from doxa.core.profiles import ModelProfile
from doxa.providers.contracts import ModelRequest


def validate_parameters(profile: ModelProfile) -> None:
    runtime = profile.runtime
    if profile.request_protocol == "responses" and runtime != "openai":
        raise ValueError("Responses requires the native OpenAI adapter")
    allowed = {"top_p", "stop"} if runtime != "gemini" else {"topP", "topK", "stopSequences"}
    parameters = profile.generation_parameters
    if not set(parameters).issubset(allowed):
        raise ValueError("Unsupported generation parameter for this transport")
    if not set(parameters).issubset(profile.capabilities.sampling_parameters):
        raise ValueError("Generation parameters require explicitly declared model capabilities")
    for name, value in parameters.items():
        if name in {"top_p", "topP"} and (
            type(value) not in {int, float} or not 0 < value <= 1  # type: ignore[operator]
        ):
            raise ValueError("top-p must be a number in (0, 1]")
        if name == "topK" and (type(value) is not int or not 1 <= value <= 1000):
            raise ValueError("topK must be an integer in [1, 1000]")
        if name in {"stop", "stopSequences"} and (
            not isinstance(value, list)
            or not 1 <= len(value) <= 4
            or any(not isinstance(v, str) or not 1 <= len(v) <= 200 for v in value)
        ):
            raise ValueError("Stop sequences require one to four bounded strings")
    reasoning = profile.reasoning
    if reasoning and "reasoning" not in profile.capabilities.sampling_parameters:
        raise ValueError("Reasoning settings require an explicit model capability declaration")
    if runtime == "openai" and profile.request_protocol == "responses":
        if not set(reasoning).issubset({"effort", "summary", "mode", "context"}) or any(
            not isinstance(v, str) or len(v) > 40 for v in reasoning.values()
        ):
            raise ValueError("Unsupported OpenAI reasoning settings")
    elif runtime == "claude":
        if reasoning and (
            reasoning.get("type") not in {"enabled", "adaptive", "disabled"}
            or not set(reasoning).issubset({"type", "budget_tokens"})
        ):
            raise ValueError("Unsupported Anthropic thinking settings")
        if reasoning.get("type") == "enabled":
            amount = reasoning.get("budget_tokens")
            if type(amount) is not int or not 1024 <= amount < profile.max_output_tokens:
                raise ValueError("Thinking budget must fit inside the output limit")
        elif "budget_tokens" in reasoning:
            raise ValueError("Only enabled thinking accepts a manual budget")
        if reasoning and not profile.omit_temperature:
            raise ValueError("Thinking requires explicit temperature omission")
    elif runtime == "gemini":
        if not set(reasoning).issubset({"thinkingBudget", "thinkingLevel", "includeThoughts"}):
            raise ValueError("Unsupported Gemini thinking settings")
        if "thinkingBudget" in reasoning:
            amount = reasoning["thinkingBudget"]
            if type(amount) is not int or not 0 <= amount < profile.max_output_tokens:
                raise ValueError("Thinking budget must fit inside the output limit")
        if "thinkingBudget" in reasoning and "thinkingLevel" in reasoning:
            raise ValueError("Choose one Gemini thinking control")
    elif reasoning:
        raise ValueError("Reasoning settings are unsupported by this transport")


def serialize(
    profile: ModelProfile, request: ModelRequest, key: str
) -> tuple[str, dict[str, str], dict[str, Any]]:
    body: dict[str, Any] = {
        "model": profile.model_id,
        "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        "max_tokens": request.max_output_tokens,
        "stream": False,
    }
    if not profile.omit_temperature and profile.runtime != "openai":
        body["temperature"] = profile.temperature
    body.update(profile.generation_parameters)
    headers = {"X-Request-ID": str(request.call_id)}
    if profile.authentication != "none":
        headers["Authorization"] = "Bearer " + key
    route = "/chat/completions"
    if profile.runtime == "openai":
        body["store"] = False
        body["max_completion_tokens"] = body.pop("max_tokens")
        if profile.request_protocol == "responses":
            route = "/responses"
            body["input"] = body.pop("messages")
            body["max_output_tokens"] = body.pop("max_completion_tokens")
            if profile.reasoning:
                body["reasoning"] = profile.reasoning
            if request.response_schema:
                body["text"] = {
                    "format": {
                        "type": "json_schema",
                        "name": "research",
                        "schema": request.response_schema,
                        "strict": True,
                    }
                }
    elif profile.runtime == "claude":
        route = "/messages"
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        body["system"] = "\n".join(m.content for m in request.messages if m.role == "system")
        body["messages"] = [m for m in body["messages"] if m["role"] != "system"]
        if profile.reasoning:
            body["thinking"] = profile.reasoning
    elif profile.runtime == "gemini":
        model = profile.model_id.removeprefix("models/")
        route = "/models/" + quote(model, safe="") + ":generateContent"
        headers = {"x-goog-api-key": key}
        config: dict[str, Any] = {"maxOutputTokens": request.max_output_tokens}
        if not profile.omit_temperature:
            config["temperature"] = profile.temperature
        config.update(profile.generation_parameters)
        if profile.reasoning:
            config["thinkingConfig"] = profile.reasoning
        if request.response_schema:
            config.update(
                responseMimeType="application/json", responseJsonSchema=request.response_schema
            )
        body = {
            "contents": [
                {
                    "role": "model" if m.role == "assistant" else "user",
                    "parts": [{"text": m.content}],
                }
                for m in request.messages
                if m.role != "system"
            ],
            "systemInstruction": {
                "parts": [
                    {"text": "\n".join(m.content for m in request.messages if m.role == "system")}
                ]
            },
            "generationConfig": config,
        }
    if request.tools:
        tools = list(request.tools)
        if profile.runtime == "claude":
            body["tools"] = [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "input_schema": t["parameters"],
                }
                for t in tools
            ]
        elif profile.runtime == "gemini":
            body["tools"] = [{"functionDeclarations": tools}]
        elif profile.request_protocol == "responses":
            body["tools"] = [{"type": "function", **t} for t in tools]
        else:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
    return route, headers, body


def normalize(profile: ModelProfile, payload: dict[str, Any]) -> dict[str, Any]:
    """Preserve the original sanitized payload as well as normalized text and blocks."""
    runtime = profile.runtime
    tools: list[dict[str, Any]] = []
    text: list[str] = []
    state = "completed"

    def tokens(value: Any) -> int | None:
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError("Invalid usage value")
        return value

    if runtime == "claude":
        blocks = payload["content"]
        reason = payload.get("stop_reason")
        usage = payload.get("usage") or {}
        incoming, outgoing = tokens(usage.get("input_tokens")), tokens(usage.get("output_tokens"))
        if incoming is not None:
            for field in ("cache_creation_input_tokens", "cache_read_input_tokens"):
                incoming += tokens(usage.get(field, 0)) or 0
        for block in blocks:
            if block["type"] == "text":
                text.append(block["text"])
            elif block["type"] == "tool_use":
                tools.append(block)
        if reason in {"max_tokens", "pause_turn", "model_context_window_exceeded"}:
            state = "incomplete"
        elif reason == "refusal":
            state = "refused"
    elif runtime == "gemini":
        candidates = payload.get("candidates")
        if not candidates and payload.get("promptFeedback", {}).get("blockReason"):
            candidate = {"finishReason": payload["promptFeedback"]["blockReason"]}
        else:
            if not isinstance(candidates, list) or not candidates:
                raise ValueError("Missing candidate response")
            candidate = candidates[0]
        blocks = candidate.get("content", {}).get("parts", [])
        reason = candidate.get("finishReason")
        usage = payload.get("usageMetadata") or {}
        incoming, outgoing = (
            tokens(usage.get("promptTokenCount")),
            tokens(usage.get("candidatesTokenCount")),
        )
        if outgoing is not None:
            outgoing += tokens(usage.get("thoughtsTokenCount", 0)) or 0
        for block in blocks:
            if "text" in block and not block.get("thought"):
                text.append(block["text"])
            if "functionCall" in block:
                tools.append(block["functionCall"])
        if reason in {"MAX_TOKENS", "CONTINUATION"}:
            state = "incomplete"
        elif reason not in {None, "STOP"}:
            state = "refused"
    elif profile.request_protocol == "responses":
        blocks = payload["output"]
        reason = payload.get("status")
        usage = payload.get("usage") or {}
        incoming, outgoing = usage.get("input_tokens"), usage.get("output_tokens")
        for block in blocks:
            if block["type"] == "message":
                for item in block["content"]:
                    if item["type"] == "output_text":
                        text.append(item["text"])
                    elif item["type"] == "refusal":
                        state = "refused"
            elif block["type"] == "function_call":
                tools.append(block)
        if reason != "completed":
            state = "incomplete"
    else:
        choice = payload["choices"][0]
        message = choice["message"]
        reason = choice.get("finish_reason")
        blocks = [message]
        if isinstance(message.get("content"), str):
            text.append(message["content"])
        tools = message.get("tool_calls") or []
        usage = payload.get("usage") or {}
        incoming, outgoing = usage.get("prompt_tokens"), usage.get("completion_tokens")
        if reason == "length":
            state = "incomplete"
        elif reason == "content_filter" or message.get("refusal"):
            state = "refused"
    if not isinstance(blocks, list) or not all(isinstance(b, dict) for b in blocks):
        raise ValueError("Invalid response blocks")
    for amount in (incoming, outgoing):
        if amount is not None and (type(amount) is not int or amount < 0):
            raise ValueError("Invalid usage value")
    if not all(isinstance(t, str) for t in text):
        raise ValueError("Invalid text blocks")
    if not text and not tools and state == "completed":
        raise ValueError("Empty response")
    if text and not "".join(text).strip():
        raise ValueError("Empty response")
    # No native tool is executed here. Orchestration must explicitly authorize a gateway.
    if tools and state == "completed":
        state = "tool_request"
    identity = payload.get("id", payload.get("responseId"))
    model = payload.get("model", payload.get("modelVersion"))
    if any(v is not None and not isinstance(v, str) for v in (identity, model, reason)):
        raise ValueError("Invalid response metadata")
    return dict(
        text="".join(text),
        blocks=[{"type": str(b.get("type", "part")), "data": b} for b in blocks],
        tool_requests=tools,
        finish_reason=reason,
        completion_state=state,
        response_id=identity,
        reported_model_id=model,
        raw_response=json.loads(json.dumps(payload)),
        usage={"input_tokens": incoming, "output_tokens": outgoing},
    )
