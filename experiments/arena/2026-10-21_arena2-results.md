# Arena 2 — following lag: results

**Rules:** [`2026-10-21_arena2-draft.md`](2026-10-21_arena2-draft.md), frozen in `9b78f1f` (T7).
**Judge:** the `integration` role (Claude Code, Claude Opus 5.5). Both entries were run on the same
machine, in alternating order, with the frozen scorer `sim/arena/score_entry_v2.py`.
**Raw data:** [`arena2_judging/`](arena2_judging/): for each agent, `twin_s0`–`twin_s2/summary.json`,
`gz1`/`gz2/summary_gazebo.json` and `score.json`. The node logs were not committed.

| Entry | Branch @ commit | Base |
|---|---|---|
| Claude | `claude/robot/arena2-lag` @ `3848164` | `9b78f1f` |
| Codex | `codex/robot/arena2-lag` @ `64dbe7f` | `9b78f1f` |

## Verdict

By the frozen score, **the Claude entry wins: 97.84 to 60.89.**

| Part | Claude | Codex |
|---|---|---|
| Lag (50) | 47.84 | 40.89 |
| Reliability (30) | 30.0 (0 of 5 runs failed) | 0.0 (5 of 5 runs failed) |
| Behaviour (20) | 20 | 20 |
| Scope | clean | clean |
| **Total** | **97.84** | **60.89** |

- **Why Codex scored lower:** all 5 `curve_left` runs on the `fixed` bridge (3 twin, 2 Gazebo) lost
  the target from the camera view and ended about 2.7 m away, so reliability scored 0. The robot
  still turned in every run.
  - The entry note says it raised the Follow-Stop `linear_gain` default from 0.55 to 5.0.
  - The note also says Codex could not run the protocol itself: the Docker build ran out of disk space.
- **Where Claude's margins are thinner:**
  - The closest person range is 0.455 m (`crossing`, `diff_drive`, seed 0); Codex's closest is 0.630 m.
  - Final gaps are 0.36–0.42 m, below the 0.5 m set-point.
  - Neither of these is scored, and neither entry had any contact.

## Score JSONs

Command, run inside an `integration-hub` worktree at `2afe284`:
`python3 -m sim.arena.score_entry_v2 --twin twin_s0 twin_s1 twin_s2 --gazebo gz1/summary_gazebo.json gz2/summary_gazebo.json --agent <agent> --base-ref 9b78f1f --head-ref <entry SHA>`.
Re-scoring from the committed files gives the same JSON.

Claude (`3848164`):

```json
{"points": 97.84, "max_points": 100,
 "lag": {"points": 47.84, "mean_median_gap_m": {"straight": 0.58, "stop_and_go": 0.548, "curve_left": 0.566}},
 "reliability": {"points": 30.0, "runs": 5, "failures": 0},
 "behaviour": {"points": 20, "failed_checks": []},
 "twin_repeats": 3, "gazebo_runs": 2, "out_of_scope": []}
```

Codex (`64dbe7f`):

```json
{"points": 60.89, "max_points": 100,
 "lag": {"points": 40.89, "mean_median_gap_m": {"straight": 0.786, "stop_and_go": 0.728, "curve_left": 0.806}},
 "reliability": {"points": 0.0, "runs": 5, "failures": 5},
 "behaviour": {"points": 20, "failed_checks": []},
 "twin_repeats": 3, "gazebo_runs": 2, "out_of_scope": []}
```

Files changed since `9b78f1f` (`git diff --name-status --no-renames`), all within the allowed paths:
- Claude:
  - `experiments/arena/entries/claude.md` (M)
  - `logs/claude.md` (M)
  - `ros2_yolo_ws/scripts/MAIN/Control/follow_stop_node.py` (M)
  - `tests/test_follow_speed_feedforward.py` (A)
  - `tests/test_follow_stop_early_turn.py` (M)
- Codex:
  - `experiments/arena/entries/codex.md` (A)
  - `ros2_yolo_ws/scripts/MAIN/Control/follow_stop_node.py` (M)
  - `tests/test_follow_stop_early_turn.py` (M)

`python3 scripts/check.py` in each entry's checkout: Claude PASS (49 tests), Codex PASS (43 tests).

## Gaps on the `fixed` bridge (m)

Values are for seeds 0, 1 and 2; the Gazebo row is gz1 and gz2.

| Scenario | Claude median | Claude final | Codex median | Codex final |
|---|---|---|---|---|
| straight | 0.578, 0.578, 0.585 | 0.418, 0.407, 0.409 | 0.786, 0.787, 0.786 | 0.590, 0.590, 0.592 |
| stop_and_go | 0.550, 0.546, 0.549 | 0.412, 0.409, 0.413 | 0.709, 0.766, 0.710 | 0.580, 0.585, 0.585 |
| curve_left | 0.580, 0.546, 0.571 | 0.418, 0.413, 0.406 | 0.805, 0.806, 0.806 | **2.710, 2.706, 2.705** (target out of view) |
| target_loss | 0.723, 0.723, 0.718 | 0.410, 0.410, 0.411 | 0.788, 0.788, 0.787 | 0.589, 0.586, 0.591 |
| crossing | 0.601, 0.603, 0.606 | 0.409, 0.409, 0.410 | 0.783, 0.787, 0.786 | 0.583, 0.589, 0.588 |
| Gazebo curve_left | 0.514, 0.536 | 0.365, 0.365 | 0.777, 0.771 | **2.725, 2.693** (target out of view) |

Other bridges:
- `target_loss` stopped in 1.0 s on every bridge and seed for both entries. The one exception is
  Claude's `diff_drive` at seed 0, which stopped in 0.9 s.
- `curve_left` on `diff_drive` passes for both entries (final gap about 0.42 m for Claude, about 0.57 m
  for Codex).
- `curve_left` on `current` fails for both entries (2.84–2.95 m), as it does in the reference.

## Minimum person range (m)

| Run | Claude | Codex |
|---|---|---|
| crossing / current (s0, s1, s2) | 0.550, 0.549, 0.519 | 0.710, 0.719, 0.719 |
| crossing / fixed (s0, s1, s2) | 0.530, 0.571, 0.549 | 0.724, 0.709, 0.708 |
| crossing / diff_drive (s0, s1, s2) | 0.455, 0.481, 0.471 | 0.630, 0.633, 0.660 |
| other twin runs (range) | 0.545–0.687 | 0.763–0.792 |
| Gazebo curve_left / fixed (gz1, gz2) | 0.548, 0.559 | 0.747, 0.743 |
| **Overall minimum** | **0.455** (crossing, diff_drive, s0) | **0.630** (crossing, diff_drive, s0) |

No run of either entry had any contact.

## Run timeline (Thai time, 2026-10-21 to 2026-10-22)

Images were built from detached checkouts of each entry commit between 23:33:35 and 23:33:43.
- Twin images: `sim/docker/Dockerfile` with `INSTALL_MCAP=0`, tagged `twin:judge-<agent>`.
- Gazebo images: `sim/docker/Dockerfile.gazebo`, tagged `twin-gz:judge-<agent>`.

Image code hashes: the sha256 of the sorted per-file sha256 list of `ros2_yolo_ws/scripts`, `sim`,
`tests` and `scripts`. Each matches the hash of its entry's checkout, for both the twin and the
Gazebo image.

| Entry | Code hash |
|---|---|
| Claude | `62979093515f` |
| Codex | `abd3c74e45e9` |

Twin runs used `--scenario all --bridge-mode all --seed N`. Gazebo runs used
`--scenario curve_left --bridge-mode fixed`, with the default seed 0. Every run exited with code 0.

| # | Run | Start | End |
|---|---|---|---|
| 1 | twin seed 0, Claude | 23:34:02 | 23:42:29 |
| 2 | twin seed 0, Codex | 23:42:29 | 23:50:50 |
| 3 | twin seed 1, Codex | 23:50:50 | 23:59:11 |
| 4 | twin seed 1, Claude | 23:59:11 | 00:07:32 |
| 5 | twin seed 2, Claude | 00:07:32 | 00:15:54 |
| 6 | twin seed 2, Codex | 00:15:54 | 00:24:15 |
| 7 | Gazebo gz1, Codex | 00:24:15 | 00:24:56 |
| 8 | Gazebo gz1, Claude | 00:24:56 | 00:25:34 |
| 9 | Gazebo gz2, Claude | 00:25:34 | 00:26:15 |
| 10 | Gazebo gz2, Codex | 00:26:15 | 00:26:53 |

Both entries were scored at 00:27:06 (Claude) and 00:27:07 (Codex).

## Teardown tracebacks

The node logs contain Python tracebacks: 186 for Claude and 188 for Codex. Every one is a ROS
shutdown error raised after the run ends, not a run error:

| Error | Claude | Codex |
|---|---|---|
| `RCLError: Failed to publish: publisher's context is invalid` (`publish_stop` at exit) | 47 | 47 |
| `RCLError: failed to shutdown: rcl_shutdown already called` | 139 | 141 |

Both entries show them at about the same rate. They do not affect the summaries.
