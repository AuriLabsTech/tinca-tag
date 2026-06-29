"""The Endpoint type: the seam between detection and rendering (ADR 0008).

``detect/`` produces an Endpoint; ``render/`` consumes one. The deep-link URL and
the QR are pure functions of an Endpoint. Keep this module free of detection and
rendering logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Protocol = Literal["rosbridge", "foxglove-ws"]


@dataclass(frozen=True)
class Endpoint:
    """A bridge endpoint a phone can connect to.

    Fields map directly onto the frozen deep-link contract (ADR 0001):
    ``tinca://connect?host=&port=&secure=&protocol=``.
    """

    host: str
    port: int
    protocol: Protocol
    secure: bool
