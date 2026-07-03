"""Vantage detection: are we inside a container? (ADR 0007).

On-host is the recommended vantage for a containerized bridge: it sees the real LAN IP
and the published ports. Run inside the container, tinca-tag cannot verify host-side
reachability and must be given ``--host``; this module lets the CLI warn about that.
"""

from __future__ import annotations

from pathlib import Path

_CGROUP_TOKENS = ("docker", "kubepods", "containerd", "lxc", "podman")


def cgroup_indicates_container(text: str) -> bool:
    """Pure check: does cgroup text name a known container runtime?"""
    lowered = text.lower()
    return any(token in lowered for token in _CGROUP_TOKENS)


def in_container() -> bool:
    """Best-effort: are we running inside a container?"""
    if Path("/.dockerenv").exists():
        return True
    for path in ("/proc/1/cgroup", "/proc/self/cgroup"):
        try:
            if cgroup_indicates_container(Path(path).read_text()):
                return True
        except OSError:
            continue
    return False
