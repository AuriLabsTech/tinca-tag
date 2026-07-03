"""Bridge and endpoint detection (ADR 0003, 0007).

Produces a validated :class:`~tinca_tag.endpoint.Endpoint` by reading the actual running
config, in source precedence: explicit flags override; otherwise a WS-handshake probe of
local listening ports then the default ports (9090/8765) settles port, protocol, and
secure. The emitted ``host`` is always the LAN-reachable address (never a container IP or
localhost), validated by probing it the way the phone would (ADR 0007).

The pip CLI lives on these rungs (process/socket enumeration, default-port probe, flags);
the ros2 ament variant adds the authoritative ROS-param rung on top. I/O is injected so
the rung logic is unit-testable without a network.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..endpoint import Endpoint, Protocol
from . import container, lan, sockets
from . import ws as ws_probe

DEFAULT_PORTS = (9090, 8765)  # rosbridge, foxglove
LOCAL_HOST = "127.0.0.1"
_MAX_NONDEFAULT_PORTS = 25  # bound how many listening ports we WS-probe (no silent cap)


@dataclass
class Detection:
    """The result of detection: an Endpoint (when found) plus echo/diagnostic context."""

    endpoint: Endpoint | None
    source: str  # how the fields were resolved, for the confirmation echo
    lan_ip: str | None
    reachable: bool | None  # probed <host>:<port> as the phone would; None = not checked
    in_container: bool
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.endpoint is not None


def _candidate_ports(port: int | None, listening: list[int]) -> list[int]:
    """Ordered, de-duplicated ports to probe: an explicit port, else defaults + listening."""
    if port is not None:
        return [port]
    ordered = list(DEFAULT_PORTS)
    extra = [p for p in listening if p not in ordered][:_MAX_NONDEFAULT_PORTS]
    return ordered + extra


def _no_detection(lan_ip: str | None, inside: bool) -> Detection:
    notes = [
        "No ROS 2 bridge detected.",
        "  Is rosbridge or foxglove_bridge running on this machine?",
        "  On a nonstandard port? Pass --port <port> --protocol rosbridge|foxglove-ws.",
        "  Pointing at another machine? Pass --host <ip> --port <port>.",
        "  Guided diagnosis arrives with `tinca-tag doctor` (M2).",
    ]
    return Detection(
        endpoint=None,
        source="none",
        lan_ip=lan_ip,
        reachable=None,
        in_container=inside,
        notes=notes,
    )


def detect(
    *,
    host: str | None = None,
    port: int | None = None,
    protocol: Protocol | None = None,
    secure: bool | None = None,
    mdns: bool = False,
    timeout: float = 1.0,
    probe_fn=ws_probe.probe,
    lan_ip_fn=lan.primary_lan_ip,
    mdns_fn=lan.mdns_host,
    ports_fn=sockets.listening_ports,
    in_container_fn=container.in_container,
) -> Detection:
    """Resolve a LAN-reachable :class:`Endpoint`, reading reality per ADR 0003/0007."""
    notes: list[str] = []
    inside = in_container_fn()
    lan_ip = lan_ip_fn()

    # 1. The host that goes in the QR -- always LAN-reachable (ADR 0006/0007).
    if host:
        emit_host = host
    elif mdns:
        emit_host = mdns_fn()
    else:
        emit_host = lan_ip

    # 2. Resolve port / protocol / secure: flags win, else probe.
    known_port, known_proto, known_secure = port, protocol, secure
    source: str

    if known_port is not None and known_proto is not None and known_secure is not None:
        source = "flags"
    else:
        listening = ports_fn() if port is None else []
        candidate_ports = _candidate_ports(port, listening)
        targets = [LOCAL_HOST]
        if host and host not in targets:
            targets.append(host)  # remote / inside-container target

        hit = None
        for target in targets:
            for candidate in candidate_ports:
                result = probe_fn(target, candidate, timeout=timeout)
                if result is not None:
                    hit = (target, candidate, result)
                    break
            if hit:
                break

        if hit is not None:
            target, candidate, result = hit
            known_port = port if port is not None else candidate
            known_proto = protocol if protocol is not None else result.protocol
            known_secure = secure if secure is not None else result.secure
            source = f"probe ({target}:{candidate})"
        elif known_port is not None and known_proto is not None:
            # Enough was specified to emit; we just could not confirm secure -> default 0.
            known_secure = secure if secure is not None else False
            source = "flags"
            notes.append(
                f"Could not probe {LOCAL_HOST}:{known_port}; assuming secure=0 "
                "(pass --secure to override)."
            )
        else:
            return _no_detection(lan_ip, inside)

    # 3. We need a LAN-reachable host to emit.
    if not emit_host:
        return Detection(
            endpoint=None,
            source=source,
            lan_ip=lan_ip,
            reachable=None,
            in_container=inside,
            notes=["Could not determine this host's LAN IP. Pass --host <ip> or --mdns."],
        )

    endpoint = Endpoint(
        host=emit_host, port=known_port, protocol=known_proto, secure=bool(known_secure)
    )

    # 4. Reachability: probe the emitted host the way the phone will (ADR 0007).
    reachable: bool | None = None
    if inside:
        notes.append(
            f"Running inside a container; cannot verify a phone can reach {emit_host} "
            "(ADR 0007). Run on the host for a verified QR."
        )
    elif emit_host.endswith(".local"):
        notes.append(f"Cannot verify .local reachability from here ({emit_host}).")
    else:
        reachable = probe_fn(emit_host, endpoint.port, timeout=timeout) is not None
        if not reachable:
            notes.append(
                f"Warning: {emit_host}:{endpoint.port} did not answer from here. "
                "The phone may not connect (port not published / firewall). "
                "`tinca-tag doctor` (M2) explains why."
            )

    return Detection(
        endpoint=endpoint,
        source=source,
        lan_ip=lan_ip,
        reachable=reachable,
        in_container=inside,
        notes=notes,
    )


__all__ = ["Detection", "detect", "DEFAULT_PORTS"]
