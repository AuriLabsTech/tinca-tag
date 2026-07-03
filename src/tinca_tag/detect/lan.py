"""LAN address resolution (ADR 0006, 0007).

The ``host`` in the QR must be LAN-reachable for a phone -- never a container IP or
localhost. The primary LAN IP is found with the stdlib UDP-socket trick: a datagram
socket is "connected" to a public address so the OS picks the outbound interface, then
its source IP is read back. No datagram is ever sent, so this makes no network call.
"""

from __future__ import annotations

import socket

# Any routable address works; UDP connect only selects an interface, it sends nothing.
_ROUTE_HINT = ("8.8.8.8", 80)


def primary_lan_ip() -> str | None:
    """Return the host's primary LAN IPv4, or ``None`` if only loopback is available."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(_ROUTE_HINT)  # no packet sent; sets the default route
        ip = sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()
    if not ip or ip.startswith("127."):  # loopback is not LAN-reachable
        return None
    return ip


def mdns_host() -> str:
    """Return the host's mDNS ``.local`` name (the ``--mdns`` host, ADR 0006)."""
    name = socket.gethostname().split(".")[0]
    return f"{name}.local"
