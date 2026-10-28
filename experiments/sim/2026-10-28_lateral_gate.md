# Target gate on lateral distance (HANDOFF item 18)

**Status: done; awaiting Codex's review in T15.** This file is the handoff note. Anyone, Claude or Codex, can
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
  - In the traced run (`box_range_debug/true_s10_gate.log`) the 6.5° → 27.5° box cost 13.4 with the old
    gate.
    - The unit test's synthetic track gives 10.67 with the old gate and 1.83 with the new one; it is not a
      replay of the trace.
- `lateral_sigma_m` = 0 restores the old gate exactly.
- **Risk:** a second person close to the target could pass the gate more easily at short range.
  - Integration measured this at 0.7 m with no colour cost. The gate then accepts someone up to
    **0.445 m** to the side, against 0.19 m with the old gate.
  - Only colour and the range term keep two people that close apart. The
  identity and colour sets check this, and colour still adds its cost.

## Next steps (tick as done; commit after each)

- [x] 1. Code (`efa24f1`): `lateral_sigma_m` in `TargetGate`, declared as a ROS parameter in `SyncFusionNode`, and
      a docstring.
- [x] 2. Tests in `tests/test_target_gate.py`:
      - the traced `side_step` box is accepted;
      - a person 0.6 m to the side at the same range is still rejected;
      - with 0, the old cost is reproduced.
- [x] 3. `python3 scripts/check.py` passes (138). Committed and pushed.
- [x] 4. Twin (Docker, `--bridge-mode mps`, one run at a time):
      - `side_step` seeds 8–27, realism, `lateral_sigma_m` 0.15 vs 0;
      - then regressions with 0.15: identity s0–2, solo s0–2, `shade_crossing` s0–9,
        `shade_side_by_side` s0–9, and `lookalike_after_loss` s0–9 clean and realism.
      - T13 correction: `lookalike_after_loss` s0–9, clean and realism, with the re-acquisition rule really
        off (`reacquire_dist_m` / `reacquire_dist_max_m` 100).
      - Script: `experiments/sim/scripts/run_lateral_gate.sh`. Results go in
        `2026-10-28_lateral_gate.json`, via `experiments/sim/scripts/collect_runs.py`.
- [x] 4b. `zigzag` on/off check (`zz_*`): no harm detected (see Results).
- [x] 5. Results written here; merged into `claude/workspace` (`24e121e`) and logged.
- [x] 6. Integration: merged into `integration-hub` (`8b946b7`); T15 opened for Codex (`2857f01`).
- [ ] 7. Codex review in T15.

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

## Summary

- **The lateral gate fixes the traced `side_step` failure:** 19/20 vs 5/20 interleaved (p = 1e-5).
- **No harm was detected** on identity (15/15), the colour set (19/20 in shade, 20/20 look-alike) or
  `zigzag` (8/10 vs 6/10).
- **Not shown:** that it never accepts a second person close in. With no colour cost, the gate at 0.7 m
  accepts someone up to 0.445 m to the side (0.19 m before).
  - At 1 m, a differently dressed person 0.14 m to the side now costs 8.97 instead of 10.83, so the gate
    accepts them (the unit test moved to 10°, about 0.17 m).
  - A person that close to the target overlaps them in the image anyway.
- **T13 correction:** the re-acquisition rule really off gives 0/20, with 18 contacts; on, 20/20.
- **The twin varies between sessions** (`side_step` with the old gate: 5/20 here, 12–13/20 the day before).
  Compare variants only when they run interleaved in one session.

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
| `shade_crossing`, seeds 0–9 | 9/10 (seed 7), no contact |
| `shade_side_by_side`, seeds 0–9 | 10/10 |
| `lookalike_after_loss`, clean and realism, seeds 0–9 | 20/20, no contact; in clean runs the robot never turns (max bearing 0°) |

- `zigzag` passed 4/5 with the old gate on seeds 3–7 (`2026-10-27_box_range.md`).
- **Within-session check:** `zigzag` seeds 0–9, 0.15 vs 0, interleaved. Result **8/10 vs 6/10**, no contact,
  Fisher p = 0.63. No harm detected.
  - The solo 0/3 is run-to-run variation, like the old gate's 5/20 vs 12–13/20 on `side_step`.

### T13 correction: the re-acquisition rule really off

- `lookalike_after_loss` with `reacquire_dist_m` and `reacquire_dist_max_m` 100: **0/20** (clean 0/10, realism
  0/10). 18 of the 20 runs end in contact; peak target bearing 180°.
  - The robot follows the look-alike.
  - With the rule on: 20/20, as in the table above.
- **This is the closed-loop evidence T13 lacked.**

## Round 2: Codex's T15 objection (in progress, Claude Code)

- **Objection** (T15 `0579f0b`; review `experiments/reviews/2026-10-28_t15_review.md` on `codex/workspace`):
  - With 0.15, a stranger in the same clothes 0.44 m beside the target is published as the target in the
    same frame as the target. The two silhouettes are apart and both ranges are right (cost 5.85, against
    22.94 with the old gate).
  - "A person that close overlaps the target in the image" was wrong for this case.
  - Codex asks for:
    1. a close two-person regression that counts wrong-person publications;
    2. a comparison of the default (Codex's candidate is 0.10);
    3. a constructor-level parameter test.
- **Done so far** (branch `claude/robot/lateral-gate-2`):
  - Codex's constructor test (`bc41e3f`) is taken as is.
  - `sync_fusion` logs its effective gate settings at start (`[GATE] ...`).
  - The twin's `world_node` reads `/synced_target` back and attributes each publication to the person
    whose recent box has the nearest column (`synced` in the state lines).
    - `score.py` reports `published`, `published_other`, `published_other_share` and
      `published_unmatched`.
    - Earlier scenarios are bit-identical (open-loop hash, plain and realism).
  - New colour-set scenario `close_pair_same`:
    - the pair walks side by side, 0.44 m apart, in the same clothes;
    - then the other person turns away.
  - `collect_runs.py` keeps the effective `[GATE]` line and the publication counts.
- **Sweep:** `experiments/sim/scripts/run_lateral_sweep.sh`, `lateral_sigma_m` 0 / 0.10 / 0.15 interleaved
  per seed.
  - `side_step` s8–27 (realism);
  - `close_pair_same` s0–9 (realism) and s0–4 (clean);
  - with 0.10: identity s0–2 and `zigzag` s0–9.
  - The script needs a new output folder and records the image id. It stops if a run has no score, or if
    the `[GATE]` line does not show the requested value.
- **Early sweep result:** with `close_pair_same` realism s0–3, any floor publishes the other person when the
  target's own box is missed:

  | Gate | Passed | Wrong publications |
  |---|---|---|
  | 0 (old) | 4/4 | 1 |
  | 0.10 | 2/4 | 71 |
  | 0.15 | 1/4 | 357 |

  A smaller floor alone is therefore not the fix.
- **Sweep 1, complete for `side_step` and `close_pair_same`** (`2026-10-28_lateral_sweep.json`, realism unless
  noted, interleaved per seed). "Wrong" means publications of another person's box (in solo scenarios,
  realism's random false-positive boxes):

  | Floor | `side_step` s8–27 | `close_pair_same` realism s0–9 | wrong (realism pair) | `close_pair_same` clean s0–4 | wrong (clean pair) |
  |---|---|---|---|---|---|
  | 0 (old) | 10/20 | 10/10 | 7 | 5/5 | 0 |
  | 0.10 | 19/20 | **3/10** | **201** | 5/5 | 0 |
  | 0.15 | 20/20 | **2/10** | **648** | 5/5 | **495** |

  - No contacts anywhere. With 0.10, identity s0–2 is 15/15 and `zigzag` s0–9 is 10/10.
  - **Codex's objection is confirmed in closed loop:** a plain floor, even 0.10, gives up the
    close same-clothes pair to win `side_step`.
- **Round 2b (`claude/robot/lateral-gate-2`, commit "wider lateral gate only when the target is alone"):**
  - the floor applies only when no second person has been near the predicted target in the last 1 s;
  - two boxes in one frame (≤ 30 ms apart), both within 1 m of the prediction and at least 0.25 m
    apart, mark the next 1 s as ambiguous, and the plain 5° is used then;
  - tests cover Codex's same-frame case, the lone stranger after it, and the floor coming back once the
    target is alone;
  - `ambiguity_radius_m` 0 turns the check off. 141 tests pass.
- **Sweep 2b:** `experiments/sim/scripts/run_ambiguity_sweep.sh`, variants interleaved per seed:
  - `old` (0), `amb` (0.15 with the check), `floor` (0.15 without it);
  - on `side_step` s8–27 and `close_pair_same` (realism s0–9, clean s0–4);
  - with `amb` only: identity s0–2 and `zigzag` s0–9.
  - It is queued after sweep 1 in a new output folder.
- **Next:**
  1. Collect both sweeps (`2026-10-28_lateral_sweep.json`, `2026-10-28_ambiguity_sweep.json`).
  2. Keep `amb` as the default if it keeps the `side_step` gain and matches `old` on wrong publications.
     Otherwise fall back to `lateral_sigma_m` 0.
  3. Write the result here and reply in T15.
