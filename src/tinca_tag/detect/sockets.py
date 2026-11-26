"""Listening-socket enumeration (ADR 0003, rung 2).

Stdlib only. Linux reads ``/proc/net/tcp{,6}``; macOS, which has no ``/proc``, parses
``nettop -L 1 -m tcp -n -J state`` (read-only, no root needed; psutil needs root there,
and netstat prints nothing under an ad-hoc-signed Python on macOS 27.2.1, ADR 0012).
This finds candidate ports for nonstandard bridge setups; the WS handshake in ``ws.py``
then confirms which, if any, are real bridges. Returns nothing on other hosts, or if
nettop fails, where detection falls back to the default-port probe and says so.
"""

from __future__ import annotations

import ipaddress
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_LISTEN_STATE = "0A"  # TCP_LISTEN in /proc/net/tcp
PROC_NET_TCP = Path("/proc/net/tcp")
_PLATFORM = sys.platform  # read through here so tests never patch the interpreter's
NETTOP = "/usr/bin/nettop"  # absolute: no PATH lookup
# One sample (-L 1), TCP only, numeric addresses, only the state column.
_NETTOP_ARGS = ["-L", "1", "-m", "tcp", "-n", "-J", "state"]
_NETTOP_TIMEOUT = 5.0


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


def parse_nettop(text: str) -> list[ListeningSocket]:
    """Pure parse of macOS ``nettop -L 1 -m tcp -n -J state`` output into listeners.

    Socket rows look like ``tcp4 127.0.0.1:8021<->*:*,Listen,`` and
    ``tcp6 *.8766<->*.*,Listen,``: IPv4 joins host and port with ``:``, IPv6 with the
    last ``.``; ``*`` is every interface. Process rows (``launchd.1,,``) and other
    states are skipped.
    """
    out: list[ListeningSocket] = []
    for line in text.splitlines():
        fields = line.split(",")
        if len(fields) < 2 or fields[1] != "Listen":
            continue
        proto, _, flow = fields[0].partition(" ")
        if proto not in ("tcp4", "tcp6") or "<->" not in flow:
            continue
        local = flow.split("<->", 1)[0]
        sep = ":" if proto == "tcp4" else "."
        if sep not in local:
            continue
        addr, port_text = local.rsplit(sep, 1)
        try:
            port = int(port_text)
        except ValueError:
            continue
        host, _, scope = addr.partition("%")  # scoped, e.g. fe80::1%lo0
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            loopback = False  # "*": every interface
        else:
            mapped = getattr(ip, "ipv4_mapped", None)  # ::ffff:127.0.0.1, pre-3.13
            loopback = ip.is_loopback or bool(mapped and mapped.is_loopback)
            loopback = loopback or scope.startswith("lo")
        out.append(ListeningSocket(port=port, loopback_only=loopback, ipv6=proto == "tcp6"))
    return out


def _run_nettop() -> str | None:
    """Run the fixed, read-only nettop command; ``None`` when it gave no usable list.

    Output with no listener at all also counts as a failure: a Mac always has system
    listeners, so an empty list means the scan was filtered or the format changed, and
    reading it as "no ports" would hide a running bridge (ADR 0012).
    """
    try:
        result = subprocess.run(
            [NETTOP, *_NETTOP_ARGS],
            capture_output=True,
            text=True,
            # Process names are printed as-is; one that is not UTF-8 must not crash qr.
            encoding="utf-8",
            errors="replace",
            timeout=_NETTOP_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not parse_nettop(result.stdout):
        return None
    return result.stdout


def _has_proc() -> bool:
    return PROC_NET_TCP.exists() or PROC_NET_TCP.with_name("tcp6").exists()


def _all_listening() -> list[ListeningSocket]:
    """Every listening socket on this host: ``/proc`` on Linux, nettop on macOS."""
    if _has_proc():
        sockets: list[ListeningSocket] = []
        for path, is_v6 in ((PROC_NET_TCP, False), (PROC_NET_TCP.with_name("tcp6"), True)):
            try:
                text = path.read_text()
            except OSError:
                continue
            sockets.extend(parse_proc_net_tcp(text, ipv6=is_v6))
        return sockets
    if _PLATFORM == "darwin":
        text = _run_nettop()
        return parse_nettop(text) if text else []
    return []


def listening_ports(*, include_loopback: bool = False) -> list[int]:
    """Return distinct listening TCP ports on this host, best LAN-reachable first.

    Empty where enumeration is unavailable (see :func:`enumeration_available`).
    Loopback-only ports are excluded by default because a phone cannot reach them
    (ADR 0007).
    """
    ports: list[int] = []
    for sock in _all_listening():
        if sock.loopback_only and not include_loopback:
            continue
        if sock.port not in ports:
            ports.append(sock.port)
    return ports


def enumeration_available() -> bool:
    """Can we enumerate listening sockets here? Linux with ``/proc``, or macOS when
    nettop gives a usable list (a nettop that fails is no scan, not an empty one)."""
    if _has_proc():
        return True
    return _PLATFORM == "darwin" and _run_nettop() is not None


def bind_status(port: int) -> str:
    """How ``port`` is bound on this host, for the doctor's reachability tree (ADR 0009).

    ``"exposed"`` (bound to a routable address, e.g. ``0.0.0.0``, so the LAN can reach it),
    ``"loopback"`` (bound to ``127.0.0.1``/``::1`` only, so a phone cannot), or ``"absent"``
    (nothing listening on this port here -- e.g. an unpublished container port seen from
    the host). ``"absent"`` wherever enumeration is unavailable or fails.
    """
    on_port = [sock for sock in _all_listening() if sock.port == port]
    if not on_port:
        return "absent"
    if any(not sock.loopback_only for sock in on_port):
        return "exposed"
    return "loopback"
