"""CP-C harness: run real ROS 2 bridge containers and assert detection matches.

Heavy and Docker-dependent, so this suite is marked ``integration`` and excluded from the
default `pytest` run (see pyproject ``addopts``). Run it explicitly:

    pytest -m integration

It is skipped (not failed) when Docker is unavailable, so it never blocks the unit suite.
The fixture image (tests/integration/Dockerfile) bundles foxglove_bridge, rosbridge_suite,
and a self-signed cert; each scenario launches it differently.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import pytest

from tinca_tag.detect import ws

IMAGE = "tinca-tag-cpc:latest"
_DOCKERFILE_DIR = Path(__file__).parent


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=15)
    return result.returncode == 0


def _run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, **kwargs)


@pytest.fixture(scope="session")
def docker():
    if not _docker_available():
        pytest.skip("Docker is not available")
    return True


@pytest.fixture(scope="session")
def cpc_image(docker):
    """Build the fixture image once per session (a no-op if already built/cached)."""
    build = _run(["build", "-t", IMAGE, str(_DOCKERFILE_DIR)], timeout=1800)
    if build.returncode != 0:
        pytest.fail(f"failed to build {IMAGE}:\n{build.stderr[-2000:]}")
    return IMAGE


class BridgeContainer:
    """A running bridge container, published to a host port we can probe."""

    def __init__(self, container_port: int, command: list[str]):
        self.container_port = container_port
        publish = f"127.0.0.1::{container_port}/tcp"
        run = _run(["run", "-d", "--rm", "-p", publish, IMAGE, *command], timeout=60)
        if run.returncode != 0:
            raise RuntimeError(f"docker run failed:\n{run.stderr}")
        self.id = run.stdout.strip()
        self.host_port = self._published_port()

    def _published_port(self) -> int:
        out = _run(["port", self.id, f"{self.container_port}/tcp"], timeout=15)
        # e.g. "127.0.0.1:54321"
        return int(out.stdout.strip().splitlines()[0].rsplit(":", 1)[1])

    def wait_ready(self, *, timeout: float = 45.0) -> ws.ProbeResult:
        """Poll until the bridge answers the WS probe, or fail with logs."""
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            last = ws.probe("127.0.0.1", self.host_port, timeout=1.0)
            if last is not None:
                return last
            time.sleep(1.0)
        logs = _run(["logs", self.id], timeout=15).stdout[-2000:]
        raise AssertionError(
            f"bridge on container port {self.container_port} never became reachable.\nlogs:\n{logs}"
        )

    def close(self):
        _run(["rm", "-f", self.id], timeout=30)


@pytest.fixture
def bridge(cpc_image):
    """Factory: start a bridge container, auto-removed at test end."""
    started: list[BridgeContainer] = []

    def _start(container_port: int, command: list[str]) -> BridgeContainer:
        container = BridgeContainer(container_port, command)
        started.append(container)
        return container

    yield _start
    for container in started:
        container.close()
