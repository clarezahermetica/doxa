"""Explicit bounded metadata discovery. Never submits a generation request."""

import asyncio
import json
from collections.abc import Mapping

import httpx
from pydantic import Field

from doxa.core.credential_store import MANAGED_PREFIX
from doxa.core.models import Contract
from doxa.core.profiles import ModelProfile
from doxa.core.secrets import secret_values
from doxa.providers.http_limits import bounded_body
from doxa.providers.runpod import endpoint_url

DISCOVERY_TIMEOUT_SECONDS = 5.0


class ConnectionCheck(Contract):
    status: str
    model_ids: tuple[str, ...] = ()
    runtime_reachable: bool | None = None
    model_listed: bool | None = None
    credential_status: str = "unverified"
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
    reachable: bool | None = None
    credential_status = "not_required"
    key = ""
    headers = {"Accept": "application/json", "Accept-Encoding": "identity"}
    if profile.authentication != "none":
        key = env.get(profile.credential_env or "", "")
        if not key or key == "replace_me":
            return ConnectionCheck(
                status="not_configured",
                credential_status="missing_or_unavailable",
                detail="Credential reference is missing or the secure vault is unavailable",
            )
        credential_status = "available"
        headers["Authorization"] = "Bearer " + key
        if profile.runtime == "claude":
            del headers["Authorization"]
            headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
        elif profile.runtime == "gemini":
            del headers["Authorization"]
            headers["x-goog-api-key"] = key
    try:
        base = endpoint_url(profile, env)
        aliases = (profile.credential_env,) if profile.credential_env else ()
        known = secret_values(credential_names=aliases)
        if (key and key in base) or any(value in base for value in known):
            raise ValueError("Credential-bearing endpoint refused")
        ollama = profile.local and profile.provider == "ollama"
        if ollama:
            parsed = httpx.URL(base)
            url = str(parsed.copy_with(path="/api/tags"))
        else:
            url = base + "/models"
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
                reachable = True
                if response.status_code in {401, 403}:
                    return ConnectionCheck(
                        status="not_configured",
                        runtime_reachable=True,
                        credential_status=credential_status,
                        detail="Runtime responded but refused metadata authentication",
                    )
                if response.status_code in {404, 405}:
                    return ConnectionCheck(
                        status="connection_unverified",
                        runtime_reachable=True,
                        credential_status=credential_status,
                        detail="This endpoint does not expose model discovery",
                    )
                response.raise_for_status()
                if response.is_redirect:
                    raise ValueError("Redirect refused")
                raw = await bounded_body(response, 262144)
        payload = json.loads(raw)
        group = "models" if ollama or profile.runtime == "gemini" else "data"
        field = "name" if group == "models" else "id"
        rows = payload[group]
        if not isinstance(rows, list) or len(rows) > 2000:
            raise ValueError("Invalid model metadata")
        names = []
        secrets = {
            value
            for name, value in env.items()
            if name.startswith(MANAGED_PREFIX)
            or name.endswith(("_KEY", "_TOKEN", "_PASSWORD", "_SECRET", "_CREDENTIAL"))
        }
        secrets.update(known)
        secrets.add(key)
        secrets.discard("")
        secrets.discard("replace_me")
        for item in rows:
            name = item[field]
            if (
                not isinstance(name, str)
                or not 0 < len(name) <= 2000
                or name != name.strip()
                or not name.isprintable()
            ):
                raise ValueError("Invalid model metadata")
            # Do not turn echoed credentials into selectable or persistable model IDs.
            if not any(value in name for value in secrets):
                names.append(name)
        ids = tuple(dict.fromkeys(names))
        return ConnectionCheck(
            status="connection_unverified",
            model_ids=ids,
            runtime_reachable=True,
            model_listed=(
                profile.model_id in ids
                or (profile.runtime == "gemini" and "models/" + profile.model_id in ids)
            ),
            credential_status=credential_status,
            detail="Endpoint reachable; generation and capabilities remain unverified",
        )
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return ConnectionCheck(
            status="unavailable",
            runtime_reachable=False,
            credential_status=credential_status,
            detail="Could not reach the runtime. Check the endpoint and whether it is running.",
        )
    except (httpx.HTTPError, ValueError, TypeError, KeyError, TimeoutError, RecursionError):
        return ConnectionCheck(
            status="unavailable",
            runtime_reachable=reachable,
            credential_status=credential_status,
            detail="Connection or metadata validation failed; no generation was requested",
        )



def describe_connection(report: ConnectionCheck) -> str:
    reachable = {True: "yes", False: "no", None: "unverified"}[report.runtime_reachable]
    listed = {True: "yes", False: "no", None: "unverified"}[report.model_listed]
    return (
        f"{report.detail}\nCredential: {report.credential_status.replace('_', ' ')}. "
        f"Runtime reachable: {reachable}. Selected model listed: {listed}.\n"
        "Capability verification: none. Inference untested by this check. "
        "Execution authorization is separate."
    )
