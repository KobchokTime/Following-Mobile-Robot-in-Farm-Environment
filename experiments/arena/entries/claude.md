# Arena 1 entry — Claude Code

**Branch:** `claude/robot/arena-sector-association`, from `integration-hub` `d623baf`.
**Model:** Claude Opus 5.5. **Simulation results only.**

## Root causes

The follower could not turn toward an off-center target, for two independent reasons:

1. **Sectors matched by index, not by direction** (finding 1).
   - The camera's 9 sectors split the 70° image left to right.
   - The LiDAR's 9 sectors split ±15° right to left.
   - `sync_fusion_node` used the camera sector number as the LiDAR sector number, so an
     off-center target looked up an empty sector and was dropped.
2. **Camera confidence penalised being off-center** (new). This only became visible once cause 1
   was fixed.
   - `fusion_prob_node` set `P_C = exp(-3·dx²)`. At sector 2, P_C is about 0.5 and P_fused falls below
     the controller's 0.6 threshold, so the robot stops.
   - The controller only turns at sectors ≤1 or ≥7, where P_C is about 0.16.
   - Confidence and turning were therefore mutually exclusive.

## Change (3 files in `ros2_yolo_ws/scripts/`, plus tests)

- `Image/sync_fusion_node.py`:
  - Convert the detection's `cx` into a bearing (pinhole model, 70° / 640 px, both parameters).
  - Pick the LiDAR sector whose centre angle, from `/lidar_sector_angles`, is closest.
  - Skip until those angles arrive.
- `Lidar/lidar_sectorizer_node.py`: the default field of view goes from ±15° to ±35°, so every
  detection has a LiDAR sector to match.
- `Image/fusion_prob_node.py`: the penalty becomes a `center_penalty` parameter, default 0. The
  detector only reports people it found, so being off-center is not a sign of a bad detection.
- `tests/test_sector_association.py`: 5 offline tests for bearing and sector matching.

Not changed: the controller, the drive bridge, `sim/`, the scorer and the baseline.

## Results

Official run: `python3 -m sim.twin.run_scenario --scenario all --bridge-mode both`, seed 0, in the twin
image built from this branch, then `python3 -m sim.arena.score_entry ... --base-ref d623baf`.

**99.42 / 100.** No regressions and no files out of scope.

| Check | Baseline | This entry |
|---|---|---|
| curve_left/diff_drive turned | no | **yes** |
| target in camera FOV at end | no | **yes** |
| final gap (set-point 0.5 m) | 3.19 m | **0.59 m** |
| distance travelled | 3.32 m | 5.72 m |
| other 9 runs | – | unchanged within 0.01 m; target_loss stops in 0.9–1.0 s |

Extra checks, not part of the score:

- Seeds 1 and 2 (curve_left/diff_drive): turned, final gap 0.59 m, max bearing 25.3°, the same as seed 0.
- Gazebo cross-check (curve_left/diff_drive): turned, travelled 5.74 m, final gap 0.55 m, so it
  agrees with the twin (tie-breaker 1).
- curve_left with the **current** bridge still does not turn (3.27 m, final gap 3.22 m). That is
  expected, because the real bridge drops `angular.z` (finding 2, out of scope).

## Caveats

- `center_penalty` defaults to 0, so on the robot P_C is now always 1 for any detection. If the real
  detector produces off-center false positives, the old filtering is gone. A better P_C would use
  YOLO's own box confidence, which `ros2_yolo_live.py` does not publish yet.
- The wider LiDAR window (±35°) can see crop rows at the edges. Matching by direction only reads the
  sector where the camera saw the person, but a sector median can still mix the person with the row
  behind them at long range. This needs checking on robot-day data.
