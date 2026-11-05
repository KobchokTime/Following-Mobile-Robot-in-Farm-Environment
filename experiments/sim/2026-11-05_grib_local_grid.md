# grib: a rolling local grid with A* in the follower: twin trial, 2026-11-05

> **Experiment only.** This is a "try it for fun" idea on `claude/robot/grib-local-grid`. It is not for
> `integration-hub` and it does not change the robot day (Saturday 2026-11-07, hub `d3a1a0b`). `grib` is off by
> default and no existing default changed.

The idea comes from the Thesis Desk Godot game (`tools/thesis_desk/godot_game/main.gd`, `grib_*`). The game
scores LiDAR hits per grid cell with decay, so repeated hits mark a cell as blocked. A* then plans through the
walkable cells.

## What was built (code `7926bd0`)

- **`ros2_yolo_ws/scripts/MAIN/Control/local_grid.py`.** Pure Python with no ROS imports.
  - 0.1 m cells in a 6 × 6 m window that rolls with the robot. The grid uses the dead-reckoned frame that
    `follow_stop` already keeps for the trail (`advance_pose`, `update_wheel_speed`).
  - Each cell gets +1 per scan that has a return in it. Scores decay by 2 per second and are capped at 4. A cell
    is blocked at a score of 2, so about 3 scans at 10 Hz. Returns within 0.30 m of the target are not scored.
  - Blocked cells are inflated by 0.25 m (the robot's half width is 0.235 m).
  - A* is 8-connected. Steps within a further 0.3 m of a blocked cell cost extra.
  - The first waypoint is the farthest path point within 1 m that the robot can reach in a clear straight line.
- **`follow_stop_node.py`.** New parameters: `grib` (default false) and `grib_cell_m`, `grib_size_m`, `grib_hit`,
  `grib_decay_per_s`, `grib_threshold`, `grib_max_score`, `grib_inflate_m`, `grib_clearance_m`,
  `grib_lookahead_m` and `grib_predict_s`.
  - **When it plans:** the follower asks to move forward, and either the straight line to the target is blocked
    (`segment_blocked`) or the target is at the image edge (just out of view).
  - **Where it plans to:** the target itself. At the image edge, the goal is at the LiDAR-tracked range, in the
    direction of the target's predicted position, clamped to between the edge and 90° on the reported side.
  - **How it steers:** at the waypoint.
  - **Speed:** `min(max(0, asked), path cap)`, where the path cap is the path length with the braking cap.
  - **Safety:** every command goes through `moving_turn` (the obstacle stop and the spin circle) and the per-scan
    re-check with `recheck_max_s`. The grid only proposes.
  - **No path:** the usual avoid and back-off logic applies.
- **Two rules added after blind_corner probes (before the comparison below).**
  - At the image edge, a constant-velocity prediction went stale or ended up behind the robot. The goal is now
    at the tracked range and never more than 90° to the side.
  - The A* path went round the bystander on the right while the target turned left, and turned the target out of
    view. With the target in the image, grib never steers away from a target 6° or more to the other side.
- **Tests.** `tests/test_local_grid.py` has 19 tests:
  - scoring, decay and clearing;
  - exclusion of the target's returns, and the rolling window;
  - inflation;
  - A* round a wall, keeping clear of a person, no path when boxed in, and an out-of-window goal;
  - callback-level tests through `cb_scan` and `cb_fused`: a grib command into the corridor is stopped, a grib
    turn with someone inside the 0.40 m spin circle is not sent (with a clear-circle control), and a published
    grib command is lowered by the next scan;
  - the two rules above, and that the defaults are unchanged.
- `tests/test_recovered_backup.py` now counts 30 sources in `ros2_yolo_ws/scripts` instead of 29.
- `scripts/check.py`: 258 tests pass (239 before).

## Twin comparison

- **Code and image:** `7926bd0`, one image for both settings (image id in the JSON).
- **Protocol:** realism profile, mps bridge, one run at a time, the `run_baseline.sh` protocol on 5 scenarios ×
  seeds 0–4.
- **Settings:** "off" is the robot-day configuration. "on" is the same with `grib:=true`.
- **Pass rule (unchanged):** target in view at the end, final gap ≤ 1.5 m, no contact, and in view for at least
  90% of the run.
- **Per-run rows:** `2026-11-05_grib_local_grid.json`.

| Scenario | Off: passed | Off: contacts | Off: closest (m) | Off: in view, lowest | On: passed | On: contacts | On: closest (m) | On: in view, lowest |
|---|---|---|---|---|---|---|---|---|
| `blind_corner` | 1/5 | 0 | 0.526 | 0.336 | **2/5** | 0 | 0.531 | 0.841 |
| `pass_by` | 5/5 | 0 | 0.531 | 0.942 | 5/5 | 0 | 0.578 | 1.000 |
| `turn_90` | 5/5 | 0 | 0.712 | 1.000 | 5/5 | 0 | 0.689 | 1.000 |
| `side_step` | 5/5 | 0 | 0.724 | 0.967 | 5/5 | 0 | 0.716 | 0.934 |
| `zigzag` | 5/5 | 0 | 0.654 | 0.919 | **3/5** | 0 | 0.707 | 0.849 |
| **Total** | **21/25** | **0** | | | **20/25** | **0** | | |

"Closest" is the closest approach to any person, target included, over the run (`min_person_range_m`).

`blind_corner` run by run:

| Seed | Off: in view | Off: final gap (m) | Off: closest (m) | On: in view | On: final gap (m) | On: closest (m) |
|---|---|---|---|---|---|---|
| 0 | 0.336 (lost) | 2.89 | 0.636 | 0.841 | 0.53 | 0.538 |
| 1 | 0.904 pass | 0.52 | 0.526 | 0.860 | 0.51 | 0.593 |
| 2 | 0.454 (lost) | 2.99 | 0.595 | 0.856 | 0.53 | 0.564 |
| 3 | 0.893 | 0.55 | 0.596 | 0.904 pass | 0.54 | 0.531 |
| 4 | 0.889 | 0.52 | 0.591 | 0.900 pass | 0.52 | 0.544 |

`zigzag` with grib on: s2 was in view 0.849 and s3 0.897; both fail. All five passed with grib off.

There were no contacts in any of the 50 runs.

## Conclusion

**The idea does not pay for itself in this form.**

- **`blind_corner`: a little better, not fixed.**
  - With grib on, the target was never lost: the final gap was 0.51–0.54 m on every seed, against two losses of
    2.9–3.0 m with grib off.
  - Passes went from 1/5 to 2/5. Both passes are on the line (0.904 and 0.900), and seeds 0–2 are at 0.84–0.86.
  - The limit is the one already recorded: the robot cannot turn towards the target until it has passed the
    bystander, who is inside the 0.40 m spin circle and the turning corridor. The grid finds the way round, but
    the safety layers, correctly, still forbid the turn that would keep the target in view.
- **`zigzag`: worse, 5/5 down to 3/5.**
  - Nothing blocks the way in `zigzag`. Grib fires because the target reaches the image edge.
  - There it replaces the follower's full-rate edge turn (±0.8 rad/s) with the path turn, clamped to ±2 × speed
    (about 0.3 rad/s at a crawl), so the target stays out of view longer.
  - Limiting grib to a blocked line would remove this regression, but it would also drop the edge case that
    helped `blind_corner`. This was not tried, to avoid tuning to the five scenarios.
- **`pass_by`, `turn_90`, `side_step`:** no change in passes. `pass_by` kept a little farther from the worker
  (closest 0.578 against 0.531 m).
- **Contacts:** 0 out of 25 on and 0 out of 25 off.
- **Total:** 21/25 off, 20/25 on (corrected 2026-11-05: an earlier version of this write-up said 21/25 for both). Grib trades a `blind_corner` gain of one run for a `zigzag` loss of two.

The full 22 × 5 run with grib on was not done, because the subset was not promising.

## Limits

- **Dead reckoning.** The grid sits in the dead-reckoned frame: the bridge's ramp model of commanded speed and
  the commanded turn rate, with no odometry and no check against the wheels (the T18 concern about the trail
  applies here too). Drift smears obstacles. Scores decay within about 1 s, which hides this in 30 s twin runs,
  but it has not been measured.
- **Twin only.** These are twin results with the realism profile and nothing more. Grib has not run on the robot
  and must not on the robot day.
- **Not reviewed by Codex.**
- **Runs vary.** Repeats of the same seed vary (process timing, see `2026-10-30_twin_110.md`). Two borderline
  `blind_corner` passes at 0.900–0.904 are not evidence of a real improvement in the pass rate.
- **The probe gave a different count on the same code.** The last probe used the same node code and passed
  `blind_corner` 1/5, with in view 0.871–0.926 and no target lost. So 2/5 against 1/5 is within run-to-run
  variation. Only "no target lost" held in both.
- **Tuned on the scenario it reports.** The two rules were added after looking at `blind_corner` probe runs
  (seeds 0–4, not kept). The comparison above was run once, after the code was frozen.
