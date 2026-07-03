"""Deep-link URL to QR (ADR 0002).

Offline rendering with ``segno`` only (a core dep). Error correction is fixed at level
H (~30%) so a centered Tinca logo can be composited later without breaking decode
(ADR 0002, verified by the CP-B round-trip test). No network calls happen here.
"""

from __future__ import annotations

import io
from pathlib import Path

import segno

# ADR 0002: level H tolerates a centered logo; CP-B pins that the QR still decodes.
ERROR_LEVEL = "h"

# Map output format to the kind segno expects, so callers pass a friendly name.
_KINDS = {"png", "svg", "txt"}


def make_qr(url: str) -> segno.QRCode:
    """Build the QR symbol for ``url`` at the fixed error-correction level."""
    return segno.make(url, error=ERROR_LEVEL)


def terminal_str(url: str, *, border: int = 2, compact: bool = True) -> str:
    """Return the QR as a compact terminal string (the default ``qr`` output)."""
    buf = io.StringIO()
    make_qr(url).terminal(out=buf, border=border, compact=compact)
    return buf.getvalue()


def png_bytes(url: str, *, scale: int = 8, border: int = 4) -> bytes:
    """Return PNG bytes for ``url`` (used by file output and the CP-B round-trip)."""
    buf = io.BytesIO()
    make_qr(url).save(buf, kind="png", scale=scale, border=border)
    return buf.getvalue()


def save(
    url: str, path: str | Path, *, kind: str | None = None, scale: int = 8, border: int = 4
) -> Path:
    """Write the QR for ``url`` to ``path``.

    ``kind`` ("png" / "svg") overrides the format; otherwise it is inferred from the
    file extension. Returns the resolved path.
    """
    path = Path(path)
    if kind is None:
        kind = path.suffix.lstrip(".").lower() or "png"
    if kind not in _KINDS:
        raise ValueError(f"unsupported output kind: {kind!r} (expected png or svg)")
    make_qr(url).save(str(path), kind=kind, scale=scale, border=border)
    return path
