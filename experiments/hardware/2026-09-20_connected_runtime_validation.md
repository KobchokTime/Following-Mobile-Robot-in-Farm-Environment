# Connected runtime validation — 2026-09-20

## Scope

Live checks performed through the local Robot Console while connected to the
robot. No autonomous following, ROS motor bridge, LiDAR acquisition, or ground
motion was enabled.

## Live hardware inventory

- Camera: Logitech C922 Pro Stream Webcam at `/dev/video0` (also exposes
  `/dev/video1`), 640×480 YUYV.
- Motor transport: FTDI FT232R at `/dev/ttyUSB0`, USB serial `A50285BI`.
- Controller read-only state: operation mode `3`, left/right faults `0x0000`,
  left/right feedback `0.0 RPM`.
- User account is in the `dialout` group.
- ROS graph snapshot contained only `/parameter_events` and `/rosout`; no live
  application control graph was running.
- A YDLidar workspace exists, but no LiDAR was enumerated in the attached USB
  inventory during this session.

## Live vision results

| Check | Result |
| --- | --- |
| YOLOv8n OpenVINO 320, 60 frames | 14.10 FPS; mean 70.9 ms; P95 71.8 ms; model hash `71c5a2160ba78dec36850f67ae717739211076e5a176ef8e8001b53540552528` |
| Tracking probe, 80 frames | PASS; 14.06 FPS; 0 motor commands; scene contained no person detections |
| Persistent Pose OpenVINO 320 | PASS; 10.75 FPS; mean 93.0 ms; P95 98.9 ms |
| Deployed temporal pose service | PASS after upload fallback fix; readback `NO_TARGET`, 10.48 FPS, 0 motor commands |

`NO_TARGET` is the expected result for the camera view at the time of the
service readback. It is a service-liveness check, not an orientation-accuracy
trial.

## Deployment fix made during the session

`dashboard/bridge/server.mjs` originally streamed the small pose-service source
into a remote `cat` command and interpreted lack of a local read event as an
upload stall. The deployment path now sends this small source file as a bounded
inline base64 payload, verifies SHA-256, and starts the service locally on the
robot. The initial health request returned HTTP 503 while frames were not yet
ready; a later temporal-state read verified normal service operation.

## Storage snapshot

- Root filesystem: 42 GB total, 34 GB used, 5.9 GB available (86% used).
- Largest retained areas: `openvino_env` 5.8 GB, `raina_001` 3.5 GB,
  `.vscode-server` 3.1 GB.
- No files were deleted in this session.

## Remaining physical/live gates

1. Orientation protocol with a person performing FRONT/BACK/LEFT/RIGHT and
   NO_TARGET, retaining labeled evidence.
2. Loss/reacquisition protocol with a person in frame.
3. Encoder scale/sign and repeated guarded pulses with logs.
4. LiDAR discovery and timestamp/ROS live validation.
5. Turn-only and then ground-following tests.
