"""Fixed document-parser entry point. Reads bounded data only; never evaluates code."""

import base64
import json
import sys


def main() -> None:
    if sys.platform != "win32":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (6, 6))
    from doxa.retrieval.documents import parse_bytes

    raw = sys.stdin.buffer.read(14_000_001)
    if len(raw) > 14_000_000:
        raise ValueError("Document input too large")
    body = json.loads(raw)
    parsed = parse_bytes(body["filename"], base64.b64decode(body["data"], validate=True))
    # This is a JSON transport, independent of a Windows console's legacy encoding.
    sys.stdout.buffer.write(parsed.model_dump_json().encode("utf-8"))


if __name__ == "__main__":
    main()
