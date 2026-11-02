"""Optional OpenAI-compatible HTTP adapter. Construction performs no network I/O."""

import asyncio
import json
import time
from collections.abc import Mapping
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from doxa.core.models import Usage
from doxa.core.profiles import ModelProfile
from doxa.core.secrets import safe_text
from doxa.providers.contracts import (
    Capabilities,
    ModelRequest,
    ModelResponse,
    ProviderConfig,
    ProviderError,
)


def endpoint_url(profile: ModelProfile, env: Mapping[str, str]) -> str:
    if profile.local and profile.runtime != "openai_compatible":
        raise ValueError("Unbilled local HTTP requires the loopback compatible adapter")
    if profile.runtime in {"openai", "claude", "gemini"}:
        official = {
            "openai": "https://api.openai.com/v1",
            "claude": "https://api.anthropic.com/v1",
            "gemini": "https://generativelanguage.googleapis.com/v1beta",
        }[profile.runtime]
        if profile.base_url not in {None, official} or profile.endpoint_id:
            raise ValueError("Native providers require their fixed official HTTPS origin")
        return official
    endpoint = profile.endpoint_id or env.get("RUNPOD_ENDPOINT_ID", "")
    if profile.runtime == "runpod" and not (profile.base_url or env.get("RUNPOD_BASE_URL")):
        if endpoint in {"", "replace_me"}:
            raise ValueError("RunPod endpoint identifier is missing")
    override = profile.base_url or (
        env.get("RUNPOD_BASE_URL", "") if profile.runtime == "runpod" else ""
    )
    if profile.runtime == "openai_compatible" and not override:
        raise ValueError("Compatible provider requires an explicit HTTPS base URL")
    url = override or f"https://api.runpod.ai/v2/{endpoint}/openai/v1"
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid provider URL syntax") from None
    if profile.runtime == "runpod":
        import re

        if (
            parsed.scheme != "https"
            or parsed.hostname != "api.runpod.ai"
            or (
                port is not None
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or not re.fullmatch(r"/v2/[A-Za-z0-9_-]+/openai/v1", parsed.path)
            )
        ):
            raise ValueError("Invalid RunPod base URL; expected official vLLM endpoint")
    elif (
        (parsed.scheme != "https" and not (profile.local and parsed.scheme == "http"))
        or not parsed.hostname
        or (parsed.username or parsed.password or parsed.query or parsed.fragment)
    ):
        raise ValueError("Compatible endpoints require an explicit HTTPS URL without credentials")
    if (
        profile.runtime == "runpod"
        and endpoint not in {"", "replace_me"}
        and (parsed.path != f"/v2/{endpoint}/openai/v1")
    ):
        raise ValueError("RunPod endpoint identifier and base URL disagree")
    if profile.local and (
        profile.runtime != "openai_compatible"
        or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
    ):
        raise ValueError("Local runtime requires a loopback OpenAI-compatible endpoint")
    if profile.authentication == "none" and not profile.local:
        # Public remote APIs can use no authentication, but remain paid/external guarded.
        pass
    return url.rstrip("/")


class RunPodProvider:
    def __init__(
        self,
        profile: ModelProfile,
        env: Mapping[str, str],
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.profile = profile
        self.env = env
        self.transport = transport
        self.tasks: dict[UUID, asyncio.Task[ModelResponse]] = {}

    def capabilities(self, config: ProviderConfig) -> Capabilities:
        return self.profile.capabilities

    async def generate(self, request: ModelRequest) -> ModelResponse:
        task = asyncio.create_task(self._generate(request))
        self.tasks[request.call_id] = task
        try:
            return await task
        finally:
            self.tasks.pop(request.call_id, None)

    async def cancel(self, call_id: UUID) -> bool:
        task = self.tasks.get(call_id)
        if task is None:
            return False
        task.cancel()
        return True  # Cancels local wait, not a guarantee of remote job/billing cancellation.

    def validate_request(self, request: ModelRequest) -> None:
        from doxa.providers.registry import provider_environment, validate_profile

        validate_profile(self.profile, self.env)
        switch, _ = provider_environment(self.profile.runtime)
        if not self.profile.enabled or (
            not self.profile.local and self.env.get(switch, "false").lower() != "true"
        ):
            raise ValueError("Provider disabled; explicitly enable the profile and provider switch")
        if self.profile.authentication != "none" and self.env.get(self.profile.credential_env) in {
            None,
            "",
            "replace_me",
        }:
            raise ValueError("Missing backend credential")
        if (request.assignment.provider, request.assignment.model_id) != (
            self.profile.provider,
            self.profile.model_id,
        ):
            raise ValueError("Request assignment differs from pinned model profile")
        if (
            request.profile_id is not None
            and request.profile_id != self.profile.id
            or request.profile_version is not None
            and request.profile_version != self.profile.version
            or request.adapter is not None
            and request.adapter != self.profile.runtime
        ):
            raise ValueError("Request profile metadata differs from the pinned configuration")
        if request.response_schema is not None and not (
            self.profile.capabilities.structured_output == "native"
            and (self.profile.request_protocol == "responses" or self.profile.runtime == "gemini")
        ):
            raise NotImplementedError("Native schema-constrained responses are unsupported")
        if request.tools:
            if self.profile.capabilities.tool_calling != "native":
                raise NotImplementedError("Native tools require declared model support")
            for tool in request.tools:
                if set(tool) - {"name", "description", "parameters"} or not all(
                    name in tool for name in ("name", "parameters")
                ):
                    raise ValueError("Only declared function tools are permitted")
        if not request.messages or any(m.role == "tool" for m in request.messages):
            raise NotImplementedError("Tool messages and empty conversations are unsupported")
        if request.max_output_tokens > self.profile.max_output_tokens:
            raise ValueError("Output token cap exceeded")
        tool_size = len(json.dumps(request.tools).encode()) if request.tools else 0
        size = sum(len(m.content.encode("utf-8")) + 32 for m in request.messages) + tool_size
        if (
            sum(len(m.content.encode("utf-8")) for m in request.messages)
            > self.profile.max_input_bytes
        ):
            raise ValueError("Input byte limit exceeded")
        if size + request.max_output_tokens > self.profile.max_context_tokens:
            raise ValueError("Context cap exceeded")

    def redact(self, value: str) -> str:
        values = [self.env.get(self.profile.credential_env, "")]
        values.extend(
            secret
            for name, secret in self.env.items()
            if name.endswith(("_KEY", "_TOKEN", "_PASSWORD", "_SECRET"))
        )
        return safe_text(value, extra_values=values)

    async def _generate(self, request: ModelRequest) -> ModelResponse:
        start = time.monotonic()
        category = "configuration"
        retryable = False
        uncertain = False
        try:
            self.validate_request(request)
            key = self.env.get(self.profile.credential_env, "")
            from doxa.providers.wire import normalize, serialize

            route, headers, body = serialize(self.profile, request, key)
            category = "transport"
            uncertain = True
            timeout = min(request.timeout_seconds, self.profile.timeout_seconds)
            async with (
                asyncio.timeout(timeout),
                httpx.AsyncClient(
                    transport=self.transport,
                    follow_redirects=False,
                    trust_env=False,
                    timeout=timeout,
                ) as client,
            ):
                async with client.stream(
                    "POST",
                    endpoint_url(self.profile, self.env) + route,
                    headers=headers,
                    json=body,
                ) as streamed:
                    chunks = []
                    received = 0
                    async for chunk in streamed.aiter_bytes():
                        received += len(chunk)
                        if received > 2_000_000:
                            category = "invalid_response"
                            raise ValueError("Response size limit exceeded")
                        chunks.append(chunk)
                    response = httpx.Response(
                        streamed.status_code,
                        headers=streamed.headers,
                        content=b"".join(chunks),
                        request=streamed.request,
                    )
            if response.status_code in {401, 403}:
                category = "authentication"
            elif response.status_code == 429:
                category = "quota"
            elif 400 <= response.status_code < 500:
                category = "invalid_request"
            elif response.status_code >= 500:
                retryable = True
            response.raise_for_status()
            if response.is_redirect:
                raise ValueError("Redirect refused")
            category = "invalid_response"
            if len(response.content) > 2_000_000:
                raise ValueError("Response size limit exceeded")
            payload = json.loads(self.redact(response.text))
            if not isinstance(payload, dict):
                raise ValueError("Invalid response object")
            normalized = normalize(self.profile, payload)
            normalized["usage"]["latency_seconds"] = time.monotonic() - start
            return ModelResponse.model_validate(
                dict(
                    call_id=request.call_id,
                    assignment=request.assignment,
                    execution_kind="live",
                    provider_request_id=self.redact(
                        response.headers.get("x-request-id", response.headers.get("request-id", ""))
                    )
                    or None,
                    **normalized,
                )
            )
        except (httpx.ConnectError, httpx.ConnectTimeout):
            category, retryable, uncertain = "transport", True, False
        except (httpx.TimeoutException, TimeoutError):
            category, retryable = "timeout", True
        except NotImplementedError:
            category, uncertain = "unsupported", False
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError, AttributeError):
            pass
        return ModelResponse(
            call_id=request.call_id,
            assignment=request.assignment,
            execution_kind="live",
            error=ProviderError.model_validate(
                dict(
                    category=category,
                    retryable=retryable,
                    billing_uncertain=uncertain,
                    safe_message="Provider request failed ("
                    + category
                    + "); raw response suppressed",
                )
            ),
            usage=Usage(latency_seconds=time.monotonic() - start),
        )
