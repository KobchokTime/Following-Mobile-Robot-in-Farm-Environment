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

---

## Correction: in-bag audit (added 2026-11-07, same day)

The sections above are kept as written. This audit of the bag contents replaces the "Result" above.

Audit script: [`bag_audit/bag_audit.py`](bag_audit/bag_audit.py). It ran on the robot against every
directory in `~/robot_day_recordings/` and reads each bag's `metadata.yaml` and the
`/synced_target`, `/yolo_frame` and `/cmd_vel` messages. Full output:
[`bag_audit/bag_audit.json`](bag_audit/bag_audit.json).
`/synced_target` data = `[cx, cy, dist_m, sector, dt_ms, stamp]`. The bearing is approximate:
`(cx − w/2)/(w/2) × 35°`, HFOV 70°, positive = image right. It is not a REP-103 bearing.

### The e1_* scenario labels are NOT ground truth

No one told the person to stand at the labelled bearing or distance. The ten runs went back to back
with a 3 s countdown. The bags show the person did not move between runs:

| Run | Label | `/yolo_frame` | `/synced_target` | dist median [min–max] m | bearing median |
| --- | --- | --- | --- | --- | --- |
| 105259Z | e1_b0_d1.0 | 42 | 27 | 1.589 [1.575–1.595] | +28.4° |
| 105322Z | e1_b0_d2.0 | 36 | 8 | 1.587 [1.585–1.589] | +28.4° |
| 105409Z | e1_b-20_d1.5 | 42 | 0 | — | — |
| 105511Z | e1_b20_d1.5 | 41 | 3 | 0.930 [0.925–1.590] | +28.4° |
| 105541Z | e1_b0_d0.5 | 29 | 4 | 0.928 [0.925–0.930] | +28.4° |
| 105610Z | e1_b0_d1.5 | 37 | 2 | 0.955 [0.927–0.982] | +28.4° |
| 105626Z | e1_b0_d3.0 | 38 | 1 | 1.596 | +28.4° |
| 105642Z | e1_b-30_d2.0 | 41 | 1 | 0.927 | +28.4° |
| 105658Z | e1_b30_d2.0 | 35 | 2 | 1.258 [0.927–1.589] | +28.4° |
| 105714Z | e1_b0_d1.0_rep | 42 | 0 | — | — |

- Every run with a lock shows the same image bearing (+28.4°, near the right edge), whatever the label says.
- Measured distances fall into two clusters (~0.93 m and ~1.59 m), whatever the label says.
- Few frames locked: 0–27 `/synced_target` messages per run, from 29–42 YOLO frames.
- **Do not use these ten runs as E1 bearing/distance ground truth.** They are valid only as
  "uncontrolled person, bridge off" captures. The E1 controlled positions must be re-recorded with
  the person placed and measured at each mark before each run.
- `20261107T105231Z_e1_b0_d1.0` holds no bag. It is the failed first attempt (MCAP plugin missing). It is kept, not deleted.

### Safety-relevant: `/cmd_vel` above the 0.5 m/s bridge cap

`follow_stop_node` sent forward commands up to **1.087 m/s** during these runs (max |vx| per run
0.61–1.09 m/s). Codex's `block_e_person_lock_*` runs show 0.58–0.84 m/s. No motion happened,
because no drive bridge was subscribed to `/cmd_vel`. The bridge is configured with
`max_speed_mps: 0.5`. Before any ground follow run, **verify on raised wheels that the bridge clamps
a >0.5 m/s `/cmd_vel` to ≤0.5 m/s**. Until a raised-wheel measurement confirms the clamp, do not
assume it works.

### Data location

- Robot: `~/robot_day_recordings/` (5.5 GB). Robot disk is 98% full (1.2 GB free), so do not record more until it is cleared.
- Laptop copy: `C:\Users\Time\Documents\robot_day_data\20261107-site01\` (outside git because of its size).

### Code that ran (robot checkout was dirty)

The robot checkout `~/robot-code` was `integration-hub @ 043b877` plus uncommitted edits to 5 files:
`config/motor_wheel_calibration.md`, `follow_bringup.launch.py`, `zlac_joystick_bridge.py`,
`record_robot_day.sh` and `ros2_yolo_live.py`. Snapshot:
[`robot_checkout_snapshot/robot-code_uncommitted.patch`](robot_checkout_snapshot/robot-code_uncommitted.patch).
YOLO was started outside the launch file with
[`robot_checkout_snapshot/start_yolo.sh`](robot_checkout_snapshot/start_yolo.sh).
The robot files were left as they were.

### Revised result

**PARTIAL.** The bags hold valid pipeline captures with the bridge off. The scenario labels are wrong,
and the E1 controlled-position runs are still to be done.
