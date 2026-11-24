"""macOS listening-socket enumeration via netstat.

`/proc` does not exist on macOS, so rung 2 parses `netstat -an -p tcp` instead. These
tests pin the parse and the platform dispatch without running netstat; the fixture rows
are copied from a real macOS run, including netstat's cut-off long IPv6 address.
"""

import subprocess

import pytest

from tinca_tag.detect import sockets

NETSTAT_OUTPUT = (
    "Active Internet connections (including servers)\n"
    "Proto Recv-Q Send-Q  Local Address          Foreign Address        (state)    \n"
    "tcp4       0      0  127.0.0.1.9993         127.0.0.1.63948        ESTABLISHED\n"
    "tcp46      0      0  *.8766                 *.*                    LISTEN     \n"
    "tcp4       0      0  127.0.0.1.8765         *.*                    LISTEN     \n"
    "tcp6       0      0  ::1.7679               *.*                    LISTEN     \n"
    "tcp6       0      0  fe80::1%lo0.631        *.*                    LISTEN     \n"
    "tcp4       0      0  192.168.1.20.3001      *.*                    LISTEN     \n"
    "tcp6       0      0  fe80::18f2:a81d:.18766 *.*                    LISTEN     \n"
    "tcp4       0      0  *.9090                 *.*                    TIME_WAIT  \n"
    "udp4       0      0  *.5353                 *.*                               \n"
)


@pytest.fixture
def macos(monkeypatch, tmp_path):
    """A host without /proc that reports darwin, with netstat output injected."""
    monkeypatch.setattr(sockets, "PROC_NET_TCP", tmp_path / "no-proc" / "tcp")
    monkeypatch.setattr(sockets, "_PLATFORM", "darwin")
    monkeypatch.setattr(sockets, "_run_netstat", lambda: NETSTAT_OUTPUT)


# --- parse ---------------------------------------------------------------------


def test_parse_netstat_keeps_tcp_listen_rows_only():
    socks = sockets.parse_netstat(NETSTAT_OUTPUT)
    assert sorted(s.port for s in socks) == [631, 3001, 7679, 8765, 8766, 18766]


def test_parse_netstat_keeps_a_cut_off_address_as_reachable():
    # netstat cuts long IPv6 addresses to fit its column, even with -W; the port is
    # still listening and is not loopback, so it must not vanish.
    by_port = {s.port: s for s in sockets.parse_netstat(NETSTAT_OUTPUT)}
    assert by_port[18766].loopback_only is False


def test_parse_netstat_classifies_loopback():
    by_port = {s.port: s for s in sockets.parse_netstat(NETSTAT_OUTPUT)}
    assert by_port[8766].loopback_only is False  # *.8766, all interfaces
    assert by_port[3001].loopback_only is False  # a LAN address
    assert by_port[8765].loopback_only is True  # 127.0.0.1
    assert by_port[7679].loopback_only is True  # ::1
    assert by_port[631].loopback_only is True  # scoped to lo0


def test_parse_netstat_marks_ipv6_rows():
    by_port = {s.port: s for s in sockets.parse_netstat(NETSTAT_OUTPUT)}
    assert by_port[7679].ipv6 is True
    assert by_port[8766].ipv6 is True  # tcp46: dual-stack, as /proc's tcp6 lists it
    assert by_port[8765].ipv6 is False


def test_parse_netstat_ipv4_mapped_loopback_is_loopback():
    # ipaddress calls ::ffff:127.0.0.1 not-loopback before Python 3.13.
    row = "tcp6       0      0  ::ffff:127.0.0.1.8766  *.*                    LISTEN\n"
    assert sockets.parse_netstat(row)[0].loopback_only is True


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


def test_parse_netstat_tolerates_garbage():
    assert sockets.parse_netstat("") == []
    assert sockets.parse_netstat("tcp4 0 0 nonsense *.* LISTEN\n") == []
    assert sockets.parse_netstat("tcp4 0 0 127.0.0.1.http *.* LISTEN\n") == []


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


def test_enumeration_unavailable_when_netstat_fails_at_runtime(monkeypatch, tmp_path):
    # The doctor's "pass --port" hint keys on this: a netstat that times out must not
    # count as a scan that found nothing.
    monkeypatch.setattr(sockets, "PROC_NET_TCP", tmp_path / "no-proc" / "tcp")
    monkeypatch.setattr(sockets, "_PLATFORM", "darwin")
    monkeypatch.setattr(sockets, "_run_netstat", lambda: None)
    assert sockets.enumeration_available() is False


def test_other_platforms_without_proc_enumerate_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(sockets, "PROC_NET_TCP", tmp_path / "no-proc" / "tcp")
    monkeypatch.setattr(sockets, "_PLATFORM", "win32")
    monkeypatch.setattr(sockets, "_run_netstat", lambda: NETSTAT_OUTPUT)
    assert sockets.listening_ports() == []
    assert sockets.enumeration_available() is False


# --- running netstat ---------------------------------------------------------------


@pytest.mark.parametrize(
    "failure",
    [
        FileNotFoundError("no netstat"),
        subprocess.TimeoutExpired(cmd="netstat", timeout=5),
        PermissionError("denied"),
    ],
)
def test_run_netstat_failure_returns_none(monkeypatch, failure):
    def boom(*args, **kwargs):
        raise failure

    monkeypatch.setattr(sockets.subprocess, "run", boom)
    assert sockets._run_netstat() is None


def test_run_netstat_nonzero_exit_returns_none(monkeypatch):
    def failed(*args, **kwargs):
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="err")

    monkeypatch.setattr(sockets.subprocess, "run", failed)
    assert sockets._run_netstat() is None


def test_run_netstat_uses_fixed_readonly_command(monkeypatch):
    seen = {}

    def ok(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(cmd, returncode=0, stdout=NETSTAT_OUTPUT, stderr="")

    monkeypatch.setattr(sockets.subprocess, "run", ok)
    assert sockets._run_netstat() == NETSTAT_OUTPUT
    assert seen["cmd"] == [sockets.NETSTAT, "-an", "-p", "tcp"]
    assert seen["kwargs"].get("timeout")
    assert seen["kwargs"].get("shell", False) is False


def test_netstat_failure_on_macos_enumerates_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(sockets, "PROC_NET_TCP", tmp_path / "no-proc" / "tcp")
    monkeypatch.setattr(sockets, "_PLATFORM", "darwin")
    monkeypatch.setattr(sockets, "_run_netstat", lambda: None)
    assert sockets.listening_ports() == []
    assert sockets.bind_status(8766) == "absent"
