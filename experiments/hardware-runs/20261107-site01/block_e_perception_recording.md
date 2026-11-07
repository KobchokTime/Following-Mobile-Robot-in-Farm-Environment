# Block E — Perception Data Recording (bridge:=false)

**Date:** 2026-11-07  
**Site:** site01  
**Condition:** Wheels on ground, person present, bridge:=false (no motor commands)

## Pipeline state

| Node | PID | Status |
| --- | --- | --- |
| lidar_sectorizer | 38368 | ✅ Running |
| sync_fusion | 38370 | ✅ Running |
| fusion_prob | 38372 | ✅ Running |
| follow_stop | 38374 | ✅ Running |
| ros2_yolo_live (OpenVINO) | 40767→41208 | ✅ Running (after display-guard patch) |

**Follow pipeline launch**: nodes started manually with `bridge:=false` semantics (no ZLAC bridge node).

## Fixes applied this session

| Fix | File | Description |
| --- | --- | --- |
| Display guard | `ros2_yolo_live.py` | Wrapped `cv2.imshow/namedWindow/waitKey` with `if os.environ.get("DISPLAY"):` — Qt xcb crash on headless SSH |
| SQLite3 storage | `record_robot_day.sh` | Changed `--storage mcap` → `--storage sqlite3` (MCAP plugin not installed on robot) |

## Topic rates (verified before recording)

| Topic | Rate | Pass |
| --- | --- | --- |
| `/yolo_frame` | ~5.8 Hz | ✅ |
| `/synced_target` | ~5.9 Hz | ✅ |
| `/lidar_sector_dists` | ~10.4 Hz | ✅ |

## Recorded scenarios (10 runs)

Output root: `/home/yakgreen001/robot_day_recordings/`

| Run | Scenario label | Directory timestamp | Duration |
| --- | --- | --- | --- |
| 1 | e1_b0_d1.0 | 20261107T105259Z | 12 s |
| 2 | e1_b0_d2.0 | 20261107T105322Z | 12 s |
| 3 | e1_b-20_d1.5 | 20261107T105409Z | 12 s |
| 4 | e1_b20_d1.5 | 20261107T105511Z | 12 s |
| 5 | e1_b0_d0.5 | 20261107T105541Z | 12 s |
| 6 | e1_b0_d1.5 | 20261107T105610Z | 12 s |
| 7 | e1_b0_d3.0 | 20261107T105626Z | 12 s |
| 8 | e1_b-30_d2.0 | 20261107T105642Z | 12 s |
| 9 | e1_b30_d2.0 | 20261107T105658Z | 12 s |
| 10 | e1_b0_d1.0_rep | 20261107T105714Z | 12 s |

Topics recorded per run: `/image_raw`, `/scan`, `/lidar_sector_dists`, `/lidar_sector_angles`, `/lidar_sector_vars`, `/yolo_frame`, `/target_centroid`, `/target_centroid_sector`, `/synced_target`, `/target_fused_prob`, `/cmd_vel`, `/tf`, `/map`, `/pose`, `/camera_info`, `/rosout`.

## Preflight check (clean checkout 026fe17)

Codex clean checkout at `/home/yakgreen001/robot-follow-clean-20261107` (integration-hub @ 026fe17):

```
[PASS] code version: 026fe17
[PASS] YOLO model: /home/yakgreen001/yolov8n_openvino_model/
[PASS] ZLAC serial port: /dev/ttyUSB1
[WARN] disk for recordings: 2.9 GB free (want 5 GB) — non-blocking
[PASS] bridge parameters: mps, r=0.085 m, 0.5 m/s
[PASS] obstacle parameters: obstacle_stop on, avoid_trail off
[WARN] wheel radius: not measured yet — run speed_check.py before >0.5 m/s
ready
preflight_exit=0
```

## Result

**PASS** — 10 perception runs recorded, all pipeline topics publishing, no motor commands issued.  
Rosbags ready for Block F analysis (analyze.py).

## Pending (Sunday 2026-11-15)

- Block F: run `analyze.py` on rosbags, commit results
- Merge Codex's integration-hub changes (wheel dir fix, queue=1 latency fix, preflight gate 247/247)
- Raised-wheel turn check with clean checkout + bridge open → then ground follow test
