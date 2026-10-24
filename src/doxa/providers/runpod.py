"""Optional OpenAI-compatible HTTP adapter. Construction performs no network I/O."""

import asyncio
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
    endpoint = profile.endpoint_id or env.get("RUNPOD_ENDPOINT_ID", "")
    if profile.provider == "runpod" and not (profile.base_url or env.get("RUNPOD_BASE_URL")):
        if endpoint in {"", "replace_me"}:
            raise ValueError("RunPod endpoint identifier is missing")
    override = profile.base_url or (
        env.get("RUNPOD_BASE_URL", "") if profile.provider == "runpod" else ""
    )
    if profile.provider == "openai_compatible" and not override:
        raise ValueError("Compatible provider requires an explicit HTTPS base URL")
    url = override or f"https://api.runpod.ai/v2/{endpoint}/openai/v1"
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid provider URL syntax") from None
    if profile.provider == "runpod":
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
        parsed.scheme != "https"
        or not parsed.hostname
        or (parsed.username or parsed.password or parsed.query or parsed.fragment)
    ):
        raise ValueError("Compatible endpoints require an explicit HTTPS URL without credentials")
    if (
        profile.provider == "runpod"
        and endpoint not in {"", "replace_me"}
        and (parsed.path != f"/v2/{endpoint}/openai/v1")
    ):
        raise ValueError("RunPod endpoint identifier and base URL disagree")
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
        switch, _ = provider_environment(self.profile.provider)
        if not self.profile.enabled or self.env.get(switch, "false").lower() != "true":
            raise ValueError("Provider disabled; explicitly enable the profile and provider switch")
        if self.env.get(self.profile.credential_env) in {None, "", "replace_me"}:
            raise ValueError("Missing backend credential")
        if (request.assignment.provider, request.assignment.model_id) != (
            self.profile.provider,
            self.profile.model_id,
        ):
            raise ValueError("Request assignment differs from pinned model profile")
        if request.response_schema is not None:
            raise NotImplementedError("Native schema-constrained responses are unsupported")
        if not request.messages or any(m.role == "tool" for m in request.messages):
            raise NotImplementedError("Tool messages and empty conversations are unsupported")
        if request.max_output_tokens > self.profile.max_output_tokens:
            raise ValueError("Output token cap exceeded")
        size = sum(len(m.content.encode("utf-8")) + 32 for m in request.messages)
        if (
            sum(len(m.content.encode("utf-8")) for m in request.messages)
            > self.profile.max_input_bytes
        ):
            raise ValueError("Input byte limit exceeded")
        if size + request.max_output_tokens > self.profile.max_context_tokens:
            raise ValueError("Context cap exceeded")

    def redact(self, value: str) -> str:
        result = safe_text(value)
        credential = self.env.get(self.profile.credential_env)
        if credential and credential != "replace_me":
            result = result.replace(credential, "[REDACTED]")
        for name, secret in self.env.items():
            if name.endswith(("_KEY", "_TOKEN", "_PASSWORD")) and secret and secret != "replace_me":
                result = result.replace(secret, "[REDACTED]")
        return result

    async def _generate(self, request: ModelRequest) -> ModelResponse:
        start = time.monotonic()
        category = "configuration"
        retryable = False
        uncertain = False
        try:
            self.validate_request(request)
            key = self.env[self.profile.credential_env]
            body: dict[str, object] = dict(
                model=self.profile.model_id,
                messages=[{"role": m.role, "content": m.content} for m in request.messages],
                max_tokens=request.max_output_tokens,
                temperature=self.profile.temperature,
                stream=False,
            )
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
                response = await client.post(
                    endpoint_url(self.profile, self.env) + "/chat/completions",
                    headers={
                        "Authorization": "Bearer " + key,
                        "X-Request-ID": str(request.call_id),
                    },
                    json=body,
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
            payload = response.json()
            text = payload["choices"][0]["message"]["content"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Invalid completion content")
            usage = payload.get("usage") or {}
            for field in ("prompt_tokens", "completion_tokens"):
                value = usage.get(field)
                if value is not None and (type(value) is not int or value < 0):
                    raise ValueError("Invalid usage value")
            metadata = [payload.get("id"), payload.get("model")]
            if any(value is not None and not isinstance(value, str) for value in metadata):
                raise ValueError("Invalid response metadata")
            return ModelResponse(
                call_id=request.call_id,
                assignment=request.assignment,
                text=self.redact(text),
                execution_kind="live",
                response_id=self.redact(metadata[0]) if metadata[0] else None,
                reported_model_id=self.redact(metadata[1]) if metadata[1] else None,
                usage=Usage(
                    input_tokens=usage.get("prompt_tokens"),
                    output_tokens=usage.get("completion_tokens"),
                    latency_seconds=time.monotonic() - start,
                ),
            )
        except (httpx.ConnectError, httpx.ConnectTimeout):
            category, retryable, uncertain = "transport", True, False
        except (httpx.TimeoutException, TimeoutError):
            category, retryable = "timeout", True
        except NotImplementedError:
            category, uncertain = "unsupported", False
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError):
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
