"""Bound identity-encoded provider bodies before parsing or content decoding."""

import httpx


class ResponseLimitError(ValueError):
    pass


async def bounded_body(response: httpx.Response, limit: int) -> bytes:
    # aiter_bytes decodes before yielding. Refuse compression before touching the
    # stream so a single compressed chunk cannot allocate beyond our body cap.
    if response.headers.get("content-encoding", "identity").strip().lower() != "identity":
        raise ResponseLimitError("Compressed provider responses are unsupported")
    body = bytearray()
    async for chunk in response.aiter_bytes():
        if len(body) + len(chunk) > limit:
            raise ResponseLimitError("Provider response exceeds the byte limit")
        body.extend(chunk)
    return bytes(body)
