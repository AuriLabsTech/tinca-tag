# Contributing to tinca-tag

Thanks for your interest. This is a small, intentionally focused tool, so please read this guide before opening a PR.

## What this tool is, and isn't

`tinca-tag` turns a robot's live bridge connection into a scannable QR for the Tinca app. It is the QR / handoff layer, not the connection layer (that is [ros-mobile-bridge](https://github.com/AuriLabsTech/ros-mobile-bridge)), and not a robotics framework. It is always optional: it must never become something the Tinca app requires.

Smaller is better. Prefer the simplest tool that solves the problem.

## Before you open a PR

1. Discuss first for anything non-trivial. Open an issue describing the problem and the proposed change.
2. Keep the deep-link format stable. The `tinca://connect?...` link is a contract shared with the Tinca app and other tools. Do not change its shape in a PR; that requires coordination across all consumers.
3. Guide, do not execute. `tinca-tag` never runs system changes (installs, firewall edits) on the user's behalf. It prints commands for the user to run. PRs that add system-modifying behavior will be declined.

## Development setup

```
git clone https://github.com/AuriLabsTech/tinca-tag.git
cd tinca-tag
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Common commands:

- `ruff check .` and `ruff format .` for lint and formatting
- `pytest` for the test suite

## Code style

- Format and lint with ruff. Type hints on public functions.
- The core package depends only on the standard library plus `segno`. Heavier dependencies (for diagnostics) live behind the `doctor` optional extra. ROS-specific code lives in the ROS 2 package variant, not the core.

## Tests

- A change to detection or rendering without a test is incomplete work.
- A bug fix without a regression test is incomplete work.

## Adding a dependency

Adding a runtime dependency to the core requires a short rationale in the PR: what it does, what it replaces, and its SPDX license. The license must be permissive (MIT, Apache-2.0, BSD, ISC, or similar). Keep the core lean; prefer the optional extras for anything heavy.

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
