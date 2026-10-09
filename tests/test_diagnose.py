"""diagnose() decision tree: the pure logic behind `tinca-tag doctor` (ADR 0009).

Fact-gatherers are injected (bind status / proc availability / listening count / ROS
env / installed bridges), so every branch runs with no network and no containers. CP-D
covers the two container-only modes (port-not-published, installed-but-not-running).
"""

from tinca_tag.detect import Detection
from tinca_tag.diagnose import Check, Diagnosis, diagnose
from tinca_tag.endpoint import Endpoint

FOX = Endpoint(host="192.168.1.50", port=8765, protocol="foxglove-ws", secure=False)
ROS = Endpoint(host="192.168.1.50", port=9090, protocol="rosbridge", secure=False)


def _found(endpoint=FOX, *, reachable=True, in_container=False, lan_ip="192.168.1.50"):
    return Detection(
        endpoint=endpoint,
        source=f"probe (127.0.0.1:{endpoint.port})",
        lan_ip=lan_ip,
        reachable=reachable,
        in_container=in_container,
        notes=[],
    )


def _none(*, lan_ip="192.168.1.50", in_container=False):
    return Detection(
        endpoint=None,
        source="none",
        lan_ip=lan_ip,
        reachable=None,
        in_container=in_container,
        notes=[],
    )


def _diagnose(detection, **overrides):
    kwargs = dict(
        host=None,
        port=None,
        bind_status_fn=lambda port: "exposed",
        proc_available_fn=lambda: True,
        listening_count_fn=lambda: 2,
        ros_distro_fn=lambda: "humble",
        bridge_installed_fn=lambda distro: ["foxglove_bridge"],
    )
    kwargs.update(overrides)
    return diagnose(detection, **kwargs)


def _check(diag: Diagnosis, name: str) -> Check:
    for check in diag.checks:
        if check.name == name:
            return check
    raise AssertionError(f"no check named {name!r} in {[c.name for c in diag.checks]}")


def _remediation(check: Check) -> str:
    return "\n".join(check.remediation)


# --- bridge found: reachability ladder (Q5 matrix) --------------------------------


def test_reachable_on_host_is_healthy():
    diag = _diagnose(_found())
    assert _check(diag, "bridge").status == "ok"
    assert _check(diag, "vantage").status == "ok"
    assert _check(diag, "reachable").status == "ok"
    assert diag.healthy is True
    assert diag.exit_code == 0


def test_unreachable_loopback_bound_names_bind_fix():
    diag = _diagnose(_found(reachable=False), bind_status_fn=lambda port: "loopback")
    reach = _check(diag, "reachable")
    assert reach.status == "fail"
    assert "loopback" in reach.detail.lower()
    assert "0.0.0.0" in _remediation(reach)
    assert diag.exit_code == 1


def test_unreachable_exposed_bind_names_firewall():
    diag = _diagnose(_found(reachable=False), bind_status_fn=lambda port: "exposed")
    reach = _check(diag, "reachable")
    assert reach.status == "fail"
    assert "firewall" in reach.detail.lower()
    assert "ufw allow 8765" in _remediation(reach)
    assert "curl http://localhost:8765/" in _remediation(reach)
    assert diag.exit_code == 1


def test_in_container_warns_and_steers_to_host_without_failing():
    diag = _diagnose(_found(reachable=None, in_container=True))
    vantage = _check(diag, "vantage")
    assert vantage.status == "warn"
    assert "container" in vantage.detail.lower()
    assert "host" in _remediation(vantage).lower()
    # a warn does not fail the run (ADR 0009 exit semantics)
    assert _check(diag, "reachable").status == "warn"
    assert diag.exit_code == 0


# --- no bridge: ADR 0004 tree -----------------------------------------------------


def test_no_bridge_installed_not_running_prints_foxglove_launch():
    diag = _diagnose(_none(), bridge_installed_fn=lambda distro: ["foxglove_bridge"])
    bridge = _check(diag, "bridge")
    assert bridge.status == "fail"
    assert "not running" in bridge.detail.lower()
    assert "ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765" in _remediation(
        bridge
    )
    assert diag.exit_code == 1


def test_no_bridge_installed_rosbridge_prints_its_launch():
    diag = _diagnose(_none(), bridge_installed_fn=lambda distro: ["rosbridge_server"])
    bridge = _check(diag, "bridge")
    assert "ros2 launch rosbridge_server rosbridge_websocket_launch.xml port:=9090" in _remediation(
        bridge
    )


def test_no_bridge_not_installed_recommends_foxglove_apt():
    diag = _diagnose(_none(), bridge_installed_fn=lambda distro: [])
    bridge = _check(diag, "bridge")
    assert bridge.status == "fail"
    assert "no bridge installed" in bridge.detail.lower()
    rem = _remediation(bridge)
    assert "sudo apt install ros-humble-foxglove-bridge" in rem
    # foxglove is the default recommendation; rosbridge is only the alternative
    assert rem.index("foxglove") < rem.index("rosbridge")


def test_no_bridge_mentions_container_publish():
    # port-not-published surfaces here from the on-host vantage (ADR 0009 / card step 2)
    rem = _remediation(_check(_diagnose(_none()), "bridge"))
    assert "network_mode: host" in rem
    assert "unpublished port" in rem


def test_no_ros_links_docs_without_apt_wall():
    diag = _diagnose(_none(), ros_distro_fn=lambda: None, bridge_installed_fn=lambda d: [])
    bridge = _check(diag, "bridge")
    assert bridge.status == "fail"
    assert "ros 2" in bridge.detail.lower()
    rem = _remediation(bridge)
    assert "apt install" not in rem  # no install wall when ROS is absent
    assert "http" in rem  # a docs link instead


# --- no bridge: conditional false-negative hint (Q6) ------------------------------


def test_hint_absent_when_on_host_scan_found_nothing():
    diag = _diagnose(_none())  # on-host Linux, enumerated fine
    hint = _remediation(_check(diag, "bridge")) + _check(diag, "bridge").detail
    assert "--port" not in hint


def test_hint_suggests_port_for_remote_target():
    diag = _diagnose(_none(), host="10.0.0.9")
    assert any("--port" in "\n".join(c.remediation) for c in diag.checks)


def test_hint_suggests_port_on_non_linux():
    diag = _diagnose(_none(), proc_available_fn=lambda: False)
    assert any("--port" in "\n".join(c.remediation) for c in diag.checks)


def test_hint_surfaces_scan_cap_truncation():
    diag = _diagnose(_none(), listening_count_fn=lambda: 40)  # over the 25-port cap
    joined = "\n".join("\n".join(c.remediation) + c.detail for c in diag.checks)
    assert "--port" in joined
    assert "25" in joined


# --- exit-code semantics ----------------------------------------------------------


def test_exit_code_is_one_iff_any_fail():
    assert _diagnose(_found()).exit_code == 0
    assert _diagnose(_found(reachable=None, in_container=True)).exit_code == 0  # warn only
    assert _diagnose(_found(reachable=False)).exit_code == 1
    assert _diagnose(_none()).exit_code == 1
