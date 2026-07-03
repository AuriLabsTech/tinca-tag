"""CLI wiring for `tinca-tag qr`: echo, URL, output formats, exit codes.

`detect` is patched to keep these offline; the detection rungs themselves are covered by
test_detect_orchestration and CP-C.
"""

import pytest

from tinca_tag import cli
from tinca_tag.detect import Detection
from tinca_tag.endpoint import Endpoint

FOX = Endpoint(host="192.168.1.50", port=8765, protocol="foxglove-ws", secure=False)


def _ok_detection(endpoint=FOX, **kwargs):
    base = dict(
        endpoint=endpoint,
        source="probe (127.0.0.1:8765)",
        lan_ip="192.168.1.50",
        reachable=True,
        in_container=False,
        notes=[],
    )
    base.update(kwargs)
    return Detection(**base)


def _patch_detect(monkeypatch, detection):
    monkeypatch.setattr(cli, "detect", lambda **kwargs: detection)


def test_qr_ascii_to_stdout(monkeypatch, capsys):
    _patch_detect(monkeypatch, _ok_detection())
    assert cli.main(["qr"]) == 0
    out = capsys.readouterr()
    assert "█" in out.out  # an actual QR was drawn
    assert "detected bridge" in out.err
    assert "tinca://connect?host=192.168.1.50&port=8765&secure=0&protocol=foxglove-ws" in out.err


def test_qr_name_appended_to_link(monkeypatch, capsys):
    _patch_detect(monkeypatch, _ok_detection())
    assert cli.main(["qr", "--name", "My Robot"]) == 0
    err = capsys.readouterr().err
    assert "&name=My+Robot" in err


def test_qr_writes_png(monkeypatch, capsys, tmp_path):
    _patch_detect(monkeypatch, _ok_detection())
    target = tmp_path / "robot.png"
    assert cli.main(["qr", "--out", str(target)]) == 0
    assert target.exists()
    assert target.read_bytes().startswith(b"\x89PNG\r\n")
    assert "Saved PNG QR" in capsys.readouterr().out


def test_qr_png_flag_default_filename(monkeypatch, capsys, tmp_path):
    _patch_detect(monkeypatch, _ok_detection())
    monkeypatch.chdir(tmp_path)
    assert cli.main(["qr", "--png"]) == 0
    assert (tmp_path / "tinca-qr.png").exists()


def test_qr_writes_svg(monkeypatch, capsys, tmp_path):
    _patch_detect(monkeypatch, _ok_detection())
    target = tmp_path / "robot.svg"
    assert cli.main(["qr", "--out", str(target), "--svg"]) == 0
    assert target.exists()
    assert b"<svg" in target.read_bytes()


def test_qr_no_detection_returns_1(monkeypatch, capsys):
    det = Detection(
        endpoint=None,
        source="none",
        lan_ip="192.168.1.50",
        reachable=None,
        in_container=False,
        notes=["No ROS 2 bridge detected."],
    )
    _patch_detect(monkeypatch, det)
    assert cli.main(["qr"]) == 1
    assert "No ROS 2 bridge detected." in capsys.readouterr().err


def test_qr_invalid_host_returns_2(monkeypatch, capsys):
    # detection should never be reached; validation rejects first
    _patch_detect(monkeypatch, _ok_detection())
    assert cli.main(["qr", "--host", "ws://192.168.1.50"]) == 2
    assert "invalid --host" in capsys.readouterr().err


def test_unreachable_warning_still_emits(monkeypatch, capsys):
    det = _ok_detection(reachable=False, notes=["Warning: ... did not answer ..."])
    _patch_detect(monkeypatch, det)
    assert cli.main(["qr"]) == 0
    err = capsys.readouterr().err
    assert "reachable no" in err
    assert "did not answer" in err


def test_bare_invocation_prints_help(capsys):
    assert cli.main([]) == 0
    assert "usage" in capsys.readouterr().out.lower()


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert "tinca-tag" in capsys.readouterr().out
