# Target gate on lateral distance (HANDOFF item 18)

**Status: in progress, Claude Code.** This file is the handoff note. Anyone, Claude or Codex, can
continue from the "Next steps" list below. Every step is committed and pushed on
`claude/robot/lateral-gate`.

## Problem

- `TargetGate.cost` (`ros2_yolo_ws/scripts/Image/sync_fusion_node.py`) gates bearing with a fixed
  angular sigma of 5°.
- At close range a small sideways step is a large angle. At 0.7 m, 0.25 m is 20°.
- In the twin's `side_step`, the bearing jumps 6.5° → 27.5° in 0.3 s and the box costs 13.4 (> 9) even
  though its range is right. The gate rejects the target. The LiDAR out-of-view tracking does not
  start, because the last accepted bearing was not near the image edge, so the robot stops.
- `side_step` passes only 15/28 to 19/28 (`2026-10-27_box_range.md`, traces in `box_range_debug/`). T14
  resolved this as a separate design change.

## Design

- **Effective bearing sigma** = max(`bearing_sigma_deg`, `lateral_sigma_m` / range):
  - range is the mean of the measured and predicted ranges, at least 0.3 m;
  - this is the same as gating on lateral distance with a sigma of max(range × 5°, `lateral_sigma_m`).
- **Beyond about 1.7 m** (`lateral_sigma_m` 0.15 / tan 5°) nothing changes.
- **Closer in**, the bearing gate is never tighter than 0.15 m sideways.
  - At 0.7 m the sigma is about 12°.
  - The 6.5° → 27.5° box then costs about 3, not 13.4.
- `lateral_sigma_m` = 0 restores the old gate exactly.
- **Risk:** a second person close to the target could pass the gate more easily at short range. The
  identity and colour sets check this, and colour still adds its cost.

## Next steps (tick as done; commit after each)

- [x] 1. Code (`efa24f1`): `lateral_sigma_m` in `TargetGate`, declared as a ROS parameter in `SyncFusionNode`, and
      a docstring.
- [x] 2. Tests in `tests/test_target_gate.py`:
      - the traced `side_step` box is accepted;
      - a person 0.6 m to the side at the same range is still rejected;
      - with 0, the old cost is reproduced.
- [x] 3. `python3 scripts/check.py` passes (138). Committed and pushed.
- [ ] 4. (side_step done; regressions running) Twin (Docker, `--bridge-mode mps`, one run at a time):
      - `side_step` seeds 8–27, realism, `lateral_sigma_m` 0.15 vs 0;
      - then regressions with 0.15: identity s0–2, solo s0–2, `shade_crossing` s0–9,
        `shade_side_by_side` s0–9, and `lookalike_after_loss` s0–9 clean and realism.
      - T13 correction: `lookalike_after_loss` s0–9, clean and realism, with the re-acquisition rule really
        off (`reacquire_dist_m` / `reacquire_dist_max_m` 100).
      - Script: `experiments/sim/scripts/run_lateral_gate.sh`. Results go in
        `2026-10-28_lateral_gate.json`, via `experiments/sim/scripts/collect_runs.py`.
- [ ] 4b. `zigzag` on/off check (`zz_*`). If 0.15 hurts `zigzag`, find out why before going further.
- [ ] 5. Write the results here. Merge into `claude/workspace` and log in `logs/claude.md`.
- [ ] 6. Integration: merge into `integration-hub` and open a thread for Codex. Update HANDOFF item 18.

## Found on the way: T13's "rule off" runs had the rule on

- `TargetGate` settings were not ROS parameters. ROS 2 silently ignores an undeclared `-p`.
- So the T13 runs with `--ros-param reacquire_dist_m:=100.0 reacquire_dist_max_m:=100.0`
  (`experiments/sim/2026-10-27_hs_colour_twin.md`, "rule off" column) ran with the rule on.
  - The table's two columns are both "rule on": `lookalike_after_loss` 18/20 on.
  - There was no closed-loop "rule off" data.
- The gate-level evidence for the rule (unit tests, Codex's 6.489 m vs 2.6 m replay) and the
  borrowed-range diagnosis (debug gate log) are unaffected. So are the `box_range_from_scan`,
  `use_hs_hist` and `identity_belief` comparisons: those parameters were declared.
- **Fix:**
  - the tunables are declared (`GATE_PARAMS`);
  - `test_gate_ros_parameters_match_the_gate_defaults` keeps them in step with `TargetGate`;
  - step 4 reruns the rule-off case for real.

## How to resume

- **Code and tests** need no Docker: `python3 scripts/check.py`.
- **Twin runs** need Docker:
  1. `docker build -q --build-arg INSTALL_MCAP=0 -f sim/docker/Dockerfile -t twin:lateral .`
  2. `bash experiments/sim/scripts/run_lateral_gate.sh <out_dir>`
  3. `python3 experiments/sim/scripts/collect_runs.py <out_dir> > experiments/sim/2026-10-28_lateral_gate.json`
- **Pass rule**, as in all twin write-ups: target in view at the end, final gap ≤ 1.5 m, no contact,
  and target in view ≥ 90% of the time.
- **Without Docker** (Codex's machine): do steps 1–3. Leave step 4 to a machine with Docker, and say so
  in the thread.

## Results

Data: `2026-10-28_lateral_gate.json`, collected with `scripts/collect_runs.py`. It is updated as runs
finish.

### `side_step`, seeds 8–27, realism, on and off interleaved in one session (`efa24f1`)

| Gate | Passed | Contacts |
|---|---|---|
| `lateral_sigma_m` 0.15 (new) | **19/20** (fails seed 17) | 0 |
| `lateral_sigma_m` 0 (old) | 5/20 | 0 |

- Fisher two-sided p = 1.0e-5.
- **The old gate's 5/20 is lower than the 12–13/20 seen the day before on the same seeds** (box ranges on
  and off, `d23e7b2`).
  - Its code path is identical: `lateral_sigma_m` 0 gives the old cost, and a test checks it.
  - So `side_step` also varies a lot from session to session, plausibly with host load. Only the
    interleaved on/off comparison within this session is a fair test.

### Regressions with 0.15 (realism)

| Set | Result |
|---|---|
| Identity, seeds 0–2 | 15/15, no contact |
| Solo, seeds 0–2 | 27/30, no contact. **`zigzag` fails all 3 seeds** |

- `zigzag` passed 4/5 with the old gate on seeds 3–7 (`2026-10-27_box_range.md`).
- A within-session check is queued: `zigzag` seeds 0–9 with 0.15 vs 0, interleaved (`zz_*` in the run
  script).

| `shade_crossing`, seeds 0–9 | 9/10 (seed 7), no contact |
| `shade_side_by_side`, seeds 0–9 | 10/10 |
| `lookalike_after_loss`, clean and realism, seeds 0–9 | 20/20, no contact; in clean runs the robot never turns (max bearing 0°) |

### T13 correction: the re-acquisition rule really off

- `lookalike_after_loss` with `reacquire_dist_m` and `reacquire_dist_max_m` 100: **0/20** (clean 0/10, realism
  0/10). 18 of the 20 runs end in contact; peak target bearing 180°.
  - The robot follows the look-alike.
  - With the rule on: 20/20, as in the table above.
- **This is the closed-loop evidence T13 lacked.**
