"""Endpoint to deep-link URL (ADR 0001).

Builds the frozen ``tinca://connect?host=&port=&secure=&protocol=`` string from an
:class:`~tinca_tag.endpoint.Endpoint`. The contract is shared with the Tinca app and
the sims-web companion page; this mirrors the byte shape that page emits via
``URLSearchParams`` (param order ``host, port, secure, protocol``) so all three
consumers stay conformant. Do not reorder or rename params without coordinating the
contract (ADR 0001).
"""

from __future__ import annotations

from urllib.parse import quote_plus

from ..endpoint import Endpoint

SCHEME = "tinca"


class InvalidHost(ValueError):
    """Raised when a host is not a bare hostname / IP (ADR 0001)."""


def validate_host(host: str) -> str:
    """Return ``host`` if it is a bare hostname or IP, else raise :class:`InvalidHost`.

    The contract requires no scheme, no embedded port, no trailing slash, no
    whitespace. The app builds ``ws(s)://<host>:<port>`` itself.
    """
    if not host:
        raise InvalidHost("host is empty")
    lowered = host.lower()
    if "://" in lowered or lowered.startswith(("ws:", "wss:", "http:", "https:")):
        raise InvalidHost(f"host must not include a scheme: {host!r}")
    if "/" in host:
        raise InvalidHost(f"host must not include a path or slash: {host!r}")
    if any(c.isspace() for c in host):
        raise InvalidHost(f"host must not contain whitespace: {host!r}")
    # A ':' means an embedded port (IPv4/hostname) -- reject. Bare IPv6 literals
    # (which legitimately contain ':') are not part of the contract today; the app
    # builds ws://<host>:<port> and would need brackets, so we reject ':' outright.
    if ":" in host:
        raise InvalidHost(f"host must not include an embedded port: {host!r}")
    return host


def connect_url(endpoint: Endpoint, name: str | None = None) -> str:
    """Build the ``tinca://connect`` deep link for ``endpoint``.

    Param order matches the sims-web emitter (``host, port, secure, protocol``) so
    the emitted string is byte-identical to the proven companion page. ``name`` is an
    optional additive param (ADR 0006); the app ignores unknown params today, so it is
    safe to include for the printed-sticker label.
    """
    host = validate_host(endpoint.host)
    query = (
        f"host={host}"
        f"&port={endpoint.port}"
        f"&secure={1 if endpoint.secure else 0}"
        f"&protocol={endpoint.protocol}"
    )
    if name:
        query += f"&name={quote_plus(name)}"
    return f"{SCHEME}://connect?{query}"
