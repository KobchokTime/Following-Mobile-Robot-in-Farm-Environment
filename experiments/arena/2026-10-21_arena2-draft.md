# Arena 2 — following lag (DRAFT)

**Status: draft.** Codex can object in `DISCUSSION.md` (T7). The rules are frozen only when both
agents reply `agree`, and the commit that freezes them is named there. No entry may start before then.
**Type:** simulation only.

## Problem

Finding 3 in `experiments/sim/2026-10-20_twin_first_run.md`: the follow controller is
proportional-only. While the target walks at 0.3 m/s, the gap grows to about 1.6–2.0 m,
against a 0.5 m set-point.

The real drive bridge now forwards `angular.z` (the `fixed` mode in the twin). With it, the robot
follows `curve_left`, but it trails behind. The bridge maps `linear.x` at 40 RPM per unit, so a
command of 1.0 gives about 0.36 m/s with a 0.085 m wheel. That unit mismatch is part of the lag.

## Task

Make the robot keep the gap close to 0.5 m while the target walks. It must not lose the target,
touch a person, or stop late when the target disappears.

## What changed from Arena 1 (its lessons)

1. **Repeated runs:**
   - At least 3 full twin runs: `--scenario all --bridge-mode all`, seeds 0, 1 and 2.
   - At least 2 Gazebo runs of `curve_left` on the `fixed` bridge.
2. **Reliability is scored:** the share of `curve_left` runs that end with the target in view and
   within 1.5 m.
3. **The scorer enforces scope**, all checked with `--no-renames`:
   - You may write only your own log.
   - The drive bridge is protected. Its unit fix is a hardware decision for the user, so it is out
     of scope here.
   - `sim/`, the scorers and the baselines are protected.
4. **The judge is not a competitor:** the `integration` role runs the scorer for both entries, on
   the same machine and in alternating order, and posts the raw `summary.json` files.

## Scoring (`sim/arena/score_entry_v2.py`, 100 points, `fixed` bridge)

- **Lag, 50 points.** The mean median gap in `straight`, `stop_and_go` and `curve_left` is compared
  with 0.5 m, linearly down to 0 at 1.5 m of error.
- **Reliability, 30 points.** The share of passing `curve_left` runs, twin and Gazebo together.
- **Behaviour, 20 points.** 5 points off for each failed check:
  - any contact;
  - `target_loss` not stopping within 1.5 s;
  - `curve_left` not turning.
- **Scope:** any violation scores 0.

## Rules

- Branches: `claude/robot/arena2-lag` and `codex/robot/arena2-lag`, from the freeze commit.
- Allowed paths: `ros2_yolo_ws/scripts/` except the drive bridge, `tests/`, your own
  `logs/<agent>.md`, and `experiments/arena/entries/<agent>.md`.
- Don't read the other agent's branch until both entries are in.
- Post your commit SHA in T7. Entries stay unmerged until judged.

## Reference: current code (`integration-hub` at `8afdae0`), not an entry

The scorer was run on the full minimum protocol: 3 twin repeats (seeds 0, 1 and 2, every scenario
on every bridge mode) and 2 Gazebo runs of `curve_left` on the `fixed` bridge. The raw summaries
and the score are in `baseline_arena2_2026-10-21.json`. The earlier 65.9 came from 1 twin repeat,
which the scorer now refuses.

| Part | Points | Detail |
|---|---|---|
| Lag | 16.0 / 50 | mean median gap: straight 1.66 m, stop_and_go 1.29 m, curve_left 1.61 m |
| Reliability | 30 / 30 | 0 failures in 5 runs (curve_left final gap: twin 0.79 m in all 3 seeds; Gazebo 0.75 and 0.75 m) |
| Behaviour | 20 / 20 | no contact; target_loss stops in 1.0 s; curve_left turns |
| **Total** | **66.0 / 100** | |

## Input validation (from Codex's T7 review)

The scorer checks the minimum protocol before it scores. It exits with code 2, and gives no points,
unless it gets:

- at least 3 twin repeats with distinct seeds, each holding every scenario on every bridge mode
  exactly once;
- at least 2 Gazebo `curve_left` runs on the `fixed` bridge.

Tests: `tests/test_arena2_scorer.py`.

## Open questions for Codex (T7)

Codex answered all three on 2026-10-21: keep the unit fix out of scope, keep the 1.5 m fall-off,
and leave `crossing` for Arena 3. The draft keeps these choices.

1. Should the bridge's unit fix (RPM per m/s from the real wheel radius) stay out of scope? This draft
   says yes, because changing it changes the real robot's speed.
2. Is a 1.5 m fall-off for the lag score right, or too lenient?
3. Should Arena 2 include the `crossing` scenario with identity selection, or leave that for Arena 3?
