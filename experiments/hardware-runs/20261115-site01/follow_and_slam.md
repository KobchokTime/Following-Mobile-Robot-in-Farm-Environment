# 2026-11-15 site01: first ground follow, turning, and SLAM map

Code: `~/robot-follow-clean-20261107` = `codex/robot/field-forward-review @ 026fe17` (PR #19), plus the
sqlite3 / raw-image-exclusion patch to `record_robot_day.sh`. The start script is
[`start_follow.sh`](start_follow.sh), which sets `max_speed_mps=0.5`, `wheel_radius_m=0.085`,
`forward_dir=-1.0`, `turn_dir=1.0`, LiDAR offset 6.2° / sign −1, and `steer_mode` sector or bearing.

## Ground follow without lifted wheels

The operator chose to skip the raised-wheel test. In its place:

- The bridge was started with nobody in the 0.5–1.0 m lock zone.
- `lidar_health.py` passed at 85 %.
- `preflight.py --live` reported `ready` with 0 FAIL. It read these back from the running nodes:
  - `forward_dir=-1.0`, `max_speed_mps=0.5`, `wheel_radius_m=0.085`, `turn_dir=1.0`;
  - offset 6.2° and sign −1 on all three LiDAR nodes;
  - obstacle stop at 0.45 m.

The operator confirmed in writing: nobody else within 3 m, the area behind the robot clear, and a
spotter on the e-stop.

### Run `20261115T041627Z_follow_first_short` (steer_mode=sector, target_distance 0.5 m)

- Locked on in 95 % of frames: 145 `/synced_target` messages from 152 YOLO frames.
- **Following works in the right direction.** While the person walked away, `follow_stop` sent
  ~+0.7 m/s and the fused range stayed at ~0.9–0.98 m (t = 14–18.5 s). With the wrong forward
  direction the range would have grown quickly.
- It closed to ~0.5 m and sent zero three times. Below 0.44 m it backed off at up to 0.33 m/s.
- **The 0.5 m/s cap holds on hardware.** The bridge never wrote more than 56.17 rpm (= 0.5 m/s at
  r = 0.085 m), while `follow_stop` asked for up to 0.88 m/s. Only the last ~1000 terminal lines
  were checked, but that window includes the cap being hit.
- Ground speed was not measured: the bridge has no odometry, and the scan has no wall behind the robot.

### Turning problems seen in that run

[`turn_frames_sector_run.png`](turn_frames_sector_run.png) was made with
[`render_turn_frames.py`](render_turn_frames.py). It shows YOLO boxes, the 9 sectors, the fused
target column and `/cmd_vel` at six moments:

| t | What the camera shows | Fused target | Command | |
| --- | --- | --- | --- | --- |
| 0.9 s | person at 0.55 m, only legs visible; YOLO box at S0–S3 | S1, +28° | turn left 0.8 | wrong |
| 1.6 s | person clearly on the **right**, S4–S8 | **cx = 0 (S0), +35°, 1.57 m** | **turn left 0.8, forward 0.88** | wrong direction |
| 5.6 s | no person, only a chair and bag | S5, 0.50 m | zero | tracking the chair |
| 8.6 s | person right, S6 | S6, −15° | turn right 0.4 | correct |
| 9.7 s | person right, S6 | S6, −17° | turn right 0.8 | correct |
| 16.4 s | person centre, S3 | S3, +7.5° | forward, no turn | correct |

Every bad turn happened with the person nearer than ~0.6 m. There the low camera sees only legs,
and YOLO misplaces or loses the box. The LiDAR track then holds a target that can be a chair, or
the image edge (cx = 0) on the wrong side. At ~0.9 m and beyond, every sampled frame turned the
right way. The candidate fix is `target_distance` ≈ 1.0 m (the thesis draft used 1.2 m). It is
untested.

### Unexplained right turn (steer_mode=bearing, no recording)

After a restart with `steer_mode=bearing`, the operator reported that the robot turned right while
they stood still. The run was stopped at once, and the bridge and controller were confirmed dead.
**The cause is unknown.** All nodes log to the screen only, so the start of that session is lost.
The last ~47 s of bridge output was 468 zero writes, with no person in view. Two hypotheses:
- bearing mode turns towards any target more than 3° off centre;
- the LiDAR track placed the target at the image edge.

**Rule from now on:** record a bag for the whole time the bridge is on in follow mode.

## SLAM map

[`slam_map_1115.sh`](slam_map_1115.sh) starts the following:
- the LiDAR driver;
- the old `~/robot-code` bridge, which publishes `/odom` and `odom→base_link` (dead reckoning from
  commanded wheel speeds, r = 0.0757 m), with `max_speed_mps:=0.5`;
- `joy_node` and `teleop_twist_joy` (hold button 4);
- a static TF;
- `slam_toolbox` with [`slam_params_1115.yaml`](slam_params_1115.yaml).

Static TF `base_link→laser`: z = 0.715 m, roll = π (the scan is mirrored, sign −1), yaw = +6.2°.
This reproduces the follow pipeline's `bearing = −raw + 6.2°`. Verified with `tf2_echo`:
`[0, 0, 0.715]`, RPY `[180, 0, 6.2]`.

**Bug found: `params_file:=` is ignored.** Humble's `online_async_launch.py` takes
`slam_params_file:=`. With the wrong name, slam_toolbox ran on its default params
(`base_frame: base_footprint`). It logged "Failed to compute odom pose" for every scan, about 2,000
times, and never published a map. The fix is `slam_params_file:=`. After the fix there were 0
failures and `base_frame = base_link`. `transform_timeout` was also raised from 0.2 to 0.5 s. The
2026-11-07 `slam_bringup.sh` used the same wrong argument **and** a TF with no roll for a mirrored
scan. **Treat `maps/map_20261107T081703` with suspicion.**

Maps:
- `maps/map_20261115T114851`: right after the slam restart, before driving. A single-spot
  snapshot, 5.7 × 5.2 m.
- **`maps/map_20261115T115027`** (shown in [`maps/map_20261115T115027.png`](maps/map_20261115T115027.png)):
  after ~4.2 m of joystick driving. 6.3 × 6.0 m, 254 occupied and 2,571 free cells at 0.05 m.
  - No doubled walls, so scan matching did not visibly slip.
  - Walls are broken up, because at 0.7 m the scan plane hits table edges, chairs and shelves more
    than walls.
  - The pose graph (`.posegraph` / `.data`) is in the laptop copy only, at
    `robot_day_data\20261115-site01\maps\`.
- Bag `slam_map_1115`: 300 s, recorded while slam was still on the wrong params. It holds raw
  scan, odom, TF and joy data, so the map can be rebuilt offline.

The follow pipeline does not use any map, and no node reads `/map`.
