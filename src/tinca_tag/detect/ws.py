"""WebSocket handshake probe (ADR 0003).

Distinguishes the two bridges by the negotiated WS subprotocol, not by port:
foxglove_bridge advertises ``foxglove.websocket.v1`` in the 101 response; rosbridge
does not. One probe, offering the foxglove subprotocol, settles both "is this a bridge"
and "which bridge". A plain-TCP attempt then a TLS attempt also settles ``secure``.

Probing the robot's own bridge on the LAN is detection, not an outbound network call:
nothing leaves the LAN, so the offline-core promise (ADR 0002, which forbids hosted /
internet round-trips) holds. ``secure`` probing does not verify the cert -- bridges
commonly use self-signed TLS, and this is a reachability check, not a trust boundary.
"""

from __future__ import annotations

import base64
import os
import socket
import ssl
from dataclasses import dataclass

from ..endpoint import Protocol

# Foxglove negotiates one of these WS subprotocols. foxglove.websocket.v1 is the classic
# documented token; foxglove_bridge 3.x (the Foxglove SDK) negotiates foxglove.sdk.v1.
# Crucially, foxglove_bridge REJECTS a handshake (HTTP 400) that offers no subprotocol it
# supports, so we must offer every known token. rosbridge ignores the offer and 101s
# without echoing one. Verified against real bridges in CP-C; see ADR 0003.
FOXGLOVE_SUBPROTOCOLS = ("foxglove.sdk.v1", "foxglove.websocket.v1")
_SWITCHING_PROTOCOLS = 101
_HEADER_END = b"\r\n\r\n"
_DEFAULT_TIMEOUT = 1.0


@dataclass(frozen=True)
class HandshakeResponse:
    status: int | None
    subprotocols: list[str]


@dataclass(frozen=True)
class ProbeResult:
    protocol: Protocol
    secure: bool


def new_ws_key() -> str:
    """A fresh base64 Sec-WebSocket-Key (16 random bytes)."""
    return base64.b64encode(os.urandom(16)).decode("ascii")


def build_handshake(host: str, port: int, key: str, *, offer_foxglove: bool = True) -> bytes:
    """Build the client WS opening handshake, offering every known foxglove subprotocol."""
    lines = [
        "GET / HTTP/1.1",
        f"Host: {host}:{port}",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Key: {key}",
        "Sec-WebSocket-Version: 13",
    ]
    if offer_foxglove:
        lines.append("Sec-WebSocket-Protocol: " + ", ".join(FOXGLOVE_SUBPROTOCOLS))
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")


def parse_handshake(raw: bytes) -> HandshakeResponse:
    """Pure parse of a server handshake response into status + offered subprotocols."""
    head = raw.split(_HEADER_END, 1)[0].decode("latin-1", "replace")
    lines = head.split("\r\n")
    status: int | None = None
    if lines and lines[0].startswith("HTTP/"):
        parts = lines[0].split(None, 2)
        if len(parts) >= 2 and parts[1].isdigit():
            status = int(parts[1])
    subprotocols: list[str] = []
    for line in lines[1:]:
        name, sep, value = line.partition(":")
        if sep and name.strip().lower() == "sec-websocket-protocol":
            subprotocols.extend(p.strip() for p in value.split(",") if p.strip())
    return HandshakeResponse(status=status, subprotocols=subprotocols)


def classify(resp: HandshakeResponse) -> Protocol | None:
    """Map a handshake response to a protocol, or ``None`` if it is not a WS bridge."""
    if resp.status != _SWITCHING_PROTOCOLS:
        return None
    if any(sub in resp.subprotocols for sub in FOXGLOVE_SUBPROTOCOLS):
        return "foxglove-ws"
    return "rosbridge"  # a 101 without a foxglove subprotocol (ADR 0003)


def _handshake_over(sock: socket.socket, host: str, port: int) -> Protocol | None:
    """Send the handshake on an open socket and classify the response."""
    sock.sendall(build_handshake(host, port, new_ws_key()))
    chunks = b""
    while _HEADER_END not in chunks and len(chunks) < 4096:
        data = sock.recv(1024)
        if not data:
            break
        chunks += data
    return classify(parse_handshake(chunks))


def _probe_once(host: str, port: int, *, use_tls: bool, timeout: float) -> Protocol | None:
    """One connection attempt (plain or TLS). Returns protocol or None."""
    try:
        raw = socket.create_connection((host, port), timeout=timeout)
    except OSError:
        return None
    try:
        raw.settimeout(timeout)
        if use_tls:
            ctx = ssl._create_unverified_context()  # LAN reachability, not a trust check
            with ctx.wrap_socket(raw, server_hostname=host) as tls:
                return _handshake_over(tls, host, port)
        return _handshake_over(raw, host, port)
    except (OSError, ssl.SSLError):
        return None
    finally:
        if not use_tls:
            raw.close()


def probe(host: str, port: int, *, timeout: float = _DEFAULT_TIMEOUT) -> ProbeResult | None:
    """Probe ``host:port``; return the bridge protocol + secure flag, or ``None``.

    Tries plain WS first, then TLS, so ``secure`` reflects what the server actually
    speaks (ADR 0003's TLS-handshake rung).
    """
    proto = _probe_once(host, port, use_tls=False, timeout=timeout)
    if proto is not None:
        return ProbeResult(protocol=proto, secure=False)
    proto = _probe_once(host, port, use_tls=True, timeout=timeout)
    if proto is not None:
        return ProbeResult(protocol=proto, secure=True)
    return None
