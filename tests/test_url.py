"""CP-A: golden conformance for the deep-link URL (ADR 0001).

These pin ``Endpoint -> exact tinca:// string``, mirroring the app's ``targetFromParams``
and the sims-web emitter (``URLSearchParams`` order: host, port, secure, protocol).
A change here means the contract changed and must be coordinated across all three
consumers. Do not "fix" a fixture to match new code without that coordination.
"""

import pytest

from tinca_tag.endpoint import Endpoint
from tinca_tag.render.url import InvalidHost, connect_url, validate_host

# (endpoint, expected exact string)
GOLDEN = [
    (
        Endpoint(host="192.168.1.50", port=9090, protocol="rosbridge", secure=False),
        "tinca://connect?host=192.168.1.50&port=9090&secure=0&protocol=rosbridge",
    ),
    (
        Endpoint(host="192.168.1.50", port=8765, protocol="foxglove-ws", secure=False),
        "tinca://connect?host=192.168.1.50&port=8765&secure=0&protocol=foxglove-ws",
    ),
    (
        Endpoint(host="10.0.0.2", port=9090, protocol="rosbridge", secure=True),
        "tinca://connect?host=10.0.0.2&port=9090&secure=1&protocol=rosbridge",
    ),
    (
        Endpoint(host="robot.local", port=8765, protocol="foxglove-ws", secure=True),
        "tinca://connect?host=robot.local&port=8765&secure=1&protocol=foxglove-ws",
    ),
    (
        # nonstandard port must round-trip verbatim (detection, not default)
        Endpoint(host="192.168.1.7", port=9999, protocol="foxglove-ws", secure=False),
        "tinca://connect?host=192.168.1.7&port=9999&secure=0&protocol=foxglove-ws",
    ),
]


@pytest.mark.parametrize("endpoint,expected", GOLDEN)
def test_connect_url_golden(endpoint, expected):
    assert connect_url(endpoint) == expected


def test_name_is_additive_and_url_encoded():
    ep = Endpoint(host="192.168.1.50", port=9090, protocol="rosbridge", secure=False)
    url = connect_url(ep, name="My Robot")
    # canonical 4-param prefix is unchanged; name appended last, space -> '+'
    assert url == (
        "tinca://connect?host=192.168.1.50&port=9090&secure=0&protocol=rosbridge&name=My+Robot"
    )


@pytest.mark.parametrize(
    "bad",
    [
        "ws://192.168.1.50",
        "wss://robot.local",
        "http://host",
        "192.168.1.50:9090",
        "robot.local/",
        "has space",
        "",
    ],
)
def test_validate_host_rejects_non_bare(bad):
    with pytest.raises(InvalidHost):
        validate_host(bad)


@pytest.mark.parametrize("ok", ["192.168.1.50", "robot.local", "robot-01", "10.0.0.2"])
def test_validate_host_accepts_bare(ok):
    assert validate_host(ok) == ok
