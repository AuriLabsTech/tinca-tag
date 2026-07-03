"""Command-line entry point.

``tinca-tag qr`` detects the running bridge, echoes what it found for confirmation
(ADR 0003), and renders the Tinca connect QR. Offline: the only sockets touched are the
robot's own bridge on the LAN. ``doctor`` is M2 and not implemented here.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .detect import Detection, detect
from .render import InvalidHost, connect_url, save, terminal_str, validate_host


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tinca-tag",
        description="Scan-to-connect QR codes for ROS 2 robots, for the Tinca app.",
    )
    parser.add_argument("--version", action="version", version=f"tinca-tag {__version__}")
    sub = parser.add_subparsers(dest="command")

    qr = sub.add_parser("qr", help="detect a bridge and print a connect QR")
    qr.add_argument("--host", help="LAN host/IP to emit (default: this host's LAN IP)")
    qr.add_argument("--port", type=int, help="bridge port (default: detected)")
    qr.add_argument(
        "--protocol",
        choices=["rosbridge", "foxglove-ws"],
        help="bridge protocol (default: detected via the WS handshake)",
    )
    secure = qr.add_mutually_exclusive_group()
    secure.add_argument(
        "--secure",
        dest="secure",
        action="store_true",
        default=None,
        help="force secure (wss). Default: detected.",
    )
    secure.add_argument(
        "--no-secure",
        dest="secure",
        action="store_false",
        help="force plaintext (ws).",
    )
    qr.add_argument("--mdns", action="store_true", help="emit <hostname>.local as the host")
    qr.add_argument("--name", help="friendly robot name (additive &name= param / sticker label)")
    out = qr.add_mutually_exclusive_group()
    out.add_argument("--png", dest="kind", action="store_const", const="png", help="write a PNG")
    out.add_argument("--svg", dest="kind", action="store_const", const="svg", help="write an SVG")
    qr.add_argument("--out", "-o", help="output file path (implies a file format)")
    qr.add_argument("--timeout", type=float, default=1.0, help="per-probe timeout in seconds")
    qr.set_defaults(func=cmd_qr)

    return parser


def _resolve_output(kind: str | None, out: str | None) -> tuple[str | None, Path | None]:
    """Decide (kind, path): None kind means ASCII to stdout."""
    if out:
        suffix = Path(out).suffix.lstrip(".").lower()
        resolved = kind or (suffix if suffix in ("png", "svg") else "png")
        return resolved, Path(out)
    if kind:
        return kind, Path(f"tinca-qr.{kind}")
    return None, None


def _annotate_host(det: Detection) -> str:
    host = det.endpoint.host
    if host == det.lan_ip:
        return "LAN IP"
    if host.endswith(".local"):
        return "mDNS"
    return "provided"


def _yes_no(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "yes" if value else "no"


def _echo(det: Detection, url: str) -> None:
    """Print the detected config for confirmation before emitting (ADR 0003)."""
    ep = det.endpoint
    lines = [
        "tinca-tag: detected bridge",
        f"  host      {ep.host}  ({_annotate_host(det)})",
        f"  port      {ep.port}",
        f"  protocol  {ep.protocol}",
        f"  secure    {_yes_no(ep.secure)}",
        f"  reachable {_yes_no(det.reachable)}",
        f"  source    {det.source}",
        f"  link      {url}",
    ]
    print("\n".join(lines), file=sys.stderr)
    for note in det.notes:
        print(note, file=sys.stderr)


def cmd_qr(args: argparse.Namespace) -> int:
    if args.host:
        try:
            validate_host(args.host)
        except InvalidHost as exc:
            print(f"tinca-tag: invalid --host: {exc}", file=sys.stderr)
            return 2

    det = detect(
        host=args.host,
        port=args.port,
        protocol=args.protocol,
        secure=args.secure,
        mdns=args.mdns,
        timeout=args.timeout,
    )

    if not det.ok:
        for note in det.notes:
            print(note, file=sys.stderr)
        return 1

    url = connect_url(det.endpoint, name=args.name)
    _echo(det, url)

    kind, path = _resolve_output(args.kind, args.out)
    if kind is None:
        sys.stdout.write(terminal_str(url))
    else:
        written = save(url, path, kind=kind)
        print(f"Saved {kind.upper()} QR to {written}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``tinca-tag`` command."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
