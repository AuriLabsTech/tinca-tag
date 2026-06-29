# Roadmap

`tinca-tag` is a small, focused tool. This roadmap reflects the planned milestones.

## 0.1.x (first releases)

- `tinca-tag qr`: auto-detect the running bridge (rosbridge / foxglove_bridge) and the primary LAN address, then print a QR that encodes the Tinca connect deep link. ASCII output for headless and SSH use, with PNG and SVG output on request.
- `tinca-tag doctor`: diagnose a missing or unreachable bridge and print guidance. It only reads and advises; it never changes your system.
- Detection reads the actual running configuration (ROS 2 parameters when available, then process and socket inspection, then a default-port probe), rather than assuming defaults.

## Later

- A served, printable HTML page for per-robot QR stickers, useful for multi-robot setups with stable addresses.
- A ROS 2 package variant (`ros2 run tinca_tag qr`) for launch-file includes.

## Related (app-side, not part of this tool)

Today you scan the QR with your phone's normal camera or QR reader, which opens Tinca through the deep link with the connection pre-filled. A QR scanner built into the Tinca app is planned separately. It is an app feature, not part of `tinca-tag`, and the QR this tool prints is the same one it will scan, so nothing here needs to change when it ships.

## Non-goals

- `tinca-tag` is not a connection library and not a transport. The wire protocol lives in [ros-mobile-bridge](https://github.com/AuriLabsTech/ros-mobile-bridge).
- It is never a requirement for using Tinca. It is a convenience only.
