"""Live socket coverage for ws.probe() against a fake bridge on loopback.

The pure tests cover parse/classify; this covers the actual connect -> send -> recv
path. It uses a minimal thread-backed server that replies with a 101 handshake,
optionally echoing the foxglove subprotocol. Real bridges (TLS, nonstandard ports) are
covered by the containerized CP-C suite.
"""

import socket
import threading

import pytest

from tinca_tag.detect import ws


class FakeBridge:
    """Accepts one connection and returns a canned WS handshake response."""

    def __init__(self, *, subprotocol: str | None):
        # subprotocol echoed in the 101 (a foxglove token), or None for rosbridge
        self._subprotocol = subprotocol
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(1)
        self.port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        try:
            conn, _ = self._sock.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(2.0)
            try:
                conn.recv(4096)  # drain the client handshake request
            except OSError:
                return
            resp = [
                "HTTP/1.1 101 Switching Protocols",
                "Upgrade: websocket",
                "Connection: Upgrade",
                "Sec-WebSocket-Accept: dummyaccept=",
            ]
            if self._subprotocol:
                resp.append(f"Sec-WebSocket-Protocol: {self._subprotocol}")
            conn.sendall(("\r\n".join(resp) + "\r\n\r\n").encode("ascii"))

    def close(self):
        self._sock.close()


@pytest.mark.parametrize("token", list(ws.FOXGLOVE_SUBPROTOCOLS))
def test_probe_detects_foxglove(token):
    server = FakeBridge(subprotocol=token)
    try:
        result = ws.probe("127.0.0.1", server.port, timeout=2.0)
    finally:
        server.close()
    assert result is not None
    assert result.protocol == "foxglove-ws"
    assert result.secure is False


def test_probe_detects_rosbridge():
    server = FakeBridge(subprotocol=None)
    try:
        result = ws.probe("127.0.0.1", server.port, timeout=2.0)
    finally:
        server.close()
    assert result is not None
    assert result.protocol == "rosbridge"
    assert result.secure is False


def test_probe_closed_port_returns_none():
    # An ephemeral port nobody is listening on -> not a bridge.
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    assert ws.probe("127.0.0.1", port, timeout=0.5) is None
