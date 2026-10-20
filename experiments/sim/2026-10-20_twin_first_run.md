# Offline twin — first run, 2026-10-20

**Type:** simulation (offline twin, `sim/`). These are not results from the robot. The detections
come from geometry, not from YOLO on images. The wheel radius (0.085 m) and track width
(0.40 m) are assumptions.

**Setup:** 5 scenarios × 2 bridge modes, seed 0, run through the **unmodified** chain:
`lidar_sectorizer_node` → `sync_fusion_node` → `fusion_prob_node` → `MAIN/Control/follow_stop_node`.
Reproduce with `docker run --rm -v "$PWD/sim_runs:/repo/sim_runs" following-robot-twin`
(see `sim/README.md`). Two consecutive full runs gave the same table to within 0.1 m.

| Scenario | Bridge | Travelled m | Median gap m | Final gap m | Max target bearing ° | Turned | Stop latency s |
|---|---|---|---|---|---|---|---|
| straight | current | 5.92 | 1.67 | 0.88 | 0 | no | – |
| straight | diff_drive | 6.21 | 1.04 | 0.59 | 0 | no | – |
| stop_and_go | current | 4.46 | 1.30 | 0.84 | 0 | no | – |
| curve_left | current | 2.40 | 2.01 | 3.85 | 40 | no | – |
| curve_left | diff_drive | 3.32 | 1.19 | 3.19 | 50 | no | – |
| target_loss | current | 5.88 | 1.70 | 0.92 | 0 | no | 1.00 |
| crossing | current | 5.92 | 1.67 | 0.88 | 0 | no | – |

The table shows 7 of the 10 runs. The `diff_drive` rows left out (`stop_and_go`, `target_loss`, `crossing`) follow the `straight`/`diff_drive` pattern. All 10 are in `sim_runs/summary.json` and the CI artifact. There was no contact with any person in any run. "Gap" is the distance from the robot to the target's surface;
the controller's set-point is 0.5 m.

## Findings

1. **The follower cannot follow a target that moves off-center.** In `curve_left`, even with
   turning enabled (`diff_drive`), the controller only ever received sectors 3–4. Commands
   stopped at t = 14.8 s, when the target was at 26° and 1.06 m away, and the robot never turned.
   - The camera node splits the full 70° image into 9 sectors.
   - The LiDAR sectorizer splits only ±15° into 9 sectors, and its sector 0 is the right-most
     angle, while the camera's sector 0 is the left-most column.
   - `sync_fusion_node` uses the camera sector index to pick the LiDAR distance. An off-center
     target therefore looks up an empty LiDAR sector, gets `inf`, and the frame is dropped.
2. **The current drive bridge ignores `angular.z`** (`MAIN/Control/zlac_joystick_bridge.py`,
   "not using angular.z yet"). With that bridge the robot cannot turn at all.
3. **Following lags at walking speed.** The controller is proportional-only. At 0.3 m/s the gap
   grows to about 2.0 m while the target walks with the current bridge (median over the whole run 1.67 m,
   including the start and the final stop), and to about 1.0 m with `diff_drive`, against a 0.5 m set-point.
   The current bridge maps `linear.x` at 40 RPM per unit, which with a 0.085 m wheel is 0.36 m/s
   per 1.0 commanded, so the command is not in m/s.
4. **Target loss behaves as intended.** When the detector went blind, the robot stopped after
   1.0 s (the bridge's command timeout) and travelled 0.24 m in that second.
5. **The crossing person had no effect here,** because the twin's distractor never sits in a sector
   that survives the sync step. The real YOLO node publishes every person it sees, one message
   each, so identity selection is still untested.

## Next

- Decide how camera and LiDAR sectors should correspond, for example by mapping the camera
  bearing to a LiDAR angle. This is a `robot` role change, and re-running the twin will show the
  effect.
- Measure the wheel radius and track width on the robot, then update `sim/twin/world.py`.

## Cross-check in Gazebo (same day)

The same scenarios were re-run in Ignition Gazebo (Fortress), headless and with the GUI, using
`sim/gazebo/`. This time `/scan` came from Gazebo's `gpu_lidar` (mounted at 180°), the poses came
from Gazebo, and everything ran on simulation time. The robot nodes and the bridge model were the
same.

| Scenario | Bridge | Travelled m (twin → Gazebo) | Median gap m | Max bearing ° | Turned | Stop latency s |
|---|---|---|---|---|---|---|
| straight | current | 5.92 → 5.96 | 1.67 → 1.63 | 0 | no | – |
| curve_left | diff_drive | 3.32 → 3.29 | 1.19 → 1.19 | 50 → 50 | no | – |
| target_loss | current | 5.88 → 5.92 | 1.70 → 1.67 | 0 | no | 1.00 → 1.00 |

The two simulators agree to within 0.05 m, so findings 1–4 do not depend on the kinematic
model. Videos: run `sim/gazebo/record_video.sh <scenario> <bridge>`.
