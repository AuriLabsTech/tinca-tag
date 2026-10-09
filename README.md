# tinca-tag

Scan-to-connect QR codes for ROS 2 robots.

`tinca-tag` runs on your robot, detects the ROS 2 bridge you already have running (rosbridge or foxglove_bridge), and prints a QR code. Scan it with your phone's camera and Tinca opens with the host, port, and protocol already filled in, so you just tap Connect. No reading off an IP, switching apps, and typing `host:port` by hand. Because the QR is built from the robot's live network address, it keeps working across reboots and DHCP changes.

> Status: pre-alpha. `qr` and `doctor` both work, but options and output may still change before 0.1.0. See [ROADMAP.md](ROADMAP.md).

## Why

Connecting a phone to a robot usually means finding the robot's IP, switching to the app, and typing `host:port` correctly on a touch keyboard. A mistyped address is a classic first-connection failure. `tinca-tag` removes that step: scan the QR and the connection is pre-filled for you.

It is strictly optional. Tinca connects to any standard rosbridge or foxglove_bridge with nothing extra installed on the robot. `tinca-tag` is a convenience on top of that, never a requirement.

## Install

```
pip install tinca-tag
```

(Not published yet. Pre-release builds will be installable with `pip install --pre tinca-tag`.)

## Usage

```
tinca-tag qr        # detect the bridge and print a QR to connect
tinca-tag doctor    # check the setup and report what, if anything, is wrong
```

Both commands detect everything by default. To override what they find, use `--host`, `--port`, `--protocol`, `--secure` / `--no-secure`, or `--mdns` (emit `<hostname>.local` as the host). `qr` can also write a file with `--png` or `--svg` (and `--out <path>`), and label the robot with `--name`.

`doctor` only reads and advises. When something is wrong, it prints the commands to fix it; it never runs them for you. Run `tinca-tag <command> --help` for the full list.

## What the QR contains

The QR encodes a Tinca deep link:

```
tinca://connect?host=<host>&port=<port>&secure=<0|1>&protocol=<rosbridge|foxglove-ws>
```

You scan the QR with your phone's camera or any QR reader. Because it is a deep link, your phone offers to open it in Tinca, which fills in the connection for you; you then tap Connect. (A scanner built into the Tinca app is planned for later, and the same QR will work there too.) Nothing in the link is secret; on a trusted LAN it simply tells the app where the bridge is. Treat the address as you would any other service address on your network.

## License

Apache-2.0. Copyright 2026 Auri Labs.

The license covers the code. It does not grant any right to use the Tinca name or logo (see section 6 of the license).
