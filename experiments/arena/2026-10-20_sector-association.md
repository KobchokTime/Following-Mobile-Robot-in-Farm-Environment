# Arena 1 — camera/LiDAR sector association

**Opened:** 2026-10-20, Thai time. These rules and `sim/arena/score_entry.py` were committed
**before** either agent wrote an entry, and they do not change during the round.
**Why:** the user asked for an internal arena, to learn which agent to route which work to.
Public leaderboards don't measure this project's kind of work.
**Type:** simulation only. A winning entry still needs a robot-day check before anyone relies on it.

## Problem

Finding 1 in `experiments/sim/2026-10-20_twin_first_run.md`:
- `ros2_yolo_live.py` splits the 70° image into 9 pixel sectors, numbered left to right.
- `Lidar/lidar_sectorizer_node.py` splits only ±15° into 9 angular sectors, and in the other
  direction.
- `Image/sync_fusion_node.py` uses the camera sector index to pick the LiDAR distance.

So an off-center target is dropped, and the follower never turns (`curve_left`).

## Task

Change the robot code so that the camera detection and the LiDAR distance refer to the same
direction, and the follower turns toward the target in `curve_left` with the `diff_drive` bridge.

## Rules

1. Entry branch:
   - Claude: `claude/robot/arena-sector-association`.
   - Codex: `codex/robot/arena-sector-association`.
   - Branch from `integration-hub` at the commit that adds this file.
2. Allowed paths: `ros2_yolo_ws/scripts/`, `tests/`, your own `logs/<agent>.md`, and
   `experiments/arena/entries/<agent>.md` (a short write-up). Do **not** change `sim/`, the
   scenarios, the scorer or the baseline. Doing so disqualifies the entry.
3. Do not change the drive bridge (`zlac_joystick_bridge.py`). Its missing `angular.z` is a
   separate finding, and the `diff_drive` mode stands in for a fixed bridge.
4. Do not read the other agent's entry branch until both entries are submitted, or until
   2026-10-27, whichever comes first.
5. Submit by pushing the branch and adding a line to thread T5 in `DISCUSSION.md` with the commit SHA.
   Do not merge the entry into your workspace until the round is judged.

## Scoring (`sim/arena/score_entry.py`, 100 points)

Run the full kinematic twin in the twin image, then score the result:

```bash
docker build -f sim/docker/Dockerfile -t following-robot-twin .
docker run --rm -v "$PWD/sim_runs:/repo/sim_runs" following-robot-twin \
  python3 -m sim.twin.run_scenario --scenario all --bridge-mode both --out /repo/sim_runs
python3 -m sim.arena.score_entry sim_runs/summary.json --base-ref <arena-base-commit> --head-ref HEAD
```

- **Task, 60 points** (`curve_left`, `diff_drive` bridge):
  - The robot turns: 20.
  - The target is in the camera's field of view at the end: 20.
  - The final gap is near 0.5 m: up to 20.
- **No regressions, 40 points**, 5 off per failed check against
  `experiments/arena/baseline_2026-10-20.json`:
  - No contact in any run.
  - Distance travelled is at least 90 % of the baseline (`curve_left` excluded).
  - In `target_loss`, the robot stops within 1.5 s.
- **Scope:** a file changed outside the allowed paths scores 0.
- **Tie-breakers, in order:**
  1. The Gazebo cross-check of `curve_left`/`diff_drive` agrees with the twin.
  2. Size of the diff (smaller wins).
  3. Test coverage of the change.

The judge is the reviewer agent on `integration-hub` plus the user. Either agent may contest a
score in T5, with evidence.

## Reference

The unchanged code (baseline) scores **42.04 / 100**: no regressions, but no turn, the target out of
view, and a 3.19 m final gap.

## Results (judged 2026-10-21)

**Official result under the frozen rules: Codex wins, by 0.02 points.** The judge re-ran both entries
with the same script, 3 full runs each, alternating between entries.

| Agent | Commit | Points (3 runs) | Mean | Turned | Target in FOV | Final gap m | Regressions | Diff (code) |
|---|---|---|---|---|---|---|---|---|
| Codex | `52edffb` | 99.45 / 99.42 / 99.43 | **99.43** | yes | yes | 0.583–0.587 | 0 | sectorizer + controller, 2 files |
| Claude | `929096d` | 99.40 / 99.41 / 99.41 | 99.41 | yes | yes | 0.588–0.589 | 0 | sync + sectorizer + fusion, 3 files |

The tie-breakers do not apply, because the scores differ.

**Robustness check (not part of the score).** `curve_left` with the `diff_drive` bridge, repeated
across seeds and runs. A failure means the robot turned but lost the target and ended about 3.1 m
away.

| Version | Twin failures | Gazebo failures | Mean abs target bearing | Turn-direction flips |
|---|---|---|---|---|
| Claude entry | 0 / 18 | 0 / 5 | 12.2° | 0 |
| Codex entry | 1 / 16 | 2 / 4 | 7.4° | 0 |
| **Combined** (`e6587fd`) | **0 / 11** | **0 / 4** | **7.4°** | 0 |

Combined scores 99.43, 99.41 and 99.42 (mean 99.42), with no regressions.

Codex's failures depend on timing, because the twin runs on wall-clock time. The likely cause is
that Codex's entry keeps the off-center confidence penalty: if the turn lags, the target reaches an
edge sector, confidence drops and the robot stops.

**Decision (user, 2026-10-21): option B, combine the entries.**
- `claude/robot/sector-association-combined` takes Claude's bearing matching and confidence fix, plus
  Codex's early turn (`wide_front_radius` 1, `edge_consistency` 1) and its early-turn test.
- Codex's LiDAR index reversal is not needed with bearing matching.
- Both entry branches stay unmerged, for the record.

**Lessons for Arena 2:**
- The score was a single run of a single seed and did not measure reliability.
- Next time, score repeated runs and seeds in both the twin and Gazebo, and deduct for failures.
- Enforce `--no-renames`, an own-log-only scope, and the bridge rule in the scorer.
