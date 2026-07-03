"""Listening-socket enumeration (ADR 0003, rung 2).

Linux-first via ``/proc/net/tcp{,6}`` (stdlib only -- psutil stays behind the doctor
extra). This finds candidate ports for nonstandard bridge setups; the WS handshake in
``ws.py`` then confirms which, if any, are real bridges. Returns nothing on non-Linux
hosts (no ``/proc``), where detection falls back to the default-port probe.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_LISTEN_STATE = "0A"  # TCP_LISTEN in /proc/net/tcp


@dataclass(frozen=True)
class ListeningSocket:
    port: int
    loopback_only: bool  # bound to 127.0.0.1 / ::1 -- a phone cannot reach it
    ipv6: bool


def _ipv4_is_loopback(hex_ip: str) -> bool:
    # /proc stores the address little-endian; the first octet is the last byte pair.
    return int(hex_ip[6:8], 16) == 127


def _ipv6_is_loopback(hex_ip: str) -> bool:
    # ::1 is stored as 31 zeros then "01000000" (word-swapped); match it directly.
    return hex_ip.upper() == "00000000000000000000000001000000"


def parse_proc_net_tcp(text: str, *, ipv6: bool = False) -> list[ListeningSocket]:
    """Pure parse of ``/proc/net/tcp`` content into listening sockets."""
    out: list[ListeningSocket] = []
    for line in text.splitlines()[1:]:  # skip the column header
        cols = line.split()
        if len(cols) < 4 or cols[3] != _LISTEN_STATE:
            continue
        local = cols[1]
        if ":" not in local:
            continue
        hex_ip, hex_port = local.rsplit(":", 1)
        try:
            port = int(hex_port, 16)
        except ValueError:
            continue
        loopback = _ipv6_is_loopback(hex_ip) if ipv6 else _ipv4_is_loopback(hex_ip)
        out.append(ListeningSocket(port=port, loopback_only=loopback, ipv6=ipv6))
    return out


def listening_ports(*, include_loopback: bool = False) -> list[int]:
    """Return distinct listening TCP ports on this host, best LAN-reachable first.

    Empty on hosts without ``/proc`` (non-Linux). Loopback-only ports are excluded by
    default because a phone cannot reach them (ADR 0007).
    """
    sockets: list[ListeningSocket] = []
    for path, is_v6 in (("/proc/net/tcp", False), ("/proc/net/tcp6", True)):
        try:
            text = Path(path).read_text()
        except OSError:
            continue
        sockets.extend(parse_proc_net_tcp(text, ipv6=is_v6))

    ports: list[int] = []
    for sock in sockets:
        if sock.loopback_only and not include_loopback:
            continue
        if sock.port not in ports:
            ports.append(sock.port)
    return ports
