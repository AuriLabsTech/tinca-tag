"""Bridge and endpoint detection (ADR 0003, 0007).

Produces a validated :class:`~tinca_tag.endpoint.Endpoint`. Reads the actual
running configuration in priority order: ROS 2 params, then process / socket
inspection, then a default-port probe, then explicit overrides. Validates that
the chosen endpoint is reachable on the LAN, not just locally.

Not implemented yet. See milestone M1.
"""
