"""CP-C: detection against real ROS 2 bridge containers.

Asserts that what tinca-tag detects (protocol, secure, port) matches each container's
actual config -- the gate that caught real foxglove_bridge negotiating foxglove.sdk.v1
rather than the classic foxglove.websocket.v1. Covers rosbridge + foxglove, default +
nonstandard port, and plain + TLS.

Run with: pytest -m integration   (needs Docker; the suite self-skips without it)
"""

from __future__ import annotations

import pytest

from tinca_tag.detect import detect
from tinca_tag.render import connect_url

pytestmark = pytest.mark.integration

# Each scenario: a label, the container port, the launch argv, and the config we expect
# detection to report back.
SCENARIOS = [
    {
        "id": "rosbridge-plain",
        "port": 9090,
        "cmd": [
            "ros2",
            "launch",
            "rosbridge_server",
            "rosbridge_websocket_launch.xml",
            "port:=9090",
        ],
        "protocol": "rosbridge",
        "secure": False,
    },
    {
        "id": "foxglove-plain",
        "port": 8765,
        "cmd": ["ros2", "launch", "foxglove_bridge", "foxglove_bridge_launch.xml", "port:=8765"],
        "protocol": "foxglove-ws",
        "secure": False,
    },
    {
        "id": "foxglove-nonstandard-port",
        "port": 9999,
        "cmd": ["ros2", "launch", "foxglove_bridge", "foxglove_bridge_launch.xml", "port:=9999"],
        "protocol": "foxglove-ws",
        "secure": False,
    },
    {
        "id": "foxglove-tls",
        "port": 8765,
        "cmd": [
            "ros2",
            "launch",
            "foxglove_bridge",
            "foxglove_bridge_launch.xml",
            "port:=8765",
            "tls:=true",
            "certfile:=/certs/cert.pem",
            "keyfile:=/certs/key.pem",
        ],
        "protocol": "foxglove-ws",
        "secure": True,
    },
    {
        "id": "rosbridge-tls",
        "port": 9090,
        "cmd": [
            "ros2",
            "launch",
            "rosbridge_server",
            "rosbridge_websocket_launch.xml",
            "port:=9090",
            "ssl:=true",
            "certfile:=/certs/cert.pem",
            "keyfile:=/certs/key.pem",
        ],
        "protocol": "rosbridge",
        "secure": True,
    },
]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_detection_matches_real_bridge(bridge, scenario):
    container = bridge(scenario["port"], scenario["cmd"])
    container.wait_ready(timeout=60.0)

    # Probe the bridge the way the CLI does, via its published host port.
    det = detect(host="127.0.0.1", port=container.host_port, timeout=2.0)

    assert det.ok, det.notes
    assert det.endpoint.protocol == scenario["protocol"]
    assert det.endpoint.secure is scenario["secure"]
    assert det.endpoint.port == container.host_port
    assert det.reachable is True

    # The endpoint renders to a valid contract URL.
    url = connect_url(det.endpoint)
    assert url.startswith("tinca://connect?host=127.0.0.1")
    assert f"protocol={scenario['protocol']}" in url
    assert f"secure={1 if scenario['secure'] else 0}" in url
