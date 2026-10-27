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

- [ ] 1. Code: `lateral_sigma_m` in `TargetGate`, declared as a ROS parameter in `SyncFusionNode`, and
      a docstring.
- [ ] 2. Tests in `tests/test_target_gate.py`:
      - the traced `side_step` box is accepted;
      - a person 0.6 m to the side at the same range is still rejected;
      - with 0, the old cost is reproduced.
- [ ] 3. `python3 scripts/check.py` passes. Commit and push.
- [ ] 4. Twin (Docker, `--bridge-mode mps`, one run at a time):
      - `side_step` seeds 8–27, realism, `lateral_sigma_m` 0.15 vs 0;
      - then regressions with 0.15: identity s0–2, solo s0–2, `shade_crossing` s0–9,
        `shade_side_by_side` s0–9, and `lookalike_after_loss` s0–9 clean and realism.
      - Script: `experiments/sim/scripts/run_lateral_gate.sh`. Results go in
        `2026-10-28_lateral_gate.json`, via `experiments/sim/scripts/collect_runs.py`.
- [ ] 5. Write the results here. Merge into `claude/workspace` and log in `logs/claude.md`.
- [ ] 6. Integration: merge into `integration-hub` and open a thread for Codex. Update HANDOFF item 18.

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

(none yet)
