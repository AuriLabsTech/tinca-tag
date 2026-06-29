"""tinca-tag: scan-to-connect QR codes for ROS 2 robots.

The QR / handoff layer for the Tinca app. It detects a running ROS 2 bridge
(rosbridge or foxglove_bridge) and renders the Tinca connect deep link as a QR.
Strictly optional, never a requirement for connecting.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("tinca-tag")
except PackageNotFoundError:  # running from a source checkout, not installed
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
