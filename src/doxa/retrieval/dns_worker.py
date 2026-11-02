"""Fixed credential-free resolver entry point; the parent owns its time limit."""

import ipaddress
import json
import socket
import sys


def public_addresses(host: str) -> tuple[str, ...]:
    addresses = tuple(
        dict.fromkeys(str(a[4][0]) for a in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM))
    )
    if (
        not addresses
        or len(addresses) > 64
        or any(not ipaddress.ip_address(a).is_global for a in addresses)
    ):
        raise PermissionError("Non-public or oversized DNS result refused")
    return addresses


def main() -> None:
    try:
        if len(sys.argv) < 2 or len(sys.argv[-1]) > 253:
            raise ValueError
        json.dump({"addresses": public_addresses(sys.argv[-1])}, sys.stdout)
    except (OSError, ValueError):
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
