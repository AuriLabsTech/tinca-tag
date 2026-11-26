# Changelog

All notable changes to this project are documented here. The format is based on Keep a Changelog, and this project aims to follow Semantic Versioning once it reaches 0.1.0.

## [Unreleased]

### Added

- `tinca-tag qr`: detect a running ROS 2 bridge (rosbridge or foxglove_bridge) and render the Tinca connect QR, fully offline. Outputs an ASCII QR by default, or a PNG or SVG file.
- Bridge detection reads the actual running config instead of guessing: a WebSocket handshake probe distinguishes foxglove_bridge from rosbridge and detects TLS, listening-port enumeration finds bridges on nonstandard ports, and the host's primary LAN IP is used so the QR is reachable from a phone.
- Flags: `--host`, `--port`, `--protocol`, `--secure` / `--no-secure`, `--mdns`, `--name`, `--png`, `--svg`, `--out`.
- Listening-port enumeration on macOS (via the built-in `nettop`, no root needed), so a bridge on a nonstandard port is found on a Mac without `--port`. When this machine's ports cannot be listed, `qr` and `doctor` say so instead of reporting only what 9090 and 8765 show.
- When more than one bridge answers, `qr` and `doctor` list them as bullets, each with the command that picks it, instead of choosing one. `--protocol` narrows the list.
