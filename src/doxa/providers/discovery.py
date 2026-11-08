"""Explicit bounded metadata discovery. Never submits a generation request."""

import asyncio
import json
from collections.abc import Mapping

import httpx
from pydantic import Field

from doxa.core.models import Contract
from doxa.core.profiles import ModelProfile
from doxa.providers.http_limits import bounded_body
from doxa.providers.runpod import endpoint_url

DISCOVERY_TIMEOUT_SECONDS = 5.0


class ConnectionCheck(Contract):
    status: str
    model_ids: tuple[str, ...] = ()
    generation_verified: bool = False
    detail: str = Field(default="Model discovery does not verify generation capabilities")


async def discover_models(
    profile: ModelProfile,
    env: Mapping[str, str],
    *,
    authorize_network: bool = False,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ConnectionCheck:
    if profile.transport == "cli_session":
        return ConnectionCheck(
            status="connection_unverified",
            detail="Account CLI profiles have no HTTP model list. Use Check installed CLIs; "
            "generation remains unverified. No network request was made.",
        )
    if not authorize_network:
        raise PermissionError("Connection discovery requires explicit network authorization")
    url = endpoint_url(profile, env) + "/models"
    headers = {"Accept": "application/json", "Accept-Encoding": "identity"}
    if profile.authentication != "none":
        key = env.get(profile.credential_env or "")
        if not key:
            return ConnectionCheck(
                status="not_configured", detail="Credential reference is missing"
            )
        headers["Authorization"] = "Bearer " + key
        if profile.runtime == "claude":
            del headers["Authorization"]
            headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
    try:
        async with (
            asyncio.timeout(DISCOVERY_TIMEOUT_SECONDS),
            httpx.AsyncClient(
                transport=transport,
                trust_env=False,
                follow_redirects=False,
                timeout=DISCOVERY_TIMEOUT_SECONDS,
            ) as client,
        ):
            async with client.stream("GET", url, headers=headers) as response:
                if response.status_code in {404, 405}:
                    return ConnectionCheck(
                        status="connection_unverified",
                        detail="This endpoint does not expose model discovery",
                    )
                response.raise_for_status()
                if response.is_redirect:
                    raise ValueError("Redirect refused")
                raw = await bounded_body(response, 262144)
        payload = json.loads(raw)
        ids = tuple(item["id"] for item in payload["data"])
        if len(ids) > 2000 or any(not isinstance(i, str) or len(i) > 2000 for i in ids):
            raise ValueError("Invalid model metadata")
        return ConnectionCheck(
            status="connection_unverified",
            model_ids=ids,
            detail="Endpoint reachable; generation and capabilities remain unverified",
        )
    except (httpx.HTTPError, ValueError, TypeError, KeyError, TimeoutError, RecursionError):
        return ConnectionCheck(
            status="unavailable", detail="Connection or metadata validation failed"
        )
