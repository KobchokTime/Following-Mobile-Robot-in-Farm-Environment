# Handoff

Live state of the shared work. Edit this file **only on `integration-hub`**. The rules are in
[`AGENTS.md`](AGENTS.md). Action history lives in `logs/claude.md` and `logs/codex.md`,
and review threads in [`DISCUSSION.md`](DISCUSSION.md).

## Integration lock

- **Current owner:** Claude Code (integration)
- **Status:** in-progress
- **Files being edited:** merging `claude/robot/arena2-lag` (`3848164`); `HANDOFF.md`, `DISCUSSION.md`, `logs/claude.md`
- **Last updated:** 2026-10-22 by Claude Code (00:59 Thai time)

## Branches

| Branch | State |
|---|---|
| `main` | Initial commit only. It receives `integration-hub` through a PR once the user approves. |
| `integration-hub` | Has the robot recovery, Thesis Desk, quest sources, agent workflow, GUI smoke-test results, 12-week plan, Codex week-1 changes, the offline twin (`sim/`, twin CI, first simulated findings; merge `18c2303`), the Gazebo 3D twin (`sim/gazebo/`, `Dockerfile.gazebo`, `gazebo` CI job, cross-check; merge `cef985f`), the frozen Arena 1 rules, scorer and baseline (merge `d623baf`) the Arena 1 results plus the combined sector-association fix `e6587fd` (merge `4652571`), the drive bridge forwarding `angular.z` plus the Arena 2 draft (merge `4f7a864`, T6/T7), the bridge guard follow-ups (non-finite guard, `turn_dir` as a sign only, Arena 2 entry scope; merge `9f55d17`), and the Arena 2 scorer validation, full-protocol reference (66.0/100) and calibration reconciliation (merge `ecc55ca`, T6/T7), and the scorer gap fixes (duplicate inputs rejected, `--agent`/`--base-ref` required; merge `da04d16`), and the integer seed check (merge `8c77425`). Arena 2 rules and scorer frozen in `9b78f1f` (T7). `scripts/check.py` passes (42 tests). |
| `claude/workspace` | Merged into `integration-hub` at `8c77425` (`abcbb9c`: integer seed check for T7). Before that at `da04d16` (`3b2cad5`: scorer gap fixes). Before that at `ecc55ca` (`16ac740`: Arena 2 scorer validation and calibration reconciliation). Before that at `9f55d17` (`0b934e3`: bridge guard follow-ups), and before that at `4f7a864` (`b36f31a`: bridge `angular.z`, Arena 2 draft), and before that at `7d400bb`, including the Arena 1 results and the combined fix `e6587fd`. The entry branch `claude/robot/arena-sector-association` (`929096d`) stays unmerged, for the record. |
| `codex/workspace` | Synced through `integration-hub` `00a0584` (workspace merge `d2d0351`); the original Arena entry remains separate and unmerged. |
| *To delete* | `integration/robot-thesis-desk`, `codex/robot-backup-quarantine` and `codex/thesis-desk`. They are fully merged, but the cloud session's git proxy cannot delete branches. The user deletes them on GitHub, or Codex runs `git push origin --delete ...` from Windows. |

## Models on `integration-hub`

- Claude Code: Claude Opus 5.5, through the `.claude/agents/integration.md` subagent (`model: opus`).
- Codex: **GPT-6 Astra** (changed from Sol 6 on 2026-10-20, on the user's instruction to adjust as
  appropriate; Arena WebDev/Code mid-October 2026: Astra #2, Sol #8). *Action for Codex:* set the
  exact model ID in your own config, then confirm it in `DISCUSSION.md` thread T1.

## Plan

The 12-week plan is in [`docs/PLAN.md`](docs/PLAN.md) (20 Oct 2026 to about 15 Jan 2027). Key decisions:

- **Scope:** the ground-motion (closed-loop) follower is in scope.
- **Safety:** the user decided there is no physical E-stop, motor-side watchdog, safety bridge or
  speed limit in this project. Safety relies on an isolated field and several spotters. The
  existing "target lost / low confidence → stop" logic stays as follower behavior. The thesis
  must state this under Limitations.
- **Simulator:** Gazebo, not Isaac Sim (no RTX GPU). It runs headless in the cloud and in CI.
- **Robot days:** about 2 per month, 5 in total. The dates are unknown; the user will announce them.

## Open items

1. **T1** in `DISCUSSION.md`: Codex reviewed the branch restructure and role setup. Still open:
   Codex's model on `integration-hub` is now **GPT-6 Astra** (was Sol 6). Codex reported its runtime
   only as **GPT-6**; Codex must set GPT-6 Astra and confirm the exact model ID before T1 can close.
2. **T2** in `DISCUSSION.md`: Codex reviewed the plan and task list. Source locations remain unknown; Windows checkout, backup and robot access are unavailable from the cloud session. User input is needed to continue those imports.
3. Optional UI fixes for the `thesis-desk` role, found in the Xvfb smoke test:
   - The Research Desk dialog ignores ESC and stays open after switching to Test Field.
   - The tracker's top bar overflows a 1440 px wide screen.
4. Not yet verified: rendering on the user's real Windows GPU, and the real robot checks
   (ROS graph, camera, LiDAR, motor). There is no physical E-stop to check (see *Plan*).
5. **T3** in `DISCUSSION.md`: the offline twin and first simulated findings (sector mismatch between
   camera and LiDAR, bridge ignores `angular.z`, proportional lag, 1.0 s stop on target loss).
   Codex re-runs the twin, checks the analysis and answers the robot questions. GitHub Actions
   run 39385504387 (`twin.yml` on `claude/workspace`) was in progress at merge time; check its result.
6. **T4** in `DISCUSSION.md`: the Gazebo 3D twin and its cross-check against the kinematic twin.
   Codex builds `Dockerfile.gazebo`, runs `curve_left`/`diff_drive` (GUI via WSLg if possible),
   judges the field layout and reviews the `sim/twin/world.py` refactor. The new `gazebo` CI job had
   not reported at merge time; check its result.
7. **T5 — resolved 2026-10-21** in `DISCUSSION.md`: Arena 1, sector association. Rules, scorer and baseline frozen in
   `d623baf`. Both entries are submitted and independently scored by Codex; Codex leads by 0.03 points.
   - **Judged 2026-10-21: Codex won on score** (mean 99.43 vs 99.41 over 3 re-runs each).
   - The user chose to combine the entries. The combined fix (`e6587fd`, Claude's bearing matching
     plus Codex's early turn) is merged to the hub (merge `4652571`). The entry branches stay unmerged.
   - Codex agreed after verifying the carried-over code/test and passing 23 tests plus 3 fresh twin runs (seeds 0–2). Data: `experiments/arena/2026-10-20_sector-association.md`.
8. **T6** in `DISCUSSION.md`: the drive bridge forwards `angular.z` (merge `4f7a864`; simulation
   only). The non-finite guard and `turn_dir` sign-only follow-ups are merged (`9f55d17`). Codex
   agrees with default `turn_dir=+1` under the bridge's stated forward mapping. The calibration
   record is reconciled in merge `ecc55ca` (`config/motor_wheel_calibration.md`: the table's signs are
   bench-pulse signs; the bridge, `Joystick.py` and the 2026-09-20 evidence agree on forward).
   `turn_dir=+1` stays. Codex confirms the reconciliation resolves the written calibration point;
   Codex agreed in T6 (21:32). The thread stays open only for the lifted-wheel check on robot day (see *Robot-day checklist*).
9. **T7** in `DISCUSSION.md`: Arena 2 (following lag on the `fixed` bridge). **Frozen in `9b78f1f`**
   on 2026-10-21 after both agents agreed (Codex at 22:00 Thai time). Entries
   (`claude/robot/arena2-lag`, `codex/robot/arena2-lag`) branch from `9b78f1f`; each agent posts its
   entry SHA in T7; neither reads the other's branch until both are in. The `integration` role judges
   with `--base-ref 9b78f1f`, both entries on the same machine in alternating order.
   **Judged 2026-10-22** (results `experiments/arena/2026-10-21_arena2-results.md`, commit `a8f1cae`):
   the Claude entry (`3848164`) wins by the frozen score, 97.84 to 60.89 for Codex (`64dbe7f`). All
   5 Codex `curve_left`/`fixed` runs lost the target. Claude's margins are thinner: closest person
   range 0.455 m against 0.630 m, and final gaps below the set-point. Neither entry is merged; merging
   the winner waits for Codex's cross-check (Codex task 14) and the user's decision. T7 stays open.
   History: the draft was merged in
   `4f7a864`. The scorer's entry scope was tightened to `entries/<agent>.md` in `9f55d17`. Codex's
   change request (enforce minimum runs and coverage) is addressed in `ecc55ca`: `validate()` exits 2
   without a score on an incomplete input set; 9 new tests. New reference on the full protocol:
   66.0/100 (reproduced at merge time). Claude agrees with Codex's three answers and replied `agree`
   to the rules as written. The two gaps found at merge time are fixed in `da04d16`: repeated inputs
   exit 2, and `--agent`/`--base-ref` are required. Codex reproduced 66.01 and passed all 41 tests,
   but found that `validate()` accepted a twin repeat with no seed field. Fixed in `8c77425`: every
   twin row needs an integer seed (regression test added, 42 tests). Codex's final `agree` is in T7.
10. `integration-hub` → `main` (draft PR KobchokTime/Following-Mobile-Robot-in-Farm-Environment#2): needs every thread resolved and the user's approval.

## Codex — week 1 tasks

Sync `codex/workspace` with `integration-hub` first. Read `docs/PLAN.md` and reply in T2.

1. On the user's Windows machine, find the code the docs reference but the repo lacks: the Robot
   Console (`dashboard/`, including `dashboard/bridge/server.mjs`), `src/following_robot/motion_safety.py`
   and the other `src/following_robot/*` modules, and the 121 automated tests plus 32 ROS-stub
   tests from `docs/EXECUTION_WORKFLOW.md`. If something exists only on the robot, pull it over SSH.
2. Bring the robot's Python code and tests into this repo as role `robot` / `qa` feature branches
   (`codex/robot/import-code`, `codex/qa/import-tests`) via `codex/workspace`.
   - Robot Console default: import it into `tools/robot_console/` (Claude's recommendation; the
     user has not objected, but confirm with the user before merging if unsure).
   - Strip secrets, private IPs, SSH keys and machine paths.
   - Make `scripts/check.py` run the full suite (extend `PY_DIRS` and test discovery as needed).
3. List the videos and ROS bags in the local backup (path, size, sha256, what each contains) in a
   new `experiments/raw_data_index.md`. Do not commit the binaries. Propose where to store them
   (GitHub Releases or other object storage).
4. Write a robot-side rosbag2 (MCAP) recording script for robot days, recording all topics plus
   the config, commit SHA and scenario label (role `robot`).
5. Update the quests in `tools/thesis_desk/thesis_data.json` (role `thesis-desk`): drop quests
   11–12 from the plan and move 13 back to Main Quest, per `docs/PLAN.md`.
6. Log everything in `logs/codex.md`. Integrate through `integration-hub` with a `DISCUSSION.md`
   thread for Claude to cross-check.
7. **Arena 1** (T5): review `experiments/arena/2026-10-20_sector-association.md` and
   `sim/arena/score_entry.py` for fairness, then fix the sector mismatch on
   `codex/robot/arena-sector-association`, branched from `integration-hub` at `d623baf`. Post the
   commit SHA in T5. Do not read `claude/robot/arena-sector-association` until both entries are in.
8. **Arena 1 combined fix** (T5): cross-check `e6587fd` on `integration-hub`.
   - Re-run `curve_left`/`diff_drive` a few times if disk space allows.
   - Confirm that your `follow_stop_node.py` change and early-turn test were carried over faithfully.
   - Then reply `agree`, or contest the verdict, in T5.

9. **T6 review**: review the drive bridge `angular.z` change (`4f7a864`). Check the sign derivation
   against `config/motor_wheel_calibration.md` and `ros2_yolo_ws/scripts/control/Joystick.py`,
   re-run `tests/test_drive_bridge_mixing.py`, and say whether the default `turn_dir` should be +1
   or -1.
10. **T7 review**: review the Arena 2 draft rules and `sim/arena/score_entry_v2.py`. Object or reply
    `agree`, and answer the draft's 3 open questions. No entry starts before the freeze. *(Done: change
    requested, answers given.)*
11. **T7 re-review**: review `sim/arena/score_entry_v2.py` as it stands after `da04d16`: `validate()`,
    rejection of repeated inputs, required `--agent`/`--base-ref`, `tests/test_arena2_scorer.py`, and
    the 66.0 reference. *(Reviewed: objected to missing-seed acceptance; fixed in `8c77425`.)*
    **Now:** final T7 review of the integer seed check in `8c77425` (`validate()` and
    `test_missing_or_non_integer_seed`). *(Done: `agree`; reproducer now exits 2; 66.01 reference passes.)*
12. **T6 calibration**: read the reconciliation section in `config/motor_wheel_calibration.md`
    (`ecc55ca`) and confirm in T6 whether it resolves your calibration point. *(Done, apart from robot day:
    Codex agreed the written calibration point is resolved; the lifted-wheel check remains.)*
13. **Arena 2 entry** (T7): build the Codex Arena 2 entry on `codex/robot/arena2-lag`, branched from the
    freeze commit `9b78f1f`. Stay within the allowed paths in
    `experiments/arena/2026-10-21_arena2-draft.md`, do not read `claude/robot/arena2-lag` until both
    entries are in, and post the entry commit SHA in T7. *(Done: pushed `64dbe7f4a823d3662a4a5c36ea160b2b049bdea9`; full self-score unavailable because Docker storage is full, so judging is pending.)* *(Judged 2026-10-22: 60.89.)*
14. **Arena 2 cross-check** (T7): cross-check `experiments/arena/2026-10-21_arena2-results.md`, the raw
    data in `experiments/arena/arena2_judging/`, and the Claude entry `claude/robot/arena2-lag` @
    `3848164` (you may read it now). Re-score from the committed files if you can. Reply `agree` or
    object in T7.

## Robot-day checklist

- [ ] Lifted-wheel turn-direction check for `zlac_joystick_bridge.py` (T6):
  - With the wheels off the ground, publish a small positive `angular.z` (counter-clockwise) and no
    `linear.x`.
  - The right wheel should turn forward and the left wheel backward. If not, set `turn_dir:=-1`.
  - Also confirm that forward `linear.x` still drives both wheels forward.

## Claude — in parallel

- [x] Replay harness for recorded rosbags (`sim/replay/replay_bag.py`, role `robot` / `qa`).
- [x] Docker image (Ubuntu 22.04, ROS 2 Humble) with fake camera/YOLO, LiDAR and ZLAC drivers
  (`sim/`, see `sim/README.md`). It runs the unmodified perception → fusion → controller chain.
- [x] CI that runs `scripts/check.py`, the twin and the replay smoke check (`.github/workflows/twin.yml`).
- [x] Gazebo world: differential-drive robot with 2D LiDAR (`gpu_lidar`) in a farm scene with crop
  beds, a headland and walking people (`sim/gazebo/`). **Done** with Ignition Gazebo Fortress from
  the Docker Hub image `osrf/ros:humble-desktop-full`, because `packages.ros.org` is blocked in
  Claude's cloud session. The camera is emulated, not rendered. Review in T4.
- [ ] Robot-day #1 checklist (role `research`).
