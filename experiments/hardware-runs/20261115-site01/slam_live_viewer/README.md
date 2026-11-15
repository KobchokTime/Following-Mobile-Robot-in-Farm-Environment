# Mapping-only SLAM + live viewer validation, 2026-11-15 17:02–17:06 (robot stationary)

Code and full write-up: [`ros2_yolo_ws/scripts/mapping/README.md`](../../../../ros2_yolo_ws/scripts/mapping/README.md).

| File | What |
|---|---|
| `run_20261115T170259.log` | Robot log of `slam_mapping_only.sh` (lidar_health PASS, static TFs, slam_toolbox, clean stop) |
| `viewer_live_8773.jpg` | Viewer in LIVE state, scan overlay on walls |
| `live_map_20261115T170447.{pgm,yaml,json}` | Map saved by the viewer's Save button from a fresh live `/map` (238 × 92 @ 0.05 m, 28.4% known) |
| `SHA256SUMS` | Hashes of the files above |

Only the LiDAR spun; no drive bridge, joystick, teleop or motor serial port was opened, and the robot
was not moved. This is a single-spot snapshot, not a map of the site.
