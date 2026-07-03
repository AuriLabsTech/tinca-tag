"""detect() orchestration: rung precedence, overrides, LAN host, reachability.

I/O is injected (probe / lan-ip / listening-ports / container) so these run with no
network. CP-C covers the same paths against real bridge containers.
"""

from tinca_tag.detect import detect
from tinca_tag.detect.ws import ProbeResult

FOX = ProbeResult(protocol="foxglove-ws", secure=False)
ROS = ProbeResult(protocol="rosbridge", secure=False)
ROS_TLS = ProbeResult(protocol="rosbridge", secure=True)


class FakeProbe:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def __call__(self, host, port, timeout=1.0):
        self.calls.append((host, port))
        return self.mapping.get((host, port))


def _detect(mapping, *, lan_ip="192.168.1.50", listening=None, inside=False, **kwargs):
    return detect(
        probe_fn=FakeProbe(mapping),
        lan_ip_fn=lambda: lan_ip,
        mdns_fn=lambda: "robot.local",
        ports_fn=lambda: list(listening or []),
        in_container_fn=lambda: inside,
        **kwargs,
    )


def test_detects_foxglove_on_default_port_and_emits_lan_ip():
    det = _detect({("127.0.0.1", 8765): FOX, ("192.168.1.50", 8765): FOX})
    assert det.ok
    assert det.endpoint.host == "192.168.1.50"
    assert det.endpoint.port == 8765
    assert det.endpoint.protocol == "foxglove-ws"
    assert det.endpoint.secure is False
    assert det.reachable is True
    assert "probe" in det.source


def test_detects_rosbridge_default_port():
    det = _detect({("127.0.0.1", 9090): ROS, ("192.168.1.50", 9090): ROS})
    assert det.endpoint.protocol == "rosbridge"
    assert det.endpoint.port == 9090


def test_nonstandard_port_via_listening_enumeration():
    det = _detect(
        {("127.0.0.1", 9999): FOX, ("192.168.1.50", 9999): FOX},
        listening=[9999],
    )
    assert det.ok
    assert det.endpoint.port == 9999
    assert det.endpoint.protocol == "foxglove-ws"


def test_full_flags_skip_identification_probe():
    probe = FakeProbe({("10.0.0.9", 7000): ROS})  # only reachability is probed
    det = detect(
        host="10.0.0.9",
        port=7000,
        protocol="rosbridge",
        secure=True,
        probe_fn=probe,
        lan_ip_fn=lambda: "192.168.1.50",
        mdns_fn=lambda: "x.local",
        ports_fn=lambda: [],
        in_container_fn=lambda: False,
    )
    assert det.source == "flags"
    assert det.endpoint == _endpoint("10.0.0.9", 7000, "rosbridge", True)
    # only the reachability probe ran, no 9090/8765 identification probes
    assert probe.calls == [("10.0.0.9", 7000)]


def test_secure_flag_overrides_probe():
    # probe reports plaintext, but the user forced --secure
    det = _detect(
        {("127.0.0.1", 9090): ROS, ("192.168.1.50", 9090): ROS},
        secure=True,
    )
    assert det.endpoint.secure is True


def test_no_bridge_anywhere_returns_guidance():
    det = _detect({})
    assert not det.ok
    assert det.source == "none"
    assert any("No ROS 2 bridge detected" in n for n in det.notes)


def test_no_lan_ip_without_host_fails_with_hint():
    det = _detect(
        {("127.0.0.1", 9090): ROS},
        lan_ip=None,
    )
    assert not det.ok
    assert any("LAN IP" in n for n in det.notes)


def test_inside_container_emits_host_flag_and_warns():
    det = _detect(
        {("127.0.0.1", 8765): FOX},
        inside=True,
        host="robot-1.lan",
    )
    assert det.ok
    assert det.endpoint.host == "robot-1.lan"
    assert det.reachable is None  # not verifiable from inside
    assert any("container" in n.lower() for n in det.notes)


def test_mdns_host_skips_reachability_check():
    det = _detect({("127.0.0.1", 9090): ROS}, mdns=True)
    assert det.endpoint.host == "robot.local"
    assert det.reachable is None
    assert any(".local" in n for n in det.notes)


def test_reachability_failure_is_warned_but_still_emits():
    # bridge identified on localhost, but the LAN IP does not answer (port not published)
    det = _detect({("127.0.0.1", 8765): FOX})  # no ("192.168.1.50", 8765) entry
    assert det.ok  # still emits a QR
    assert det.reachable is False
    assert any("did not answer" in n for n in det.notes)


def test_tls_bridge_sets_secure():
    det = _detect({("127.0.0.1", 9090): ROS_TLS, ("192.168.1.50", 9090): ROS_TLS})
    assert det.endpoint.secure is True


def _endpoint(host, port, protocol, secure):
    from tinca_tag.endpoint import Endpoint

    return Endpoint(host=host, port=port, protocol=protocol, secure=secure)
