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

# Arena 2 entry — following lag (Claude Code)

- **Branch:** `claude/robot/arena2-lag`, from the freeze commit `9b78f1f`.
- **Changed:** `ros2_yolo_ws/scripts/MAIN/Control/follow_stop_node.py`; tests
  `tests/test_follow_speed_feedforward.py` (new, 7 tests) and the clock stub in
  `tests/test_follow_stop_early_turn.py`. The drive bridge is untouched.

## Change

1. **Speed feed-forward.** The P-only distance control balanced where `0.55 × error` equals the
   command that keeps pace (about 0.84 for 0.3 m/s through the bridge), so about 2 m behind.
   `speed_command()` adds a feed-forward that integrates the gap error (gain 1.0, capped at 1.0,
   where the bridge saturates). It decays with a 0.3 s time constant once the robot is closer than
   the set-point, and resets on a low-confidence stop. Inside the ±0.1 m band the robot holds the
   learned speed instead of stopping. The proportional gain is 1.5, and the old gain taper at small
   errors is removed.
2. **Faster turning.** At 0.5 m behind, the target's bearing changes faster. With the old turn
   limit (0.25 rad/s), `curve_left` lost the target (final gap 2.80 m at 45°). The turn gain goes
   from 0.10 to 0.30 and the limit from 0.25 to 0.80 rad/s.

## Self-check, full frozen protocol

3 twin repeats (seeds 0, 1 and 2, every scenario on every bridge mode) and 2 Gazebo `curve_left`
runs on the `fixed` bridge. `score_entry_v2 --agent claude --base-ref 9b78f1f` gives:

| Part | Points | Detail |
|---|---|---|
| Lag | 47.87 / 50 | mean median gap: straight 0.581 m, stop_and_go 0.548 m, curve_left 0.563 m |
| Reliability | 30 / 30 | 0 failures in 5 runs. curve_left final gap: twin 0.41 m (all seeds); Gazebo 0.37 and 0.37 m |
| Behaviour | 20 / 20 | no contact in any run; target_loss stops in 0.9–1.0 s; curve_left turns |
| **Total** | **97.87 / 100** | the reference (current code) scores 66.0; scope clean |

`check.py` passes 49 tests. The judge's run is the one that counts.

## Notes for the judge and the reviewer

- **Thin margin in `crossing` on `diff_drive`.** The distractor passes 0.42–0.46 m from the
  robot's centre; the contact line is 0.40 m. On `fixed` it is 0.54–0.55 m. Following closer leaves
  less room for someone who walks between the robot and the target. This is not scored here.
- **`curve_left` on the `current` bridge** (linear only) still loses the target, as before; that
  bridge cannot turn.
- **Simulation only.** The twin and Gazebo have no wheel slip or acceleration limit. The
  feed-forward is in `/cmd_vel` units, so it adapts to the bridge's 40-RPM-per-unit scale without
  knowing the wheel radius.

# Arena 3 entry — keep following the right person (Claude Code)

- **Branch:** `claude/robot/arena3-identity`, from the freeze commit `08a7ac8`.
- **Changed:** `ros2_yolo_ws/scripts/Image/sync_fusion_node.py` and the new
  `tests/test_target_gate.py` (9 tests). The drive bridge and the controller are untouched.

## Change

1. **`TargetGate`** decides which detection is the target.
   - It locks on in the controller's start window: 0.5–1.0 m, within ±15° of the image centre.
   - Each later detection gets a cost against an alpha-beta prediction of the target's bearing
     (σ 5°) and range (σ 0.15 m). The clothing chroma adds a soft cost (σ 15) when the message
     carries it, and the target's colour is learned slowly.
   - Only detections with cost ≤ 9 are published. The gate widens while the target is unseen.
   - Old 3-value messages still work. The parameters `target_gate` and `use_chroma` switch the gate
     or the colour off, for the E7 ablation.
2. **Give way to a person in the path.**
   - Trigger: a rejected detection inside the driving corridor (±0.7 m) and nearer than the target.
   - Action: publish the target's last image position with that person's range minus 0.4 m. Target
     messages in the next 0.5 s also use it. This keeps working while the person hides the target.

## What went wrong on the way (kept for the record)

- **Self-check 1 (gate only): 94.21.**
  - Identity was 21/21, but `crossing` on `diff_drive` had contact (0.37 m).
  - Ignoring the crossing person also removed the accidental slow-down the old code got from using
    whoever was nearest.
  - While that person hid the target, nothing was published, and the robot kept its last command.
- **Self-check 2 (first give-way): 82.64.**
  - My bug: the give-way message used the other person's range even when they were **farther**
    than the target.
  - In `side_by_side` the controller therefore saw the target farther away than it was, and drove
    into it.
  - Fixed by giving way only to someone nearer than the target's own range.

## Self-check 3 (submitted), full frozen protocol

3 twin seeds × 9 scenarios × `fixed`/`diff_drive`, plus 2 Gazebo runs each of `curve_left`,
`side_by_side`, `side_by_side_same` and `stand_aside`. Scored with
`score_entry_v3 --agent claude --base-ref 08a7ac8`:

| Part | Points | Detail |
|---|---|---|
| Identity | 50 / 50 | 21/21 runs pass, mean visible share 1.0 |
| Following | 29.15 / 30 | mean median gap: straight 0.577 m, stop_and_go 0.548 m, curve_left 0.566 m; curve_left 0/5 failures |
| Behaviour | 20 / 20 | no contact; target_loss stops in 1.0 s; curve_left turns |
| **Total** | **99.15 / 100** | reference 60.6; scope clean |

Closest approach to the other person (centre to centre):

| Scenario | Closest approach |
|---|---|
| `crossing` | 0.46 m |
| `stand_aside` | 0.70 m |
| `head_on` | 0.80 m |
| `side_by_side` | 1.57 m |

`check.py` passes 72 tests. The judge's run is the one that counts.

## Notes

- `side_by_side_same` passes on geometry alone. Colour only breaks ties.
- The corridor width (0.7 m), the margin (0.4 m) and the gate σ values were tuned in the twin. They
  need checking on the robot (E5). `crossing` keeps only about 0.06 m above the contact line.
- The give-way path has no unit test of its own; it is checked through the twin runs.
