"""Rendering: Endpoint to deep link and QR (ADR 0001, 0002).

Consumes an :class:`~tinca_tag.endpoint.Endpoint` and produces the
``tinca://connect?...`` URL and the QR (ASCII / PNG / SVG). Offline: no network calls.
"""

from .qr import make_qr, png_bytes, save, terminal_str
from .url import SCHEME, InvalidHost, connect_url, validate_host

__all__ = [
    "SCHEME",
    "InvalidHost",
    "connect_url",
    "validate_host",
    "make_qr",
    "png_bytes",
    "save",
    "terminal_str",
]
