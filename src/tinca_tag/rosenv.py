"""ROS 2 environment facts for the doctor's no-bridge tree (ADR 0004, 0009).

Pure filesystem/env reads -- no subprocess, no sourcing the ROS setup -- so it stays
"read + render + advise, zero side effects." Bridges are laid down by apt under
``/opt/ros/<distro>/share/<pkg>``, which is exactly what we look for.
"""

from __future__ import annotations

import os
from pathlib import Path

ROS_ROOT = Path("/opt/ros")

# Preference order: foxglove first (the website card marks it "Recommended -- lowest
# latency"; rosbridge is "Supported"). The no-bridge tree recommends the first of these.
BRIDGE_PACKAGES = ("foxglove_bridge", "rosbridge_server")


def ros_distro() -> str | None:
    """The active ROS 2 distro (``$ROS_DISTRO``, else the newest under ``/opt/ros``)."""
    env = os.environ.get("ROS_DISTRO")
    if env:
        return env
    try:
        distros = sorted(p.name for p in ROS_ROOT.iterdir() if p.is_dir())
    except OSError:
        return None
    return distros[-1] if distros else None


def installed_bridges(distro: str | None) -> list[str]:
    """Bridge packages present on disk for ``distro``, foxglove first."""
    if not distro:
        return []
    share = ROS_ROOT / distro / "share"
    return [pkg for pkg in BRIDGE_PACKAGES if (share / pkg).is_dir()]
