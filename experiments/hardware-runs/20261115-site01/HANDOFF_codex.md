# Handoff to Codex: robot day 2026-11-15 (site01)

From Claude, 2026-11-15. Everything below is on branch `claude/test-ssh-humsai-67e424`, under
`experiments/hardware-runs/20261115-site01/` (PR #17). Proposed as **T22** in `DISCUSSION.md`. Hub
`HANDOFF.md` / `DISCUSSION.md` will be updated on `integration-hub` under the lock only after the
operator approves.

## 1. Main task (T22): LiDAR-held track at the image edge turns the robot away from the person

**Symptom, seen twice on hardware:**
- `20261115T060903Z_e6_session` at t = 23–26 s (t = 0 is 06:18:55 UTC). Analysis in [`e6_series_stop.md`](e6_series_stop.md).
- `20261115T041627Z_follow_first_short` at t ≈ 1.6–1.9 s. Analysis in [`follow_and_slam.md`](follow_and_slam.md).

In both, the person was at about 1.1–1.6 m. The camera's largest YOLO box was at the centre or on the
right (−2° to −30°). Meanwhile `/synced_target` reported the target at the **left image edge**
(cx = 0, +35°), and `follow_stop` turned left at +0.8 rad/s, away from the person. In the E6 case
the camera box was centred at t = 24 s and on the right at t = 25 s, yet the fused output never
switched back to it. The person was lost by t = 26 s.

**Probable path (not yet confirmed; confirming it is part of the task):**
1. The person moves left quickly. The camera track lags, and `assist_with_lidar` /
   `track_with_lidar` move the `TargetGate` track onto a LiDAR cluster.
2. The cluster is something else on the left, not the person. The track runs to the left edge, and
   `track_with_lidar` publishes cx = 0 because the bearing is beyond the camera's half field of view.
3. The real person's camera box fails `TargetGate.accept`: its cost against the drifted prediction
   is above the gate, and `_reacquire` does not take it back within bearing/colour/distance. So it
   is treated as another person, and the LiDAR track keeps publishing.
4. `follow_stop` turns at the full rate towards the edge. Edge steering
   (`front_band_radius = wide_front_radius = 2`) cannot help, because cx = 0 is in S0.

Code at `codex/robot/field-forward-review @ 026fe17`, `ros2_yolo_ws/scripts/Image/sync_fusion_node.py`:
- `TargetGate` (`:165`): `_predict` `:273`, `cost` `:283`, `_reacquire` `:306`, `accept` `:365`
- `assist_with_lidar` `:614`, `track_with_lidar` `:664`, `try_sync_from_yolo` `:732`
- the controller's edge handling is in `follow_stop_node.py`: the sector block near `:686`, and bearing mode `cx <= 0`

**Reproduce offline:**
```
python3 -m sim.replay.replay_bag <bag>/recording --out replay_out
```
The session bag is image-free but holds `/scan`, `/target_centroid_sector`, `/target_centroid`,
`/yolo_frame`, `/synced_target` and `/cmd_vel`. The first follow bag also holds `/image_raw/compressed`.
The E6 bag needs these node parameters: `lidar_angle_offset_deg:=6.2 lidar_angle_sign:=-1.0
target_distance:=1.0 steer_mode:=sector front_band_radius:=2 wide_front_radius:=2`. The first follow
bag needs target 0.5 and the default bands. **`replay_bag.py` cannot pass node parameters yet.** Its
only options are `--out`, `--inputs` and `--rate`, and `sim/twin/pipeline.py`
`Processes.start_robot_nodes(ros_args)` is not given any. Adding a parameter pass-through is part of
this task.
- Wrong-turn detector: [`e6_check.py`](e6_check.py). It compares the turn sign with the side of the
  largest YOLO box while the fused range is ≥ 0.9 m.
- Frame renderer: [`render_turn_frames.py`](render_turn_frames.py).

**Done when:**
- The replay of both bags shows **no wrong-direction turn** at ≥ 0.9 m (by `e6_check.py`'s rule).
- A camera person box inside the image is never overridden by a LiDAR-only edge target on the
  opposite side. Either the gate takes the box back, or the fused output fails closed (no target,
  so a zero command) while camera and LiDAR disagree. Choose with the safety rule: **safety never
  changes identity**. Prefer fail-closed over switching to a person who may be someone else.
- There are unit tests for that rule. `scripts/check.py` passes. The twin is not worse than the current
  robot-day configuration (106/110, 0 contacts). Add a twin scenario for "fast side step left past
  a static cluster".
- Branch `codex/robot/<topic>` → PR into `integration-hub`, all three CI jobs green. Claude does an
  independent review before merge. No main merge. No robot motion.

## 2. Robot-local patches to turn into proper commits (separate small PRs)

The robot checkout `~/robot-follow-clean-20261107` (026fe17) is dirty with:

| Change | Why | Where now |
| --- | --- | --- |
| `record_robot_day.sh`: `--storage sqlite3` and `--exclude "^/image_raw(/theora\|/compressedDepth)?$"` | The robot has no MCAP plugin. Raw images were ~90 % of each bag and filled the disk | robot checkout only |
| `follow_bringup.launch.py`: launch args `front_band_radius`, `wide_front_radius` (default 1) | operator's "edge" steering, turn only in S0–S1/S7–S8 | robot checkout only (3 lines) |
| LiDAR yaw `lidar_angle_offset_deg 6.2` (sign −1) | LiDAR remounted at 0.70–0.73 m; measured at 1.6 m and 3.8 m. See [`lidar_mount_change.md`](lidar_mount_change.md) | [`start_follow.sh`](start_follow.sh); the launch default is still 0.0 |
| `lidar_health.py` (≥ 70 % valid beams, ≥ 7 Hz) | the driver once started with ~18 % valid beams and phantom ranges | [`lidar_health.py`](lidar_health.py). Proposal: fold it into `preflight.py --live` |
| `run_check.py`, `e6_check.py`, `walk_shape.py`, `lidar_mount_check.py` | per-run field checks | this folder |

Outside the repo, on the robot: `~/start_follow.sh` (off|on, sector|edge|bearing, target distance),
`~/start_joy.sh` (joystick only), `~/slam_map_1115.sh`, and `~/slam_params_1115.yaml`. The YOLO venv
`~/openvino_env` now also has `minimalmodbus 2.1.1` / `pyserial 3.5`. Launch runs with that venv
active, because system `python3` has no `ultralytics`.

## 3. Findings to carry into docs and the thesis

- **SLAM argument bug:** `online_async_launch.py` takes `slam_params_file:=`, not `params_file:=`. With
  the wrong name it silently used defaults (`base_frame: base_footprint`), so every scan failed with
  "Failed to compute odom pose". The 2026-11-07 `slam_bringup.sh` had the same bug **and** a TF with
  no roll for the mirrored scan. **`map_20261107T081703` should be treated as invalid.** A valid map
  from today is `maps/map_20261115T115027` (6.3 × 6.0 m).
- **Glass:** facing a glass door at 0.32 m, the front ±30° had 3–30 % valid beams (62 % overall).
  Claude first misreported this as outdoor sunlight and corrected it the same day. Sunlight has not
  been tested.
- **Low obstacles:** at 0.70–0.73 m the LiDAR does not see anything lower, so obstacle stop does
  not cover it. The operator's proposed camera "crossing guard" (stop for anything in front of the
  target) is deferred.
- **Lock-on window** is 0.5–1.0 m, by design (`sync_fusion_node.py` `lock_range`). Started from farther
  away, nothing is published.
- **Bearing mode:** one unexplained right turn with the person standing still. There was no
  recording, so the cause is unknown. Do not use bearing mode until it is replayed with a bag.
- **0.5 m/s cap holds:** the bridge never wrote more than 56.17 rpm while `follow_stop` asked for up to 0.88 m/s.

## 4. Data and robot state

- Laptop backup, md5-verified (42 files): `C:\Users\Time\Documents\robot_day_data\20261115-site01\`
  (`MANIFEST.md5`). The 7 Nov backup is in `...\20261107-site01\`.
- Robot disk is **98 % (1.1 GB free)**. Today's bags are still on the robot. The operator's rule is
  to delete only after analysis and an md5-verified backup. The backup is done; analysis is not.
- Robot right now: no follow pipeline, bridge, joystick or recorder running.
- The E6 series (coordinator plan, edge mode, target 1.0 m) is **stopped** after the first run, per
  its own stop rule. It restarts only after T22 is fixed and replayed.
