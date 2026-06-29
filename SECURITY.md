# Security Policy

## Reporting a Vulnerability

If you believe you have found a security vulnerability in `tinca-tag`, please report it privately. Do not open a public GitHub issue.

Email: `security@aurilabs.tech`

Include:

- A description of the issue and its impact.
- Reproduction steps or a proof of concept, if available.
- The affected version(s).
- Your name and contact details (optional, for credit).

## Process and Timeline

- Acknowledgement: within 3 business days of receipt.
- Triage and assessment: within 7 business days.
- Fix or mitigation for confirmed high-severity issues: within 30 days of confirmation.
- Coordinated disclosure: public disclosure happens after a fix is released, or after 90 days if no fix is feasible. Earlier disclosure is possible by mutual agreement.

## Design notes relevant to security

`tinca-tag` runs on the robot and is intentionally minimal:

- The core `qr` path makes no outbound network calls. It reads the local bridge configuration and renders a QR.
- It never modifies the system. When setup is missing, it prints suggested commands for you to run; it does not run installs, firewall changes, or any other system modification.
- The QR encodes the bridge's LAN address. On a trusted network this is information any device on that network can already discover. Do not post a robot's QR publicly if its bridge is reachable from an untrusted network.

## In Scope

- The published package and its runtime behavior.
- Any code path that reads local configuration or renders output.

## Out of Scope

- Third-party bridge software (`foxglove_bridge`, `rosbridge_server`). Report those upstream.
- The security of the network the robot is on.
- Misconfiguration of the host system.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes |
| < 0.1   | No (pre-release) |
