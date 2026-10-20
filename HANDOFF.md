# Handoff

Live state of the shared work. Edit this file **only on `integration-hub`**. The rules are in
[`AGENTS.md`](AGENTS.md). Action history lives in `logs/claude.md` and `logs/codex.md`,
and review threads in [`DISCUSSION.md`](DISCUSSION.md).

## Integration lock

- **Current owner:** Claude Code (integration)
- **Status:** in-progress
- **Files being edited:** merge of `claude/workspace` (`sim/`, `tests/test_sim_twin.py`, `scripts/check.py`, `.github/workflows/twin.yml`, `experiments/sim/`), `HANDOFF.md`, `DISCUSSION.md`, `logs/claude.md`
- **Last updated:** 2026-10-20 by Claude Code

## Branches

| Branch | State |
|---|---|
| `main` | Initial commit only. It receives `integration-hub` through a PR once the user approves. |
| `integration-hub` | Has the robot recovery, Thesis Desk, quest sources, agent workflow, GUI smoke-test results, 12-week plan and Codex week-1 changes. `scripts/check.py` passes. |
| `claude/workspace` | Behind the latest `integration-hub` commits; no feature in progress. |
| `codex/workspace` | Week-1 changes are integrated into `integration-hub`; it is behind the latest integration commits. |
| *To delete* | `integration/robot-thesis-desk`, `codex/robot-backup-quarantine` and `codex/thesis-desk`. They are fully merged, but the cloud session's git proxy cannot delete branches. The user deletes them on GitHub, or Codex runs `git push origin --delete ...` from Windows. |

## Models on `integration-hub`

- Claude Code: Claude Opus 5.5, through the `.claude/agents/integration.md` subagent (`model: opus`).
- Codex: **Sol 6**. *Action for Codex:* set the exact model ID in your own config, then
  confirm it in `DISCUSSION.md` thread T1.

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
   Codex's model should be **Sol 6** on `integration-hub`, but Codex reported its runtime as
   **GPT-6**. The user must confirm or set the model before T1 can close.
2. **T2** in `DISCUSSION.md`: Codex reviewed the plan and task list. Source locations remain unknown; Windows checkout, backup and robot access are unavailable from the cloud session. User input is needed to continue those imports.
3. Optional UI fixes for the `thesis-desk` role, found in the Xvfb smoke test:
   - The Research Desk dialog ignores ESC and stays open after switching to Test Field.
   - The tracker's top bar overflows a 1440 px wide screen.
4. Not yet verified: rendering on the user's real Windows GPU, and the real robot checks
   (ROS graph, camera, LiDAR, motor). There is no physical E-stop to check (see *Plan*).
5. `integration-hub` → `main` (draft PR KobchokTime/Following-Mobile-Robot-in-Farm-Environment#2): needs every thread resolved and the user's approval.

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

## Claude — in parallel

- Replay harness for recorded rosbags (role `robot` / `qa`).
- Docker image (Ubuntu 22.04, ROS 2 Humble, OpenVINO) with fake camera, LiDAR and ZLAC drivers.
- CI that runs `scripts/check.py` and the replay tests on every PR.
- Gazebo world: differential-drive robot with camera and 2D LiDAR in a farm scene with walking people.
- Robot-day #1 checklist (role `research`).
