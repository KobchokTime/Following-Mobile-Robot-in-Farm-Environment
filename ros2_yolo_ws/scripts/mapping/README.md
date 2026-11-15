# Mapping-only SLAM and the live map viewer

Use this to build a map and watch the scanned and unknown areas update live, without the
wheels ever being driven.

| File | Runs on | What it does |
|---|---|---|
| `slam_mapping_only.sh` | robot | LiDAR driver, static TFs, slam_toolbox. No drive bridge, joystick or teleop. |
| `slam_params_mapping_only.yaml` | robot | slam_toolbox params for running with no wheel odometry |
| `lidar_health.py` | robot | Fails if `/scan` is degraded (copied from `20261115-site01`); the start script runs it |
| `live_slam_viewer.py` | PC | Local page at http://127.0.0.1:8772/ that subscribes read-only to `/map` and `/scan` over SSH and saves a fresh live map |

## Run

On the robot, the files go in `~/slam_mapping_only/`. Use LF line endings.

```bash
~/slam_mapping_only/slam_mapping_only.sh          # Ctrl-C stops everything
~/slam_mapping_only/slam_mapping_only.sh stop     # stops a run that was started detached
```

On the PC:

```bash
py -3 ros2_yolo_ws/scripts/mapping/live_slam_viewer.py
```

Then open http://127.0.0.1:8772/. Set `SLAM_VIEW_PORT` if 8772 is already taken.

Save writes `live_map_<local time>.pgm`, `.yaml` and `.json` (provenance) to
`%USERPROFILE%\Documents\robot_day_data\slam_live_captures\`. It only saves while a live `/map` is
still arriving (one received within 12 s; `SLAM_LIVE_MAX_AGE_S`). When the archive is shown, or the
map is stale, Save returns HTTP 409.

## Why mapping-only uses a static identity `odom→base_link`

slam_toolbox needs an `odom→base_link` transform. Three ways to provide it were considered:

1. **A static identity `odom→base_link` (chosen).** This starts no process that can drive the
   wheels, so the robot pose comes only from scan matching. The params change so that this works:
   - `minimum_travel_distance` and `minimum_travel_heading` go from 0.5 to 0.0. An identity odom
     never "moves", so with the old values only the first scan would ever be added.
   - `minimum_time_interval` goes to 0.3, `correlation_search_space_dimension` to 0.8, and
     `map_update_interval` to 2.0.

   The limitation: the robot has to be moved slowly by hand (pushed or carried), at less than about
   0.3 m/s and 30°/s. Moving a robot by hand needs the operator's OK.
2. **Laser odometry.** `rf2o_laser_odometry` is not installed on the robot (`ros2 pkg prefix`
   failed on 2026-11-15). Option 1 already does scan-to-map matching, so installing it would add
   little.
3. **The drive bridge with motor writes disabled.** Rejected. The old bridge's odometry is dead
   reckoning from *commanded* wheel speeds, so with writes disabled it publishes nothing useful.
   It would still open the motor serial port, which is a risk with no benefit.

The script refuses to start (exit 2) if a process matching
`zlac|drive_bridge|joystick_bridge|teleop|joy_node|Follow_stop_node|start_bridge|start_follow|slam_map_1115|slam_bringup`
is running, or if slam_toolbox is already up. It also makes sure nothing else publishes
`odom→base_link`. Do **not** use `~/slam_bringup.sh` or `~/slam_map_1115.sh` for viewing. Both
depend on a drive bridge, and `slam_bringup.sh` also has the wrong `params_file:=` and no mirror
roll.

Pitfalls carried over from 2026-11-15:
- Humble's `online_async_launch.py` takes `slam_params_file:=`. If you pass `params_file:=`
  instead, it is silently ignored and the defaults are used (`base_frame: base_footprint`).
- The scan is mirrored. The TF `base_link→laser` is z 0.715, roll π, yaw +0.10821
  (bearing = −raw + 6.2°).
- The YDLidar driver sometimes starts degraded. The script runs `lidar_health.py` and stops if
  it fails.

## Review of Codex's prototype (2026-11-15)

Source: `%USERPROFILE%\.codex\visualizations\2026\10\28\01a18067-...\lidar-live-view\live_slam_viewer.py`.
Its SHA-256 `D3CE8FDEF1EA765754D1DA0884CAB90DC06C78B8990341422386DC64FF2790BA` matches the
handoff. The prototype was safe: it only subscribes (to `/map`, `/scan` and TF), has no publisher
and no motor path, binds to localhost only, uses SSH `BatchMode` and `StrictHostKeyChecking=yes`,
and does not save the archive.

These defects were fixed in this copy:

| # | Prototype | Effect | Fix |
|---|---|---|---|
| 1 | Placed scan points on the map using only the yaw of `map→laser` | The laser frame has roll π, so the overlay was **mirrored**. On the robot, 37% of points landed on walls, against 100% with the fix | The full quaternion is applied on the robot side (`TF_MATH`, tested) |
| 2 | Treated `/map` as live only if it was less than 5 s old | slam_toolbox publishes every `map_update_interval` (5 s in the 1115 params), so the live state and Save flickered | The live window is now 12 s (configurable); mapping-only publishes every 2 s |
| 3 | Drew the polar scan in the raw laser frame, labelled "front" | Left and right were swapped | Points are drawn in `base_link` (forward is up), with a labelled raw fallback |
| 4 | Remote subscriber ignored the end of its SSH session; ssh.exe outlived a killed viewer | Read-only subscribers piled up on the robot (two were found) | Remote watchdog on the parent PID, a Windows job object (kill-on-close), and the child is killed on error |
| 5 | Save had no CSRF or Host check | Any web page could POST to it | Save requires an `X-Slam-Viewer` header, and requests must be to the `127.0.0.1` or `localhost` Host |
| 6 | Saved next to the script, with no provenance | Captures could be mixed up with the archive | Saves go to a separate `slam_live_captures/` folder with a `live_map_` prefix and a JSON sidecar (map stamp, age, cell counts) |
| 7 | Fixed node name | Duplicate node names on the graph | The name now includes the PID |

## Offline tests (`tests/test_live_slam_viewer.py`, 18 tests, no ROS and no SSH)

| What | How |
|---|---|
| `/map` QoS | `REMOTE_CODE` runs against stubs of rclpy, the message types and tf2_ros. The `/map` subscription must be RELIABLE, TRANSIENT_LOCAL and depth 1 (so it gets slam_toolbox's latched map). `/scan` uses the sensor-data QoS. Only `/map` and `/scan` are subscribed, and there is no publisher |
| Placing `/scan` through TF | Same stubs, with the 2026-11-15 mount (z 0.715, roll π, yaw 0.10821) and a robot at (1, 2) facing +y. Points in `base_link` must come out at bearing = −raw + 6.2°, and map points must land where hand geometry puts them. With no TF, the scan is sent raw and the map points and pose are null |
| PGM orientation | Uses the real `map_saver` output `tests/fixtures/slam/map_20261115T115027` (126 × 120). It reads 254 occupied and 2,571 free cells. ROS row 0 must equal the **last** PGM row, and writing the grid back must give exactly the bytes `map_saver` wrote. A `# CREATOR` comment header must also parse |
| Stale state | Save works on a fresh live map. With a map older than `LIVE_MAX_AGE_S` (which must be more than 5 s), Save returns 409. With the archive shown, Save returns 409 and nothing is written. Malformed maps are ignored |
| PGM/YAML save | The trinary thresholds (65/25) and the top-down rows, plus the YAML and JSON sidecar. A live capture is never picked up as the archive |
| Save hardening | No `X-Slam-Viewer` header returns 403. A foreign `Host` returns 403 |

Still needs a live `/map`, and is not covered offline:
- slam_toolbox's real QoS and its republish period on the running graph, and how the viewer behaves across an SSH reconnect.
- The canvas drawing (JavaScript): map orientation on screen, the overlay and the pose arrow.
- The map growing while the robot is moved by hand, and Save on that growing map.
- How the robot side copes with the alternating 384/386 beam scans.

## Validation on the robot (2026-11-15 17:02–17:06, robot stationary, no motion)

> Scope note: this one stationary run, with only the LiDAR spinning, happened *before* the user's
> later instruction to work offline only. No further robot runs were made after that instruction.

Evidence is in `experiments/hardware-runs/20261115-site01/slam_live_viewer/`.

- The bringup started: `lidar_health` PASSED (31 scans, 10.3 Hz, 80% valid beams). The static TFs,
  slam_toolbox, `odom→base_link` from the static identity, and no drive bridge, joystick or teleop
  were all up.
- TF `map→laser` resolves to `[0, 0, 0.715]`, RPY `[3.142, 0, 0.108]`. There were 0 "Failed to
  compute odom pose" messages.
- `/map` was published every 2 s (header stamps 1794737046, 048, … 056) at 238 × 92 cells.
- Viewer on port 8773: LIVE status, and the overlay sits on the walls (screenshot
  `viewer_live_8773.jpg`). Save wrote `live_map_20261115T170447.{pgm,yaml,json}`: 28.4% known,
  484 occupied and 5,727 free cells, received 0.78 s after it was published.
- Negative checks:
  - POST without the header: 403.
  - After stopping SLAM, the viewer showed the map as stale (17 s), and Save returned 409.
  - The script refused to start when a fake `zlac` process was running (exit 2, nothing started).
  - `stop` ended every process.

### Push test 1 (17:12–17:19, user's OK): the robot barely moved

The robot was pushed by hand with the mapping-only bringup running. Save worked on the live map
(`live_map_20261115T171845`, 30.4% known), and known cells grew from 5,732 to 6,679. **The SLAM
pose never left (0, 0, 0):** 433 graph nodes were added, all at the start. The user confirmed that the
robot barely moved, so tracking during real motion is still untested.
Evidence: `experiments/hardware-runs/20261115-site01/slam_live_viewer/push_test_1/`.

The script's motor guard used to flag its own launching shell, because an `ssh "bash -c ..."`
command line contained the word `zlac`. The guard now skips its own ancestor processes. It was
re-checked: a real `zlac_*` process is still refused (exit 2).

Not tested yet: the map growing while the robot is moved, because that needs the operator's OK
to push or carry the robot.

Known issue: the T-mini Pro sends scans with 384 and 386 beams in turn. slam_toolbox drops the
ones that do not match ("LaserRangeScan contains 386 range readings, expected 384"), so only about
half of the scans are used. That was enough on 2026-11-15. A scan normalizer would fix it.
The driver also exits with code −6 when it gets SIGINT. This happens during shutdown and does no
harm.
