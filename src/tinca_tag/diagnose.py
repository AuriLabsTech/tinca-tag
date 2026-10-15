"""The diagnostic tree behind ``tinca-tag doctor`` (ADR 0009).

Builds on ``detect()``: takes its :class:`~tinca_tag.detect.Detection` plus injected
fact-gatherers (bind status, proc availability, listening count, ROS env, installed
bridges) and returns a pure :class:`Diagnosis` -- an ordered list of typed
:class:`Check`s with an overall pass/fail exit code. All logic is stdlib and pure, so
every branch is unit-testable; CP-D covers the two container-only modes.

Remediation copy mirrors the Tinca "Troubleshooting connection" card (the single source
of truth) so the two cannot drift; see ADR 0004/0007/0009.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from . import rosenv
from .detect import _MAX_NONDEFAULT_PORTS as SCAN_CAP
from .detect import DEFAULT_PORTS, Detection, sockets

Status = Literal["ok", "warn", "fail", "skip"]

# protocol (contract value) -> the launch package that speaks it.
_PROTOCOL_PACKAGE = {"foxglove-ws": "foxglove_bridge", "rosbridge": "rosbridge_server"}
# package -> (launch package, launch file, default port). Used to print launch commands.
_LAUNCH = {
    "foxglove_bridge": ("foxglove_bridge", "foxglove_bridge_launch.xml", 8765),
    "rosbridge_server": ("rosbridge_server", "rosbridge_websocket_launch.xml", 9090),
}
# package -> launch args appended to every printed launch command, so actions work.
# foxglove_bridge advertises no action endpoint (`_action/...`) unless include_hidden is
# true (measured by the Tinca lab, 2026-10-11). rosbridge 2.0.8 (Humble) defaults both
# thread args to false, so a cancel or service call waits behind a running action goal
# (measured by ros-mobile-bridge, 2026-10-14); later distros default to true.
_EXTRA_ARGS = {
    "foxglove_bridge": "include_hidden:=true",
    "rosbridge_server": "send_action_goals_in_new_thread:=true call_services_in_new_thread:=true",
}


@dataclass(frozen=True)
class Check:
    """One diagnostic layer's verdict and, when it failed, how to fix it."""

    name: str
    status: Status
    detail: str
    remediation: tuple[str, ...] = ()


@dataclass
class Diagnosis:
    """The ordered checks for one ``doctor`` run, plus the detection they build on."""

    checks: list[Check]
    detection: Detection

    @property
    def healthy(self) -> bool:
        return all(check.status != "fail" for check in self.checks)

    @property
    def exit_code(self) -> int:
        # A warn (e.g. an unverifiable in-container run) stays 0; only a fail fails.
        return 0 if self.healthy else 1


def _launch_cmd(package: str, port: int | None = None, address: str | None = None) -> str:
    name, launch_file, default_port = _LAUNCH[package]
    args = [f"address:={address}"] if address else []
    args.append(f"port:={port if port is not None else default_port}")
    if package in _EXTRA_ARGS:
        args.append(_EXTRA_ARGS[package])
    return f"ros2 launch {name} {launch_file} " + " ".join(args)


def _bind_fix(protocol: str, port: int) -> tuple[str, ...]:
    return (
        "The bridge is bound to loopback (127.0.0.1) only. Relaunch it on all interfaces:",
        "  " + _launch_cmd(_PROTOCOL_PACKAGE[protocol], port, address="0.0.0.0"),
    )


def _firewall_fix(port: int) -> tuple[str, ...]:
    return (
        "Open the port if a host firewall is active:",
        f"  sudo ufw allow {port}",
        f"Verify from the host:  curl http://localhost:{port}/",
        "Then use the host's LAN IP (hostname -I) in Tinca, not localhost.",
    )


def _publish_fix(port: int) -> tuple[str, ...]:
    return (
        "If the bridge runs in a container, publish its port to the host:",
        f'  docker-compose.yml:  ports: ["{port}:{port}"]   (or network_mode: host)',
        f"  docker ps should then show 0.0.0.0:{port}->{port}/tcp",
    )


def _default_listening_count() -> int:
    return len([p for p in sockets.listening_ports() if p not in DEFAULT_PORTS])


def _reachability_check(endpoint, bind_status_fn) -> Check:
    """On-host: name the single confident cause from the bind-address signal (ADR 0009)."""
    status = bind_status_fn(endpoint.port)
    if status == "loopback":
        return Check(
            "reachable",
            "fail",
            "listening on loopback (127.0.0.1) only, so the phone can't reach it",
            _bind_fix(endpoint.protocol, endpoint.port),
        )
    if status == "exposed":
        return Check(
            "reachable",
            "fail",
            "reachable on this host but not from the LAN, so the firewall is blocking it",
            _firewall_fix(endpoint.port),
        )
    # "absent": nothing listening here (rare on-host); show both candidate layers.
    return Check(
        "reachable",
        "fail",
        f"{endpoint.host}:{endpoint.port} did not answer from here",
        _publish_fix(endpoint.port) + _firewall_fix(endpoint.port),
    )


def _found_checks(detection, bind_status_fn) -> list[Check]:
    endpoint = detection.endpoint
    checks = [Check("bridge", "ok", f"{endpoint.protocol} at {endpoint.host}:{endpoint.port}")]

    if detection.in_container:
        checks.append(
            Check(
                "vantage",
                "warn",
                "inside a container; the phone reaches the host, not here",
                (
                    "Run tinca-tag doctor on the host (not in the container) to verify "
                    "the phone can reach the bridge.",
                ),
            )
        )
        checks.append(
            Check(
                "reachable",
                "warn",
                "cannot verify phone reachability from inside the container",
                _publish_fix(endpoint.port),
            )
        )
        return checks

    checks.append(Check("vantage", "ok", "on host"))
    if detection.reachable is True:
        checks.append(Check("reachable", "ok", f"{endpoint.host}:{endpoint.port} answered"))
    elif detection.reachable is None:
        checks.append(Check("reachable", "warn", "reachability not checked"))
    else:
        checks.append(_reachability_check(endpoint, bind_status_fn))
    return checks


def _scan_hint(host, port, proc_available_fn, listening_count_fn) -> str | None:
    """Only surface --port when we genuinely could not auto-scan (ADR 0009 / Q6)."""
    if port is not None:
        return None
    if host is not None:
        return (
            "Note: can't scan a remote host's ports from here. If its bridge uses a "
            "nonstandard port, pass --port <port> --protocol rosbridge|foxglove-ws."
        )
    if not proc_available_fn():
        return (
            "Note: couldn't enumerate ports on this OS; only 9090 and 8765 were probed. "
            "Pass --port <port> for a nonstandard bridge."
        )
    if listening_count_fn() > SCAN_CAP:
        return (
            f"Note: probed the defaults and the first {SCAN_CAP} listening ports; if your "
            "bridge is beyond that, pass --port <port>."
        )
    return None


def _missing_check(
    host, port, proc_available_fn, listening_count_fn, ros_distro_fn, bridge_installed_fn
) -> Check:
    distro = ros_distro_fn()
    installed = bridge_installed_fn(distro) if distro else []
    remediation: list[str] = []

    if distro and installed:
        detail = f"ROS 2 {distro} detected; {', '.join(installed)} installed but not running"
        remediation.append("Start the bridge:")
        remediation.extend("  " + _launch_cmd(pkg) for pkg in installed)
    elif distro and not installed:
        detail = f"ROS 2 {distro} detected; no bridge installed"
        remediation.extend(
            [
                "Install and launch a bridge (foxglove recommended):",
                f"  sudo apt install ros-{distro}-foxglove-bridge",
                "  " + _launch_cmd("foxglove_bridge"),
                "or rosbridge:",
                f"  sudo apt install ros-{distro}-rosbridge-suite",
                "  " + _launch_cmd("rosbridge_server"),
            ]
        )
    else:
        detail = "ROS 2 not detected on this host"
        remediation.extend(
            [
                "Install ROS 2 and a bridge, then re-run. See:",
                "  https://docs.ros.org/en/rolling/Installation.html",
                "  https://aurilabs.tech/tinca/docs  (Troubleshooting connection)",
            ]
        )

    # An unpublished container port is invisible from the host, so "no bridge here" is
    # often a containerized bridge that never reached the LAN (card step 2 / ADR 0009).
    remediation.append(
        "If the bridge runs in a container, publish its port to the host (ports: "
        '["8765:8765"] / ["9090:9090"]) or use network_mode: host; an unpublished port '
        "is invisible from here."
    )

    hint = _scan_hint(host, port, proc_available_fn, listening_count_fn)
    if hint:
        remediation.append(hint)
    return Check("bridge", "fail", detail, tuple(remediation))


def diagnose(
    detection: Detection,
    *,
    host: str | None = None,
    port: int | None = None,
    bind_status_fn=sockets.bind_status,
    proc_available_fn=sockets.proc_available,
    listening_count_fn=None,
    ros_distro_fn=rosenv.ros_distro,
    bridge_installed_fn=rosenv.installed_bridges,
) -> Diagnosis:
    """Diagnose a bridge setup from a :class:`Detection`, per ADR 0009."""
    if listening_count_fn is None:
        listening_count_fn = _default_listening_count

    if detection.ok:
        checks = _found_checks(detection, bind_status_fn)
    else:
        checks = [
            _missing_check(
                host,
                port,
                proc_available_fn,
                listening_count_fn,
                ros_distro_fn,
                bridge_installed_fn,
            )
        ]
    return Diagnosis(checks=checks, detection=detection)


__all__ = ["Check", "Diagnosis", "diagnose", "Status"]
