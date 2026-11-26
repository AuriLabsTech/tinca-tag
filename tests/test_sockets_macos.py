"""macOS listening-socket enumeration via nettop.

`/proc` does not exist on macOS, so rung 2 parses `nettop -L 1 -m tcp -n -J state`.
netstat was used first, but on macOS 27.2.1 it prints nothing when spawned by an
ad-hoc-signed Python (Homebrew, conda, uv), while nettop still lists every listener.
These tests pin the parse and the platform dispatch without running nettop; the fixture
rows are copied from a real macOS 27.2.1 run unless marked otherwise.
"""

import subprocess

import pytest

from tinca_tag.detect import sockets

NETTOP_OUTPUT = (
    ",state,\n"
    "launchd.1,,\n"
    "tcp4 127.0.0.1:8021<->*:*,Listen,\n"
    "tcp6 ::1.8021<->*.*,Listen,\n"
    "zerotier-one.879,,\n"
    "tcp4 *:9993<->*:*,Listen,\n"
    "tcp4 127.0.0.1:9993<->127.0.0.1:52893,Established,\n"
    "com.docker.backend.85209,,\n"
    "tcp6 *.8766<->*.*,Listen,\n"
    "tcp6 *.9090<->*.*,Listen,\n"
    "tcp4 127.0.0.1:8765<->*:*,Listen,\n"
    "tcp4 10.125.181.96:51486<->17.57.146.55:5223,Established,\n"
)


@pytest.fixture
def macos(monkeypatch, tmp_path):
    """A host without /proc that reports darwin, with nettop output injected."""
    monkeypatch.setattr(sockets, "PROC_NET_TCP", tmp_path / "no-proc" / "tcp")
    monkeypatch.setattr(sockets, "_PLATFORM", "darwin")
    monkeypatch.setattr(sockets, "_run_nettop", lambda: NETTOP_OUTPUT)


# --- parse ---------------------------------------------------------------------


def test_parse_nettop_keeps_listen_rows_only():
    socks = sockets.parse_nettop(NETTOP_OUTPUT)
    assert sorted(s.port for s in socks) == [8021, 8021, 8765, 8766, 9090, 9993]


def test_parse_nettop_classifies_loopback():
    socks = sockets.parse_nettop(NETTOP_OUTPUT)
    by = {(s.port, s.ipv6): s for s in socks}
    assert by[(8766, True)].loopback_only is False  # *.8766, all interfaces
    assert by[(9993, False)].loopback_only is False  # *:9993
    assert by[(8765, False)].loopback_only is True  # 127.0.0.1
    assert by[(8021, True)].loopback_only is True  # ::1


def test_parse_nettop_reads_a_lan_address():
    row = "tcp4 192.168.1.20:3001<->*:*,Listen,\n"
    (sock,) = sockets.parse_nettop(row)
    assert (sock.port, sock.loopback_only, sock.ipv6) == (3001, False, False)


def test_parse_nettop_scoped_loopback_is_loopback():
    # Constructed row (no scoped listener in the capture): fe80::1 scoped to lo0.
    row = "tcp6 fe80::1%lo0.631<->*.*,Listen,\n"
    assert sockets.parse_nettop(row)[0].loopback_only is True


def test_parse_nettop_ipv4_mapped_loopback_is_loopback():
    # ipaddress calls ::ffff:127.0.0.1 not-loopback before Python 3.13.
    row = "tcp6 ::ffff:127.0.0.1.8766<->*.*,Listen,\n"
    assert sockets.parse_nettop(row)[0].loopback_only is True


def test_parse_nettop_tolerates_garbage():
    assert sockets.parse_nettop("") == []
    assert sockets.parse_nettop("tcp4 nonsense,Listen,\n") == []
    assert sockets.parse_nettop("tcp4 127.0.0.1:http<->*:*,Listen,\n") == []
    assert sockets.parse_nettop("udp4 *:5353<->*:*,Listen,\n") == []


def test_proc_branch_runs_when_only_tcp6_exists(monkeypatch, tmp_path):
    proc = tmp_path / "net"
    proc.mkdir()
    (proc / "tcp6").write_text(
        "  sl  local_address\n"
        "   0: 00000000000000000000000000000000:223E"
        " 00000000000000000000000000000000:0000 0A 0 0 0 0 0 0\n"
    )
    monkeypatch.setattr(sockets, "PROC_NET_TCP", proc / "tcp")
    monkeypatch.setattr(sockets, "_PLATFORM", "linux")
    assert sockets.listening_ports() == [8766]
    assert sockets.enumeration_available() is True


# --- dispatch on a macOS host ------------------------------------------------------


def test_listening_ports_on_macos_finds_nonstandard_bridge(macos):
    ports = sockets.listening_ports()
    assert 8766 in ports
    assert 8765 not in ports  # loopback-only: a phone cannot reach it


def test_bind_status_on_macos(macos):
    assert sockets.bind_status(8766) == "exposed"
    assert sockets.bind_status(8765) == "loopback"
    assert sockets.bind_status(4242) == "absent"


def test_enumeration_available_on_macos(macos):
    assert sockets.enumeration_available() is True


def test_enumeration_unavailable_when_nettop_fails_at_runtime(monkeypatch, tmp_path):
    # qr's and doctor's "could not list ports" warning keys on this: a failed scan must
    # not count as a scan that found nothing.
    monkeypatch.setattr(sockets, "PROC_NET_TCP", tmp_path / "no-proc" / "tcp")
    monkeypatch.setattr(sockets, "_PLATFORM", "darwin")
    monkeypatch.setattr(sockets, "_run_nettop", lambda: None)
    assert sockets.enumeration_available() is False
    assert sockets.listening_ports() == []
    assert sockets.bind_status(8766) == "absent"


def test_other_platforms_without_proc_enumerate_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(sockets, "PROC_NET_TCP", tmp_path / "no-proc" / "tcp")
    monkeypatch.setattr(sockets, "_PLATFORM", "win32")
    monkeypatch.setattr(sockets, "_run_nettop", lambda: NETTOP_OUTPUT)
    assert sockets.listening_ports() == []
    assert sockets.enumeration_available() is False


# --- running nettop ---------------------------------------------------------------


@pytest.mark.parametrize(
    "failure",
    [
        FileNotFoundError("no nettop"),
        subprocess.TimeoutExpired(cmd="nettop", timeout=5),
        PermissionError("denied"),
    ],
)
def test_run_nettop_failure_returns_none(monkeypatch, failure):
    def boom(*args, **kwargs):
        raise failure

    monkeypatch.setattr(sockets.subprocess, "run", boom)
    assert sockets._run_nettop() is None


def test_run_nettop_nonzero_exit_returns_none(monkeypatch):
    def failed(*args, **kwargs):
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="err")

    monkeypatch.setattr(sockets.subprocess, "run", failed)
    assert sockets._run_nettop() is None


@pytest.mark.parametrize(
    "stdout",
    [
        "",  # what netstat printed on macOS 27.2.1 under an ad-hoc-signed Python
        ",state,\nlaunchd.1,,\n",  # processes but no listener: a filtered or changed list
        "tcp4 10.0.0.2:51486<->17.57.146.55:5223,Established,\n",
    ],
)
def test_run_nettop_without_listeners_returns_none(monkeypatch, stdout):
    """A Mac always has system listeners, so none at all means the scan did not work."""

    def blank(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(sockets.subprocess, "run", blank)
    assert sockets._run_nettop() is None


def test_run_nettop_survives_a_process_name_that_is_not_utf8(monkeypatch):
    # nettop prints process names (netstat never did); one in another encoding must not
    # crash qr with a UnicodeDecodeError. A real child process writes the raw bytes.
    import sys

    script = "import sys; sys.stdout.buffer.write(b'caf\\xe9.42,,\\ntcp6 *.8766<->*.*,Listen,\\n')"
    monkeypatch.setattr(sockets, "NETTOP", sys.executable)
    monkeypatch.setattr(sockets, "_NETTOP_ARGS", ["-c", script])
    text = sockets._run_nettop()
    assert text is not None
    assert [s.port for s in sockets.parse_nettop(text)] == [8766]


def test_run_nettop_uses_fixed_readonly_command(monkeypatch):
    seen = {}

    def ok(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(cmd, returncode=0, stdout=NETTOP_OUTPUT, stderr="")

    monkeypatch.setattr(sockets.subprocess, "run", ok)
    assert sockets._run_nettop() == NETTOP_OUTPUT
    assert seen["cmd"] == [sockets.NETTOP, "-L", "1", "-m", "tcp", "-n", "-J", "state"]
    assert seen["kwargs"].get("timeout")
    assert seen["kwargs"].get("shell", False) is False
