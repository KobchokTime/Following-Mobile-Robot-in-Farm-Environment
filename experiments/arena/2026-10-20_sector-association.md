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

## Results

Filled in after both entries are in:

| Agent | Commit | Points | Turned | Target in FOV | Final gap m | Regressions | Gazebo agrees | Diff lines |
|---|---|---|---|---|---|---|---|---|
| Claude | | | | | | | | |
| Codex | | | | | | | | |
