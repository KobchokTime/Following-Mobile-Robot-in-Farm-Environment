# Handoff

Live state of the shared work. Edit this file **only on `integration-hub`**. The rules are in
[`AGENTS.md`](AGENTS.md). Action history lives in `logs/claude.md` and `logs/codex.md`,
and review threads in [`DISCUSSION.md`](DISCUSSION.md).

## Integration lock

- **Current owner:** none
- **Status:** ready
- **Files being edited:** none
- **Last updated:** 2026-10-24 by Codex (16:16 Thai time)

## Branches

| Branch | State |
|---|---|
| `main` | Initial commit only. It receives `integration-hub` through a PR once the user approves. |
| `integration-hub` | Has the robot recovery, Thesis Desk, quest sources, agent workflow, GUI smoke-test results, 12-week plan, Codex week-1 changes, the offline twin (`sim/`, twin CI, first simulated findings; merge `18c2303`), the Gazebo 3D twin (`sim/gazebo/`, `Dockerfile.gazebo`, `gazebo` CI job, cross-check; merge `cef985f`), the frozen Arena 1 rules, scorer and baseline (merge `d623baf`) the Arena 1 results plus the combined sector-association fix `e6587fd` (merge `4652571`), the drive bridge forwarding `angular.z` plus the Arena 2 draft (merge `4f7a864`, T6/T7), the bridge guard follow-ups (non-finite guard, `turn_dir` as a sign only, Arena 2 entry scope; merge `9f55d17`), and the Arena 2 scorer validation, full-protocol reference (66.0/100) and calibration reconciliation (merge `ecc55ca`, T6/T7), and the scorer gap fixes (duplicate inputs rejected, `--agent`/`--base-ref` required; merge `da04d16`), and the integer seed check (merge `8c77425`). Arena 2 rules and scorer frozen in `9b78f1f` (T7), results in `a8f1cae`, and the winning Arena 2 entry `claude/robot/arena2-lag` (speed feed-forward, faster turning; merge `d8401a9`), and the Arena 3 draft with the clothing chroma channel and the thesis review (merge `6698278`, T8). `scripts/check.py` passes (62 tests). |
| `claude/workspace` | Merged into `integration-hub` at `35c161c` (`11056a6`: T8 finding fixes). Before that at `6698278` (`04782cd`: Arena 3 draft, chroma channel, thesis review). Before that at `8c77425` (`abcbb9c`: integer seed check for T7). Before that at `da04d16` (`3b2cad5`: scorer gap fixes). Before that at `ecc55ca` (`16ac740`: Arena 2 scorer validation and calibration reconciliation). Before that at `9f55d17` (`0b934e3`: bridge guard follow-ups), and before that at `4f7a864` (`b36f31a`: bridge `angular.z`, Arena 2 draft), and before that at `7d400bb`, including the Arena 1 results and the combined fix `e6587fd`. The entry branch `claude/robot/arena-sector-association` (`929096d`) stays unmerged, for the record. The Arena 2 winning entry `claude/robot/arena2-lag` (`3848164`) was merged straight into `integration-hub` at `d8401a9`; `claude/workspace` picks it up at its next sync. |
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
   the winner waits for Codex's cross-check (Codex task 14) and the user's decision.
   **Merged 2026-10-22 on the user's decision:** `claude/robot/arena2-lag` @ `3848164` → `d8401a9`
   (49 tests; drive bridge unchanged). Codex's cross-check (relayed to the user: scores reproduce, no
   blocking problem) is waiting for Codex to post it in T7. The Codex entry stays unmerged. T7 is
   resolved once Codex posts `agree`.
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
11. **T8** in `DISCUSSION.md`: Arena 3 (keep following the right person). **Frozen in `08a7ac8`** on
   2026-10-22 after both agents agreed (Codex at 03:37 Thai time). Entries
   (`claude/robot/arena3-identity`, `codex/robot/arena3-identity`) branch from `08a7ac8`; each agent posts
   only its entry SHA in T8; neither reads the other's branch until both are in. The `integration` role
   judges with `score_entry_v3 --base-ref 08a7ac8`, both entries on the same machine in alternating order,
   and posts the raw summaries. T8 stays open until judging. **Both entries are in:** Claude
   `claude/robot/arena3-identity` @ `191d2c1`, Codex `codex/robot/arena3-identity` @ `4d22f41` (both
   unmerged).
   **Judged 2026-10-22** (results `experiments/arena/2026-10-22_arena3-results.md`, commit `a57dff7`): the
   Claude entry wins by the frozen score, 99.13 to 94.13. Both entries passed 21/21 identity runs; Codex
   had contact with the crossing person on `diff_drive` in all 3 seeds. Neither entry is merged. Merging
   the winner waits for Codex's cross-check (Codex task 17) and the user's decision. History: the draft was merged in
   `6698278`. New identity scenarios, the clothing chroma channel `[cx, cy, sector, cb, cr]` (also
   published by the real `ros2_yolo_live.py`), the draft scorer `sim/arena/score_entry_v3.py`, and a
   reference score of 60.6/100. The two merge-time findings are fixed in `35c161c`. Codex requested a
   change (the turn check ignored `diff_drive`) and answered the 4 questions; fixed in `4aba2f6` (turn check
   on both bridges and Gazebo, metric renamed to `target_visible_share`, limits stated, 63 tests).
   Both agents replied `agree`. The thesis review (`docs/thesis_review_2026-10-22.md`) now has C3,
   the box-crop limitation.

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
    `3848164` (you may read it now). *(Done 2026-10-22: re-scored the committed summaries: Claude
    97.84, Codex 60.89, both with empty `out_of_scope`; `scripts/check.py` passed 49 tests on
    `3848164`; reviewed the controller change and tests, found no merge blocker, replied `agree`, and
    marked T7 resolved after confirming the Claude entry merge at `d8401a9`.)*
15. **T8 review**: review the Arena 3 draft rules
    (`experiments/arena/2026-10-22_arena3-draft.md`), the twin chroma model (`sim/twin/world.py`,
    `sim/twin/scenarios.py`) and `sim/arena/score_entry_v3.py` with its tests. *(Done 2026-10-22:
    final `agree` posted in T8 after the diff_drive turn-check fix and regression reproducer passed;
    v3 baseline 60.64, `scripts/check.py` 63 tests. Answered all 4 questions and commented on the
    thesis review's box-crop chroma limitation. Both agents agree; the integration role still needs to
    name the freeze commit. No entry started.)* Also read `docs/thesis_review_2026-10-22.md` and
    comment in T8 or a new thread.
16. **Arena 3 entry** (T8): build the Codex Arena 3 entry on `codex/robot/arena3-identity`, branched
    from the freeze commit `08a7ac8`.
    - Stay within the allowed paths in `experiments/arena/2026-10-22_arena3-draft.md`.
    - Target selection must live in `sync_fusion_node.py`, `fusion_prob_node.py` or
      `follow_stop_node.py`; the twin bypasses `ros2_yolo_live.py`.
    - Detections carry `[cx, cy, sector, cb, cr]` (clothing chroma). Code that reads `cb, cr` must
      accept old 3-value messages.
    - The full protocol needs about 30 minutes of twin time plus the Gazebo runs. If your disk cannot run
      it, say so in your entry note.
    - Do not read `claude/robot/arena3-identity` until both entries are in. Post only the entry commit
      SHA in T8.
    *(Entry pushed: `4d22f4157bb61843d749f0089d07fd29f218c208`; `scripts/check.py` passes 69 tests.
    Full twin/Gazebo protocol unavailable because the root overlay is full and `rclpy` is absent; see
    the entry note. Leave full scoring to the judge.)* *(Judged 2026-10-22: 94.13.)*
17. **Arena 3 cross-check** (T8): *(Done 2026-10-24: re-scored the committed raw summaries: Claude
    `191d2c1` 99.13 and Codex `4d22f41` 94.13, both with empty `out_of_scope`; `scripts/check.py`
    passed 72 tests on a read-only snapshot of Claude's entry; reviewed TargetGate, corridor give-way
    and tests, found no merge blocker, and replied `agree` in T8. Did not merge either entry.)*

## Robot-day checklist

- [ ] Lifted-wheel turn-direction check for `zlac_joystick_bridge.py` (T6):
  - With the wheels off the ground, publish a small positive `angular.z` (counter-clockwise) and no
    `linear.x`.
  - The right wheel should turn forward and the left wheel backward. If not, set `turn_dir:=-1`.
  - Also confirm that forward `linear.x` still drives both wheels forward.
- [ ] Revised experiments E1–E7 from the thesis review
  ([`docs/thesis_review_2026-10-22.md`](docs/thesis_review_2026-10-22.md), section E):
  - **Robot day 1:** E1 (camera vs LiDAR bearing against tape marks), E3 (detection rate against
    distance) and E4 (clothing colour, 2 people × same/different clothes × sun/shade). Add E2
    (latency) once detections carry image stamps.
  - **Robot day 2:** E5 (keep the right person, with the Arena 3 winner) and E6 (following quality).
  - E7 (ablation) runs in the twin.

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
