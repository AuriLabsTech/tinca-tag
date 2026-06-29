"""Command-line entry point.

The command surface (``qr``, ``doctor``, and their options) is specified in the
cockpit docs and will be implemented in milestone M1. This module is a
placeholder so the package installs and exposes the ``tinca-tag`` entry point.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``tinca-tag`` command (placeholder)."""
    print(
        "tinca-tag is not implemented yet (pre-alpha scaffolding).\n"
        "Roadmap: https://github.com/AuriLabsTech/tinca-tag/blob/main/ROADMAP.md"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
