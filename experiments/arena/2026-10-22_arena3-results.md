# Arena 3 — keep following the right person: results

**Rules:** [`2026-10-22_arena3-draft.md`](2026-10-22_arena3-draft.md), frozen in `08a7ac8` (T8).
**Judge:** the `integration` role (Claude Code, Claude Opus 5.5). Both entries ran on the same machine,
in alternating order, and were scored with the frozen scorer `sim/arena/score_entry_v3.py`.
**Raw data:** [`arena3_judging/`](arena3_judging/). For each agent: `twin_s0`–`twin_s2/summary.json`,
`gz1`/`gz2/summary_gazebo.json` and `score.json`. The node logs are not committed.

| Entry | Branch @ commit | Base |
|---|---|---|
| Claude | `claude/robot/arena3-identity` @ `191d2c1` | `08a7ac8` |
| Codex | `codex/robot/arena3-identity` @ `4d22f41` | `08a7ac8` |

## Verdict

By the frozen score, **the Claude entry wins: 99.13 to 94.13.**

| Part | Claude | Codex |
|---|---|---|
| Identity (50) | 50.0 (21/21 runs pass, mean visible share 1.0) | 50.0 (21/21 runs pass, mean visible share 1.0) |
| Following (30) | 29.13 | 29.13 |
| Behaviour (20) | 20 | 15 (contact in at least one run) |
| Scope | clean | clean |
| **Total** | **99.13** | **94.13** |

- **Why the scores differ.** In all 3 seeds of `crossing` on the `diff_drive` bridge, the Codex entry
  came into contact with the crossing person: 0.379, 0.378 and 0.381 m centre to centre, against a
  0.4 m contact threshold. Identity counts only the `fixed` bridge, so these runs cost no identity
  points. The behaviour contact check covers both bridges, which cost 5 points.
- **Same failure in Claude's development.** Claude's entry note records that its first self-check had
  the same contact (`crossing` on `diff_drive`, 0.37 m). It was fixed by giving way to a person who is
  inside the driving corridor (±0.7 m) and nearer than the target. While that person is there, the
  entry publishes the target's last image position with that person's range minus 0.4 m, and it keeps
  doing so while the person hides the target.
- **Following is equal.** Both entries run the hub's Arena 2 controller, and their means round to the
  same values. The per-run values differ; for example, `straight` was 0.5817, 0.5809 and 0.5821 m for
  Claude against 0.5799, 0.5816 and 0.5846 m for Codex.

**Notes for both entries:**
- Gazebo final gaps are 0.36–0.39 m for both entries, below the 0.5 m set-point.
- Codex could not run the protocol itself: its disk was full and it had no `rclpy`. Its entry note
  claims no score.
- Claude's closest approach to the crossing person on `diff_drive` was 0.517 m, the smallest margin in
  its runs.

## Score JSONs

Command, run inside an `integration-hub` worktree at `167e0c0`:
`python3 -m sim.arena.score_entry_v3 --twin twin_s0 twin_s1 twin_s2 --gazebo gz1/summary_gazebo.json gz2/summary_gazebo.json --agent <agent> --base-ref 08a7ac8 --head-ref <entry SHA>`.
Re-scoring from the committed files gives the same JSON.

Claude (`191d2c1`):

```json
{"points": 99.13, "max_points": 100,
 "identity": {"points": 50.0, "runs": 21, "passed": 21, "mean_visible_share": 1.0,
   "passed_per_scenario": {"crossing": "3/3", "side_by_side": "5/5", "side_by_side_same": "5/5", "head_on": "3/3", "stand_aside": "5/5"}},
 "following": {"points": 29.13, "mean_median_gap_m": {"straight": 0.582, "stop_and_go": 0.549, "curve_left": 0.565}, "curve_left_runs": 5, "curve_left_failures": 0},
 "behaviour": {"points": 20, "failed_checks": []},
 "twin_repeats": 3, "gazebo_runs": 8, "out_of_scope": []}
```

Codex (`4d22f41`):

```json
{"points": 94.13, "max_points": 100,
 "identity": {"points": 50.0, "runs": 21, "passed": 21, "mean_visible_share": 1.0,
   "passed_per_scenario": {"crossing": "3/3", "side_by_side": "5/5", "side_by_side_same": "5/5", "head_on": "3/3", "stand_aside": "5/5"}},
 "following": {"points": 29.13, "mean_median_gap_m": {"straight": 0.582, "stop_and_go": 0.549, "curve_left": 0.565}, "curve_left_runs": 5, "curve_left_failures": 0},
 "behaviour": {"points": 15, "failed_checks": ["contact in at least one run"]},
 "twin_repeats": 3, "gazebo_runs": 8, "out_of_scope": []}
```

Files changed since `08a7ac8` (`git diff --name-status --no-renames`). All are within the allowed paths.

- **Claude:**
  - `experiments/arena/entries/claude.md` (M)
  - `logs/claude.md` (M)
  - `ros2_yolo_ws/scripts/Image/sync_fusion_node.py` (M)
  - `tests/test_target_gate.py` (A)
- **Codex:**
  - `experiments/arena/entries/codex.md` (A)
  - `logs/codex.md` (M)
  - `ros2_yolo_ws/scripts/Image/sync_fusion_node.py` (M)
  - `tests/test_target_selection.py` (A)

`python3 scripts/check.py` in each entry's checkout: Claude PASS (72 tests), Codex PASS (69 tests).

## Failed runs

A run fails if:
- its target is out of view at the end;
- its final gap is above 1.5 m;
- it had contact;
- its visible share is below 0.9; or
- for `curve_left`, it did not turn.

This was checked on both bridges, in the twin and in Gazebo.

**Claude: none.** That includes the `diff_drive` identity runs, which are not scored for identity.
Every `curve_left` run turned, and `target_loss` stopped in 1.0 s.

**Codex: 3 runs**, all on `diff_drive`:

| Scenario | Bridge | Seed | Final gap (m) | Visible share | Contact |
|---|---|---|---|---|---|
| crossing | diff_drive | 0 | 0.42 | 1.00 | yes, with the crossing person (0.379 m) |
| crossing | diff_drive | 1 | 0.42 | 1.00 | yes (0.378 m) |
| crossing | diff_drive | 2 | 0.43 | 1.00 | yes (0.381 m) |

Every other Codex run passes, in the twin and in Gazebo.

## Closest range to the other person (m, centre to centre)

The first value is the minimum. The values in brackets are seeds 0–2, then gz1 and gz2 for `fixed`
scenarios that also ran in Gazebo.

| Scenario | Bridge | Claude | Codex |
|---|---|---|---|
| crossing | fixed | 0.612 (0.734, 0.614, 0.612) | 0.502 (0.529, 0.502, 0.544) |
| crossing | diff_drive | 0.517 (0.519, 0.517, 0.526) | **0.378** (0.379, 0.378, 0.381): contact |
| side_by_side | fixed | 1.577 (1.619, 1.621, 1.624, 1.578, 1.577) | 1.576 (1.619, 1.622, 1.623, 1.576, 1.607) |
| side_by_side | diff_drive | 1.590 (1.593, 1.605, 1.590) | 1.589 (1.595, 1.615, 1.589) |
| side_by_side_same | fixed | 1.572 (1.619, 1.615, 1.622, 1.572, 1.607) | 1.572 (1.623, 1.618, 1.621, 1.577, 1.572) |
| side_by_side_same | diff_drive | 1.590 (1.592, 1.606, 1.590) | 1.594 (1.603, 1.606, 1.594) |
| head_on | fixed / diff_drive | 0.800–0.801 | 0.800–0.801 |
| stand_aside | fixed / diff_drive | 0.700 | 0.700 |

In `head_on` and `stand_aside` the closest range equals the scenario's set offset (0.8 m and 0.7 m).
So neither entry moved the robot towards the other person.

## Run timeline (Thai time, 2026-10-22)

Images were built from detached checkouts of each entry commit between 06:38:15 and 06:38:20:
- `sim/docker/Dockerfile` with `INSTALL_MCAP=0`, tagged `twin:judge3-<agent>`;
- `sim/docker/Dockerfile.gazebo`, tagged `twin-gz:judge3-<agent>`.

The code hash is the sha256 of the sorted per-file sha256 list of `ros2_yolo_ws/scripts`, `sim`,
`tests` and `scripts`. For each entry, the twin image and the Gazebo image both match the hash of the
entry's checkout:

| Entry | Code hash |
|---|---|
| Claude | `fb39c440a943` |
| Codex | `549f339b37b1` |

The commands were:
- twin: `--scenario everything --bridge-mode turning --seed N`;
- Gazebo: `--scenario curve_left,side_by_side,side_by_side_same,stand_aside --bridge-mode fixed`,
  with the default seed 0.

Every run exited with code 0.

| # | Run | Start | End |
|---|---|---|---|
| 1 | twin seed 0, Claude | 06:38:27 | 06:48:33 |
| 2 | twin seed 0, Codex | 06:48:33 | 06:58:39 |
| 3 | twin seed 1, Codex | 06:58:39 | 07:08:45 |
| 4 | twin seed 1, Claude | 07:08:45 | 07:18:51 |
| 5 | twin seed 2, Claude | 07:18:51 | 07:28:56 |
| 6 | twin seed 2, Codex | 07:28:56 | 07:39:02 |
| 7 | Gazebo gz1, Codex | 07:39:02 | 07:41:34 |
| 8 | Gazebo gz1, Claude | 07:41:34 | 07:44:07 |
| 9 | Gazebo gz2, Claude | 07:44:07 | 07:46:37 |
| 10 | Gazebo gz2, Codex | 07:46:37 | 07:49:10 |

Both entries were scored at 07:49:16.

## Teardown tracebacks

The node logs contain 248 tracebacks per entry. All of them are raised at shutdown, after the run's
data is recorded. None is a run error.

| Error | Claude | Codex |
|---|---|---|
| `RCLError: Failed to publish: publisher's context is invalid` | 60 | 62 |
| `RCLError: failed to shutdown: rcl_shutdown already called` | 188 | 183 |
| `RuntimeError: Unable to convert call argument to Python object` (rclpy `take_message`) | 0 | 3 |

The 3 `RuntimeError`s are in Codex's Gazebo runs:
- gz1 `side_by_side`, in `sync_fusion.log`;
- gz2 `side_by_side_same`, in `fusion_prob.log` and `lidar_sectorizer.log`.

Each is the last traceback in its log, and the affected runs have their full 320–321 samples. One of
them is in `lidar_sectorizer`, which neither entry changed, so these are treated as the same
shutdown race.
