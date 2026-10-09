"""CP-D: doctor's vantage-sensitive modes against a real ROS 2 container (ADR 0009).

The pure decision tree is covered by unit tests (test_diagnose). CP-D exercises only what
containers uniquely prove: the fact-gatherers (rosenv / sockets / container) and the
in-container vantage, run *inside* a real ROS install. detect()+diagnose() are stdlib-only
(no segno), so we mount the source read-only and `docker exec` them -- the image (which
already ships Python 3 and both bridges, see Dockerfile) needs no rebuild.

Two modes:
- port-not-published: a bridge runs but its port is unpublished; from *inside* the
  container doctor finds it, flags the vantage, and prints the publish guidance.
- installed-but-not-running: the bridges are installed but none is launched; doctor reports
  exactly that and prints the launch command.

Run with: pytest -m integration   (needs Docker; self-skips without it)
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

IMAGE = "tinca-tag-cpc:latest"
SRC = (Path(__file__).parents[2] / "src").resolve()

# Run detect()+diagnose() and dump each check as "status|name|detail|remediation", exiting
# with the diagnosis's exit code. Stdlib-only import path: no segno, no install needed.
_PROBE = (
    "import sys\n"
    "from tinca_tag.detect import detect\n"
    "from tinca_tag.diagnose import diagnose\n"
    "g = diagnose(detect(timeout=2.0))\n"
    "print('\\n'.join(c.status + '|' + c.name + '|' + c.detail + '|' + ' ;; '.join(c.remediation)"
    " for c in g.checks))\n"
    "sys.exit(g.exit_code)"
)


def _docker(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, **kwargs)


class ExecContainer:
    """A container we run diagnose() *inside* via `docker exec` (source mounted at /pkg)."""

    def __init__(self, command: list[str]):
        run = _docker(["run", "-d", "--rm", "-v", f"{SRC}:/pkg:ro", IMAGE, *command], timeout=60)
        if run.returncode != 0:
            raise RuntimeError(f"docker run failed:\n{run.stderr}")
        self.id = run.stdout.strip()

    def probe(self, timeout: float = 30.0) -> subprocess.CompletedProcess:
        return _docker(
            ["exec", "-e", "PYTHONPATH=/pkg", self.id, "python3", "-c", _PROBE], timeout=timeout
        )

    def wait_bridge(self, port: int, *, timeout: float = 90.0) -> None:
        check = (
            "import socket,sys\n"
            f"try: socket.create_connection(('127.0.0.1',{port}),1).close()\n"
            "except OSError: sys.exit(1)"
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if _docker(["exec", self.id, "python3", "-c", check], timeout=15).returncode == 0:
                return
            time.sleep(1.0)
        logs = _docker(["logs", self.id], timeout=15).stdout[-2000:]
        raise AssertionError(f"bridge never came up inside the container:\nlogs:\n{logs}")

    def close(self) -> None:
        _docker(["rm", "-f", self.id], timeout=30)


@pytest.fixture
def exec_container(cpc_image):
    """Factory: start a container (source mounted), auto-removed at test end."""
    started: list[ExecContainer] = []

    def _start(command: list[str]) -> ExecContainer:
        container = ExecContainer(command)
        started.append(container)
        return container

    yield _start
    for container in started:
        container.close()


def test_port_not_published_flags_vantage_from_inside(exec_container):
    # Bridge running, port NOT published (no -p). From inside, doctor finds it but must
    # flag the container vantage and print the publish guidance -- a warn, not a fail.
    container = exec_container(
        ["ros2", "launch", "foxglove_bridge", "foxglove_bridge_launch.xml", "port:=8765"]
    )
    container.wait_bridge(8765)
    result = container.probe()
    report = result.stdout
    assert "container" in report.lower()
    assert 'ports: ["8765:8765"]' in report or "network_mode: host" in report
    assert result.returncode == 0  # in-container reachability is a warn, not a fail


def test_installed_but_not_running_names_the_layer(exec_container):
    # Bridges installed in the image but none launched. doctor must say exactly that and
    # print the launch command -- proving rosenv sees the real /opt/ros install.
    container = exec_container(["sleep", "infinity"])
    result = container.probe()
    report = result.stdout
    assert "installed but not running" in report
    assert "ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765" in report
    assert result.returncode == 1
