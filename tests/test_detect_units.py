"""Unit tests for the pure detection logic (no sockets, no /proc needed).

The socket I/O (probe) and live /proc reads are exercised by the containerized
integration suite (CP-C); here we pin the parsing/classification that decides
protocol, secure, and candidate ports.
"""

import pytest

from tinca_tag.detect import container, lan, sockets, ws

# --- ws handshake: build / parse / classify (ADR 0003) ---------------------------


def test_build_handshake_offers_all_foxglove_subprotocols():
    req = ws.build_handshake("192.168.1.50", 8765, "abc123==").decode()
    assert req.startswith("GET / HTTP/1.1\r\n")
    # both tokens are offered so we detect classic and SDK-era foxglove_bridge
    assert "Sec-WebSocket-Protocol: foxglove.sdk.v1, foxglove.websocket.v1\r\n" in req
    assert "Host: 192.168.1.50:8765\r\n" in req
    assert req.endswith("\r\n\r\n")


def test_build_handshake_can_omit_foxglove_offer():
    req = ws.build_handshake("h", 1, "k", offer_foxglove=False).decode()
    assert "Sec-WebSocket-Protocol" not in req


def _foxglove_101(token: str) -> bytes:
    return (
        b"HTTP/1.1 101 Switching Protocols\r\n"
        b"Upgrade: websocket\r\nConnection: Upgrade\r\n"
        b"Sec-WebSocket-Accept: x\r\n"
        b"Sec-WebSocket-Protocol: " + token.encode() + b"\r\n\r\n"
    )


ROSBRIDGE_101 = (
    b"HTTP/1.1 101 Switching Protocols\r\n"
    b"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: x\r\n\r\n"
)
PLAIN_HTTP = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n<html>"


@pytest.mark.parametrize("token", ["foxglove.sdk.v1", "foxglove.websocket.v1"])
def test_classify_foxglove_for_either_token(token):
    assert ws.classify(ws.parse_handshake(_foxglove_101(token))) == "foxglove-ws"


def test_classify_rosbridge_is_101_without_subprotocol():
    assert ws.classify(ws.parse_handshake(ROSBRIDGE_101)) == "rosbridge"


def test_classify_non_ws_server_is_not_a_bridge():
    assert ws.classify(ws.parse_handshake(PLAIN_HTTP)) is None


def test_classify_garbage_is_not_a_bridge():
    assert ws.classify(ws.parse_handshake(b"\x16\x03\x01 not http")) is None


def test_new_ws_key_is_16_bytes_base64():
    import base64

    key = ws.new_ws_key()
    assert len(base64.b64decode(key)) == 16


# --- /proc/net/tcp parsing (ADR 0003 rung 2) -------------------------------------

# port 9090 = 0x2382 bound to 0.0.0.0 (LISTEN), port 8765 = 0x223D bound to 127.0.0.1,
# plus an ESTABLISHED row (state 01) that must be ignored.
PROC_NET_TCP = (
    "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt\n"
    "   0: 00000000:2382 00000000:0000 0A 00000000:00000000 00:00000000 00000000\n"
    "   1: 0100007F:223D 00000000:0000 0A 00000000:00000000 00:00000000 00000000\n"
    "   2: 00000000:1F90 0A2A0AC0:D903 01 00000000:00000000 00:00000000 00000000\n"
)


def test_parse_proc_net_tcp_finds_listen_only():
    socks = sockets.parse_proc_net_tcp(PROC_NET_TCP)
    by_port = {s.port: s for s in socks}
    assert set(by_port) == {0x2382, 0x223D}  # the ESTABLISHED row is excluded
    assert by_port[0x2382].loopback_only is False  # 0.0.0.0
    assert by_port[0x223D].loopback_only is True  # 127.0.0.1


def test_parse_proc_net_tcp_hex_ports_decode():
    socks = sockets.parse_proc_net_tcp(PROC_NET_TCP)
    assert {s.port for s in socks} == {9090, 8765}


def test_ipv6_loopback_detection():
    line = (
        "  sl  local_address\n"
        "   0: 00000000000000000000000001000000:2382"
        " 00000000000000000000000000000000:0000 0A 0 0 0 0 0 0\n"
    )
    socks = sockets.parse_proc_net_tcp(line, ipv6=True)
    assert socks[0].loopback_only is True


# --- container vantage (ADR 0007) ------------------------------------------------


def test_cgroup_detects_docker():
    assert container.cgroup_indicates_container("12:devices:/docker/abc123") is True


def test_cgroup_detects_kubepods():
    assert container.cgroup_indicates_container("0::/kubepods/pod123") is True


def test_cgroup_plain_host_is_false():
    assert container.cgroup_indicates_container("0::/init.scope") is False


# --- LAN helpers (ADR 0006) ------------------------------------------------------


def test_mdns_host_strips_domain_and_appends_local():
    assert lan.mdns_host().endswith(".local")
    assert lan.mdns_host().count(".") == 1  # bare hostname + .local


def test_primary_lan_ip_is_none_or_non_loopback():
    ip = lan.primary_lan_ip()
    assert ip is None or not ip.startswith("127.")
