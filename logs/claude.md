# Claude Code — action log

Append-only. Only Claude Code edits this file. The format and rules are in `AGENTS.md` → *Logging*.
Earlier history: `history-2026-10-16.md`.

---

### 2026-10-16 — integration — Restructured branches into main / workspaces / integration
- User asked for four branches:
  1. `main`: the main work.
  2. `claude/workspace`: Claude's feature work, split by agent role.
  3. `codex/workspace`: Codex's feature work, split by agent role.
  4. `integration`: combine features, test, and let Claude and Codex discuss and re-check
     each other's work. Claude uses Claude Opus 5.5 there, and Codex uses Sol 6.
- Claimed the lock on `integration/robot-thesis-desk`, then rewrote `AGENTS.md` (branches,
  models, roles, workflow).
- Added the shared role files `agents/roles/{robot,thesis-desk,research,qa,integration}.md`.
- Added Claude subagents in `.claude/agents/`, one per role. The `integration` subagent is pinned to Opus.
- Split the log into `logs/claude.md` and `logs/codex.md`. The old `AGENT_LOG.md` became
  `logs/history-2026-10-16.md`.
- Added `DISCUSSION.md` for cross-check threads. `scripts/check.py` now also compiles `src/`.
- Branch operations and the PR change are logged in the next entry.

### 2026-10-16 — integration — Branch operations (partly blocked)
- Created and pushed `claude/workspace` and `codex/workspace` at `680f44f`.
- Commented on PR KobchokTime/Following-Mobile-Robot-in-Farm-Environment#1 that the branch
  would become `integration` and the PR would close.
- **Blocked, waiting for the user:** the session's permission check refused deleting remote
  branches. Still to do:
  1. Rename `integration/robot-thesis-desk` → `integration`. Git can't keep both names, so the
     old branch has to be deleted. That closes PR #1, and a new PR `integration` → `main` replaces it.
  2. Delete the fully merged `codex/robot-backup-quarantine` (tip `66d7b92`) and
     `codex/thesis-desk` (tip `cddc049`). Both tips are contained in `integration`.
- Until then the `integration` role works on `integration/robot-thesis-desk`, and PR #1 stays open.

### 2026-10-16 — integration — Branch deletion is not possible from the cloud session
- The user approved deleting the 3 branches. `git push --delete` was rejected by the session's
  git proxy ("remote end hung up") on two tries with different branches. The GitHub MCP tools
  have no delete-branch action, so nothing was deleted.
- Next: the user deletes `integration/robot-thesis-desk`, `codex/robot-backup-quarantine` and
  `codex/thesis-desk` on GitHub (Branches page). Codex could also do it from Windows with
  `git push origin --delete <branch>`. After that, Claude Code pushes `integration` from
  `93c4e0b`+ and opens the new PR `integration` → `main`.

### 2026-10-20 — integration — Branch #4 is now `integration-hub`
- Retried the deletion in a new session; the git proxy rejected it again. Asked the user.
  They chose to name branch #4 `integration-hub` instead of waiting for `integration`.
- Renamed the branch references in `AGENTS.md`, `CLAUDE.md`, `README.md`, `HANDOFF.md`,
  `DISCUSSION.md` and both `integration` role files. The *role* is still called `integration`.
- Created `integration-hub` from this commit and fast-forwarded `claude/workspace` and
  `codex/workspace` to it. Released the `HANDOFF.md` lock (`ready`).
- Closed PR KobchokTime/Following-Mobile-Robot-in-Farm-Environment#1 and opened a new draft PR
  `integration-hub` → `main` (the number is in the next entry).
- Still pending: deleting `integration/robot-thesis-desk`, `codex/robot-backup-quarantine` and
  `codex/thesis-desk` (the user on GitHub, or Codex from Windows).

### 2026-10-20 — integration — PR #1 closed, PR #2 opened
- Closed PR KobchokTime/Following-Mobile-Robot-in-Farm-Environment#1 (head `integration/robot-thesis-desk`).
- Opened draft PR KobchokTime/Following-Mobile-Robot-in-Farm-Environment#2: `integration-hub` → `main`.
  Its checklist: Codex reviews T1 and confirms the Sol 6 model ID, the leftover branches get
  deleted, optional thesis-desk UI fixes, and the user approves.

### 2026-10-20 — research — 12-week plan agreed with the user
- Planned with the user, Thai time 10:30–11:30:
  - 1–3 months, about 2 robot days per month (dates unknown).
  - Ground-motion follower is in scope.
  - The user decided: no physical E-stop, motor-side watchdog, safety bridge or speed limit in this
    project. Safety comes from an isolated field and several spotters. The existing
    "target lost → stop" logic stays as follower behavior.
  - No RTX GPU, so Gazebo instead of Isaac Sim.
  - Offline twin = rosbag record/replay + Docker with fake drivers + Gazebo.
- Wrote `docs/PLAN.md` on `claude/research/plan`, branched from `claude/workspace`
  (after syncing `integration-hub` in `4ab4721`).
- Found that the code the docs reference but the repo lacks (Robot Console, `motion_safety.py`,
  121 tests) was never committed. `quarantine/BACKUP_AUDIT.md` says `dashboard/` is a
  separate repo on the Windows machine, and the backup also holds videos and ROS bags. This
  became Codex's week-1 task in `HANDOFF.md`.

### 2026-10-20 — integration — integrate the 12-week plan and hand Codex its week-1 tasks
- Claimed the `HANDOFF.md` lock on `integration-hub` (`1141b95`, `handoff: claim plan integration`).
- Merged `origin/claude/workspace` (`90943bb`: `docs/PLAN.md` and a log entry) into
  `integration-hub` with `--no-ff` as `70c048e`. Scanned the diff for private IPs, machine paths
  and secrets: none.
- Ran `python3 scripts/check.py`: exit 0 (compile pass, quest data 18 tasks, 8 unit tests OK).
- `HANDOFF.md`: added a *Plan* section (follower in scope; no physical E-stop, watchdog, safety
  bridge or speed limit by the user's decision, isolated field and spotters instead; Gazebo, not
  Isaac Sim; robot dates unknown). Replaced *Next step* with **Codex — week 1 tasks** (six tasks)
  and **Claude — in parallel**. Kept T1 open (Sol 6 expected, Codex reports GPT-6; the user must
  confirm) and added T2. Removed E-stop from the unverified robot checks.
- `DISCUSSION.md`: opened T2 "12-week plan and Codex week-1 tasks" (Claude Code → Codex, open).
- Released the lock (owner none, status ready) and pushed `integration-hub`. Fast-forwarded
  `claude/workspace` to `integration-hub`. Did not touch `codex/*` branches or PRs.
- Follow-ups: Codex replies in T1 and T2 and starts the week-1 tasks; the user confirms Codex's model.

### 2026-10-20 — integration — Checked Codex commit `0bd37e9` on `codex/workspace` (13:26 Thai time)
- Wording cleanup across docs, comments and Thesis Desk. Deleted `docs/MOTION_SAFETY_GATE.md`. Renamed
  `SAFE_STOP` → `STOP_LATCHED` and `safe_stop()` → `latch_stop()` in `target_identity.py`.
  Removed quest 11, kept quest 12 as "Motor calibration". Added a communication rule to `AGENTS.md`.
- Runtime behavior is unchanged: the stop-on-target-timeout branches and `RPM_LIMIT` are intact,
  and only comments and labels changed.
- `scripts/check.py` on that commit: PASS (17 tasks, 8/8 tests). Codex's log says it had not run the tests.
- A trial merge with `integration-hub` (`aba8175`) conflicts only in `HANDOFF.md`; Codex will resolve
  it when integrating. Notes for Codex:
  - `HANDOFF.md` should only be edited on `integration-hub`.
  - The commit spans several roles, which is fine for a wording pass.

### 2026-10-20 — qa — Checked Codex week-1 work on `codex/workspace` (`3949ddc`, 13:46 Thai time)
- `scripts/check.py` on `3949ddc`: PASS (16 tasks, 8/8 tests).
- `record_robot_day.sh`: tested with a fake `ros2` on PATH.
  - It writes `recording.json` (scenario, commit, dirty count, config SHA-256, start/end time,
    exit code) and rejects bad scenario labels.
  - Suggestions for Codex:
    - Configs land at `config/config/...` (doubled folder).
    - Save `git diff` when the tree is dirty, plus `ros2 topic list -t` and the hostname.
    - Uncompressed `/image_raw` at 640×480 is roughly 1 GB/min, so consider an MCAP zstd
      preset or recording the compressed image topic.
    - The script needs a git checkout of this repo on the robot. Today the code is deployed
      file by file through the Robot Console bridge.
- `experiments/raw_data_index.md` is a placeholder. Codex runs in a cloud session with no access to
  the Windows backup or the robot. The same goes for task 1 (importing the missing code), so it is
  blocked on the user.
- Codex has not integrated into `integration-hub` yet and has not answered T2. Its log says it
  is waiting for the user's authorization to write to `integration-hub`.

### 2026-10-20 — robot / qa — Offline twin, replay harness and CI (14:00–15:20 Thai time)
- Branch `claude/robot/offline-twin` from `claude/workspace`, which had synced `integration-hub` `0382a0f`.
- Added `sim/`:
  - Docker image (`sim/docker/`, ROS 2 Humble).
  - Kinematic twin world with fake LiDAR, fake camera/YOLO and a ZLAC bridge model
    (`sim/twin/world.py`, `world_node.py`).
  - 5 scenarios and a scorer.
  - `run_scenario.py`, which runs the **unmodified** robot nodes.
  - `sim/replay/replay_bag.py`: rosbag2 replay plus `/cmd_vel` comparison.
  - `sim/tests/smoke.py` and `sim/README.md`.
- Added `tests/test_sim_twin.py` (9 offline tests). `scripts/check.py` now also compiles `sim/`.
- Added `.github/workflows/twin.yml`: `check.py` plus the Docker twin, replay and smoke check on push and PR.
- Verified here:
  - Image built with `INSTALL_MCAP=0`, because `packages.ros.org` is blocked in this session.
  - 10/10 scenario runs passed, twice, with the smoke check OK.
  - Record → replay: 272 vs 258 `/cmd_vel`, linear RMSE 0.066.
  - `check.py`: PASS.
  - Not verified: MCAP replay (no plugin here) and the GitHub Actions run itself (pending push).
- Findings are written up in `experiments/sim/2026-10-20_twin_first_run.md`:
  - Camera/LiDAR sector mismatch, so the follower cannot follow a target off-center.
  - The bridge ignores `angular.z`.
  - P-only lag (gap about 2 m at 0.3 m/s).
  - Target-loss stop after 1.0 s.
- Gazebo is deferred because its package server is blocked in this session. The same harness can host it later.

### 2026-10-20 — integration — integrate the offline twin and open T3
- Claimed the `HANDOFF.md` lock on `integration-hub` (`375467e`, `handoff: claim offline twin integration`).
- Merged `origin/claude/workspace` (`4b1b45e`: `sim/`, `tests/test_sim_twin.py`, `scripts/check.py`
  compiles `sim/`, `.github/workflows/twin.yml`, `.dockerignore`,
  `experiments/sim/2026-10-20_twin_first_run.md`) into `integration-hub` with `--no-ff` as `18c2303`.
  No conflicts.
- Ran `python3 scripts/check.py`: exit 0 (compile pass including `sim/`, quest data 16 tasks,
  17 unit tests OK). Skipped `sim/tests/smoke.py`: there is no `sim_runs/summary.json`.
- Reviewed the merged diff: no secrets, private IPs or machine paths. `sim/` touches no serial or
  motor devices and runs on a random ROS domain with `ROS_LOCALHOST_ONLY=1`. Minor notes went into
  T3 (the findings table has 7 of 10 runs, the "about 2 m" gap wording, actions pinned by tag and
  no `permissions:` block in `twin.yml`). The sector-mismatch claim matches `lidar_sectorizer_node.py`
  (±15° default) and `sync_fusion_node.py` (indexes LiDAR by the camera sector).
- GitHub Actions run 39385504387 (`twin.yml`, `4b1b45e`): the `check` job passed and the `twin` job
  was still in progress at merge time.
- `DISCUSSION.md`: opened T3 "Offline twin and first simulated findings" (Claude Code → Codex, open).
- `HANDOFF.md`: updated the branches table. Marked the replay harness, Docker with fake drivers and CI
  as done; Gazebo is deferred (`packages.ros.org` and the Gazebo apt server are blocked in the cloud
  session); the robot-day #1 checklist is still open. Added T3 to the open items.
- Released the lock (owner none, status ready) and pushed `integration-hub`. Did not touch
  `codex/*`, PRs or `claude/workspace`.

### 2026-10-20 — qa — Applied the integration review notes from T3
- `twin.yml`: added `permissions: contents: read`. Actions stay pinned by tag; pinning them by SHA is
  left open.
- Findings doc: noted that the table shows 7 of the 10 runs, and stated precisely that the gap grows
  to about 2.0 m while the target walks (median 1.67 m over the whole run).
- Synced `integration-hub` (`29e00f9`) into `claude/workspace` first.

### 2026-10-20 — qa — First GitHub Actions results for `twin.yml` (checked 14:31 Thai time)
- All 4 runs passed (`check` and `twin` jobs: image build with the MCAP plugin, 10 scenario runs,
  record → replay, smoke check):
  - Run 39385504387: `claude/workspace` `4b1b45e`.
  - Run 39385789266: `claude/workspace` `2574d0e`.
  - Run 39385704216: `integration-hub` `29e00f9`, push.
  - Run 39385709202: `integration-hub` `29e00f9`, PR KobchokTime/Following-Mobile-Robot-in-Farm-Environment#2.
- This confirms that the full Dockerfile (`INSTALL_MCAP=1`) builds on GitHub's runners. That could not
  be checked in Claude's cloud session.

### 2026-10-20 — robot / research — Gazebo 3D twin with video (15:00–15:30 Thai time)
- User asked for a graphical Gazebo view. `packages.ros.org` and Gazebo Fuel are blocked in this
  session, so I used the Docker Hub image `osrf/ros:humble-desktop-full`, which ships Ignition
  Gazebo Fortress and `ros_gz_bridge`.
- Added `sim/gazebo/` on `claude/robot/gazebo-world`:
  - `world_gen.py`: a farm world with crop beds and a headland, the robot with `gpu_lidar` at 180°,
    and people as simple shapes.
  - `gz_twin_node.py`: drives the people, models the ZLAC bridge and emulates the detector, reusing
    `sim/twin/world.py`, which was refactored into `bridge_rpm` / `wheel_twist` / `project_detections`.
  - `run_gazebo.py`: runs the unmodified robot nodes on sim time.
  - `record_video.sh`: Xvfb + ffmpeg recording.
- Also added `sim/docker/Dockerfile.gazebo` and a `gazebo` job in `twin.yml`.
- Verified here:
  - Headless and GUI runs both work.
  - 3 videos recorded (straight/current, curve_left/diff_drive, target_loss/current) and sent to the user.
  - Gazebo scores match the kinematic twin to within 0.05 m.
  - `check.py` PASS; the 9 twin tests still pass after the refactor.
- Not verified yet: the new `gazebo` CI job (runs after the push).
- Cross-check table added to `experiments/sim/2026-10-20_twin_first_run.md` on `claude/research/gazebo-crosscheck`.

### 2026-10-20 — integration — Gazebo 3D twin merged into `integration-hub`, T4 opened (15:25 Thai time)
- Claimed the `HANDOFF.md` lock (`7d6d20f`). Merged `origin/claude/workspace` (`68e4c10`) with
  `--no-ff` (`cef985f`); no conflicts, no Codex content dropped.
- `python3 scripts/check.py` on `integration-hub`: exit 0 (compile, quest data with 16 tasks, 17 unit tests).
- Review of the merged diff: no secrets, private IPs or machine paths; nothing opens serial or
  motor devices; `/cmd_vel` only reaches Gazebo's `/model/robot/cmd_vel` on an isolated ROS domain.
  The `world.py` refactor keeps the same logic and RNG call order. Minor points recorded in T4: no
  offline test for `sim/gazebo/`, unpinned `osrf/ros:humble-desktop-full` tag, and headless
  `gpu_lidar` on GPU-less CI runners is untested.
- Opened **T4 — Gazebo 3D twin and cross-check** for Codex. The `gazebo` CI job had not reported yet.
- `HANDOFF.md`: Gazebo task marked done, T4 added to open items, branches table updated. Lock released.

### 2026-10-20 — qa — Gazebo CI job verified (checked 15:43 Thai time)
- All runs passed, including the new `gazebo` job:
  - Runs #6–#10, 15:22–15:31 Thai time: `claude/workspace` `68e4c10`, `integration-hub` `7d6d20f` and
    `40ab328`, push and PR KobchokTime/Following-Mobile-Robot-in-Farm-Environment#2.
- In run #6, the `gazebo` job built `Dockerfile.gazebo` (70 s), ran straight + target_loss headless
  with `gpu_lidar` on GitHub's no-GPU runner (73 s), and passed the smoke check. This closes the
  open CI point in T4.

### 2026-10-20 — research — Arena 1 rules frozen (sector association)
- The user said to adjust as fits the work. I decided:
  1. Codex uses GPT-6 Astra on `integration-hub` (Arena WebDev #2, versus Sol at #8). This goes
     into `AGENTS.md` through integration, and Codex sets the model itself.
  2. Run an internal arena on the sector-mismatch fix.
- Committed `experiments/arena/2026-10-20_sector-association.md` (rules), `sim/arena/score_entry.py`
  (scorer) and `experiments/arena/baseline_2026-10-20.json` (the 10 baseline runs) on
  `claude/research/arena-spec`, **before** writing Claude's entry.
- Baseline score: 42.04 / 100 (no regressions, task failed).

### 2026-10-20 — integration — Arena 1 rules frozen on `integration-hub`, Codex model set to GPT-6 Astra, T5 opened
- Claimed the `HANDOFF.md` lock (`9c47096`). Merged `origin/claude/workspace` (`0d4ee2f`) with
  `--no-ff` (`d623baf`); no conflicts. This merge freezes the Arena 1 rules, scorer and baseline on
  the hub before any entry exists.
- `python3 scripts/check.py`: exit 0 (compile, 16 quest tasks, 17 unit tests).
  `python3 -m sim.arena.score_entry /nonexistent/entry.json` imports and stops with
  `FileNotFoundError`. Scoring the baseline against itself gives 42.04 / 100, as documented.
- Review: no hardware commands, secrets or machine paths. Fairness points recorded in T5: the scope
  check misses renames, rule 3 (bridge untouched) is not enforced by the scorer, `logs/` is wider than
  "your own log", and the task is scored on a single seed.
- Models: Codex on `integration-hub` changed from Sol 6 to GPT-6 Astra in `AGENTS.md`,
  `agents/roles/integration.md` and `HANDOFF.md` (user said to adjust as appropriate; Arena
  WebDev/Code mid-October 2026: Astra #2, Sol #8). Replied in T1 asking Codex to set it and confirm the ID.
- Opened **T5 — Arena 1: sector association**. Added the Arena 1 task to Codex's list in
  `HANDOFF.md` and T5 to the open items. Lock released.

### 2026-10-20 — integration — Arena 1 submission note in T5

- Lock claimed (`handoff: claim T5 submission note`) and released. Worktree `/tmp/claude-0/hub-wt4`.
- Recorded Claude's Arena 1 entry in T5 (rule 5): `claude/robot/arena-sector-association` @ `929096d`,
  from `d623baf`, self-reported 99.42/100. Entry **not merged**; it waits for judging.
- Scope check: ancestry OK; `git diff --name-only --no-renames d623baf 929096d` shows 6 paths, all
  under `ros2_yolo_ws/scripts/`, `tests/`, `logs/claude.md` or `experiments/arena/entries/claude.md`;
  `zlac_joystick_bridge.py` untouched. No paths, secrets or hardware commands in the added lines.
- `HANDOFF.md`: Arena 1 item notes Claude submitted `929096d`, waiting for Codex's entry.

### 2026-10-20 — robot — Arena 1 entry submitted (17:15–17:50 Thai time)
- Branch `claude/robot/arena-sector-association` from `d623baf`. I did not read Codex's branch; it did
  not exist yet.
- Root causes:
  1. Sector index mismatch between camera and LiDAR.
  2. `fusion_prob_node`'s fixed off-center penalty (`P_C = exp(-3·dx²)`) dropped P_fused below 0.6
     exactly where the controller would start turning.
- Fix:
  - `sync_fusion_node` matches by bearing using `/lidar_sector_angles`.
  - The LiDAR sectorizer FOV defaults to ±35°.
  - `fusion_prob_node` gets a `center_penalty` parameter, default 0.
  - 5 new offline tests.
- Official score 99.42/100: turned, target in view, final gap 0.59 m, no regressions, in scope.
  Seeds 1 and 2 give the same result; Gazebo agrees (final gap 0.55 m). Write-up in
  `experiments/arena/entries/claude.md`.
- `check.py` PASS (22 tests). Not merged into `claude/workspace` until the round is judged.

### 2026-10-21 — research / robot — Arena 1 judged; combined fix chosen
- Re-ran both entries with the same script: 3 full runs each, alternating. Codex scored 99.43 and
  Claude 99.41, so **Codex wins under the frozen rules**.
- Robustness check on `curve_left`/`diff_drive`, not scored:
  - Claude: 0/18 twin failures, 0/5 Gazebo.
  - Codex: 1/16 twin failures, 2/4 Gazebo. These depend on timing.
- The user chose option B, combining the two. `claude/robot/sector-association-combined` (`e6587fd`)
  is Claude's entry plus Codex's early-turn controller change and its test.
  - Result: mean score 99.42, 0/11 twin failures, 0/4 Gazebo failures, mean bearing 7.4°, no
    oscillation.
  - `check.py` passes with 23 tests.
- Results and lessons for Arena 2 are in `experiments/arena/2026-10-20_sector-association.md`.
  The combined branch is merged into `claude/workspace`; the entry branches stay unmerged.

### 2026-10-21 — integration — Arena 1 verdict and combined fix merged into integration-hub
- Claimed the `HANDOFF.md` lock (`a73b739`). Codex had released it after its submission (`9133145`).
- Merged `origin/claude/workspace` @ `7d400bb` with `--no-ff` (`4652571`). There were no conflicts,
  and no Codex content changed. `check.py` PASS with 23 tests.
- Robot-code review since `a73b739`:
  - Four files changed under `ros2_yolo_ws/scripts/`.
  - The three Claude files are byte-identical to `929096d`.
  - `follow_stop_node.py` is byte-identical to Codex's `52edffb`.
  - `zlac_joystick_bridge.py` is untouched.
  - The added lines have no paths, IPs, secrets or new `cmd_vel` publishers.
- T5: posted the judge data (Codex wins 99.43 vs 99.41), the user's decision to combine, and the
  Arena 2 lessons. Asked Codex to agree and to cross-check `e6587fd`. T5 stays open.
- HANDOFF: updated the Arena 1 status, added Codex task 8 to cross-check the combined fix, and added
  open item 8 to draft the Arena 2 rules. Released the lock.

### 2026-10-21 — robot / research — Drive bridge turns; Arena 2 draft (19:20–20:10 Thai time)
- User: "do all of it" (bridge fix, Arena 2 draft, dashboard additions, live CI).
- `claude/robot/bridge-angular` (`594c434`): `zlac_joystick_bridge.py` now mixes `angular.z` in
  `wheel_commands()`.
  - Straight driving is identical to before; a test checks this.
  - Both wheels are scaled together at MAX_CMD.
  - New ROS parameters: `use_angular`, `track_width_m` (0.40 m, not measured) and `turn_dir`.
  - Register signs follow the existing forward mapping and `config/motor_wheel_calibration.md`.
    Spinning counter-clockwise writes negative to both registers. The joystick script suggests
    the opposite, so check the direction once on robot day with the wheels lifted, and flip
    `turn_dir` if needed.
  - The twin's `fixed` bridge mode mirrors it, and a test checks that they agree.
  - `--bridge-mode all` runs current, fixed and diff_drive.
  - `check.py`: 30 tests pass.
- Results (twin, 15 runs):
  - curve_left with the fixed bridge now turns: final gap 0.79 m (current bridge 3.22 m),
    travelled 5.45 m.
  - Gazebo agrees on 2 seeds: final gap 0.75 m.
  - Straight, stop_and_go and target_loss are unchanged.
- Arena 2 draft (`claude/research/arena2-draft`): following lag on the fixed bridge, with a
  multi-run scorer `sim/arena/score_entry_v2.py` that applies the Arena 1 lessons. The current code
  scores 65.9/100 (lag 15.9/50). Not frozen; it waits for Codex.
- No GitHub connector exists in claude.ai, so dashboard CI stays a snapshot.

### 2026-10-21 — integration — Merge bridge angular.z and Arena 2 draft; open T6 and T7
- Model: Claude Opus 5.5 (`integration` subagent). Worktree `/tmp/claude-0/hub-wt6`, removed at the end.
- Lock: free (last released by Codex). Claimed in `09c8a43` (`handoff: claim bridge fix and Arena 2 draft`), pushed.
- Merged `origin/claude/workspace` (`b36f31a`) into `integration-hub` with `--no-ff`: merge `4f7a864`.
  There were no conflicts. `logs/claude.md` merged cleanly with no lines removed, and no Codex files
  were touched.
- `python3 scripts/check.py`: PASS (compile, 16 quest tasks, 30 unit tests).
  `tests.test_drive_bridge_mixing` re-run on its own: 7/7 OK.
- Bridge review (`zlac_joystick_bridge.py`):
  - With `angular.z = 0`, the register values are identical to the old code, as floats and after
    `int()`. Checked over 210,006 `linear.x` values, including the ±40 clamp, ±1e9, 1e300 and -0.0.
  - `update_loop` timeout-to-zero, the ZLAC driver class, `destroy_node` and `main` are unchanged.
  - Difference: `linear.x = ±inf` (or a non-finite `angular.z`) now gives NaN, so `int()` raises in
    `update_loop`. The old code clamped ±inf to ±40. Follow-up for Claude's workspace: add a
    `math.isfinite` guard.
  - `track_width_m` and `turn_dir` are not range-checked.
  - The calibration table's sign column and `Joystick.py`'s stick-left mapping both disagree with
    the derived counter-clockwise sign. This is raised in T6.
- Arena 2 scorer: `ALLOWED` admits all of `experiments/arena/entries/`, not only
  `entries/<agent>.md`. Raised in T7; follow-up for Claude's workspace before the freeze.
- DISCUSSION: opened T6 (drive bridge forwards angular.z) and T7 (Arena 2 draft: following lag),
  both open with Codex as reviewer.
- HANDOFF: added Codex tasks 9 (review T6) and 10 (review T7), a *Robot-day checklist* with the
  lifted-wheel `turn_dir` check, and open items 8 (T6) and 9 (T7). Updated the branch table.
  Released the lock.
- Not touched: `codex/*`, `claude/workspace`, PRs, `main`.

### 2026-10-21 — robot / integration — Review follow-ups for T6/T7; dashboard extended (20:15 Thai time)
- `claude/robot/bridge-guards`:
  - `wheel_commands()` returns 0 for NaN/inf input. Before, `int(NaN)` would have raised every tick.
  - `turn_dir` is treated as a sign only.
  - The Arena 2 scorer allows only the agent's own `experiments/arena/entries/<agent>.md`.
  - 2 new tests; `check.py` passes 32 tests.
- Dashboard "Follower Test Bench" (https://claude.ai/artifact/JmYTWLwJiiPDRKiG2L1pdS) updated:
  - Fixed-bridge rows for the combined code.
  - A LiDAR view from the curve_left/fixed bag, synced to the replay.
  - A robot speed chart.
  - CI snapshot with 36 runs; 30 unit tests.
  - There is no GitHub connector in claude.ai, so CI stays a snapshot.

### 2026-10-21 — integration — Merge bridge guard follow-ups (T6/T7)
- Model: Claude Opus 5.5 (`integration` subagent). Worktree `/tmp/claude-0/hub-wt7`, removed at the end.
- Lock: free. Claimed in `34503bb` (`handoff: claim bridge guard follow-ups`), pushed.
- Merged `origin/claude/workspace` (`0b934e3`) with `--no-ff`: merge `9f55d17`. The only conflict
  was in `logs/claude.md`; both sides were kept in full.
- `python3 scripts/check.py`: PASS (compile, 16 quest tasks, 32 unit tests).
- `wheel_commands()` with finite inputs is identical to the reviewed `4f7a864` version: 1,004,818 cases,
  0 mismatches. These include `angular.z = ±0` over 100,007 `linear.x` values and a
  `linear`/`angular` grid for `turn_dir`/`forward_dir` = ±1. `use_angular=False` is also identical.
  NaN/±inf returns `(0, 0)`. Edge case noted in T6: `turn_dir = 0` now counts as +1, where it used to
  disable turning.
- `score_entry_v2.py`: `experiments/arena/entries/` was removed from `ALLOWED`; only
  `entries/<agent>.md` is accepted.
- DISCUSSION: replied in T6 and T7 that the follow-ups are merged. Both threads stay open for Codex.
- HANDOFF: updated the branch table, open items 8 and 9 and the test count (32), and released the lock.
- Not touched: `codex/*`, `claude/workspace`, PRs, `main`.

### 2026-10-21 — qa / research — Answer Codex's T6/T7 reviews (20:30–20:57 Thai time)
- Read Codex's hub commits `cc9f563` and `e0da45c`: T1 (no exact model ID available), T6 `agree` with
  `turn_dir=+1` plus a calibration-record conflict, T7 change request (scorer did not enforce minimum runs).
- `claude/qa/arena2-scorer-validation` (`48ef769`, `b62df9a`):
  - `score_entry_v2.py` `validate()` refuses to score (exit 2) unless it has 3+ twin repeats with distinct
    seeds, each with every scenario × bridge mode exactly once, and 2+ Gazebo `curve_left/fixed` runs.
  - New `tests/test_arena2_scorer.py` (9 tests); `check.py` passes 41 tests.
  - Re-ran the reference on the full protocol (hub code `8afdae0`, seeds 0–2, 2 Gazebo runs): 66.0/100
    (lag 16.0, reliability 30 with 0/5 failures, behaviour 20). Raw data in
    `experiments/arena/baseline_arena2_2026-10-21.json`; the draft records Codex's three answers.
- `claude/research/calibration-reconcile` (`dfac379`): `config/motor_wheel_calibration.md` now notes that the bridge
  and `Joystick.py` agree on forward (`0x2088` −, `0x2089` +), that the table's signs are bench-pulse signs,
  and lists the lifted-wheel check that settles `turn_dir`.
- Both merged into `claude/workspace`; integration to the hub goes through the `integration` subagent.

### 2026-10-21 — integration — Merge Arena 2 scorer validation and calibration reconcile (T6/T7) (20:58–21:00 Thai time)
- Model: Claude Opus 5.5 (`integration` subagent). Worktree `/tmp/claude-0/wt_hub`.
- Lock: free (Codex released it at 20:22). Claimed in `4df6ccf` (20:58), pushed.
- Merged `origin/claude/workspace` (`16ac740`) with `--no-ff`: merge `ecc55ca`. The only conflict
  was in `logs/claude.md`; both sides were kept in full.
- `python3 scripts/check.py`: PASS (compile, 16 quest tasks, 41 unit tests).
- Scorer review: `validate()` reproduced. Wrote the twin (seeds 0–2) and Gazebo arrays of
  `experiments/arena/baseline_arena2_2026-10-21.json` to temp summaries and ran
  `python3 -m sim.arena.score_entry_v2`: 66.01, identical to the stored score; scope check on an empty
  diff passes. 2 repeats → exit 2; the same twin directories passed twice → exit 2 (reused seed).
  Gap: the same Gazebo file passed twice → exit 0 (noted in T7). `--base-ref` stays optional (noted).
- Calibration review: re-derived the signs from code. Bridge forward `(0x2088, 0x2089)` = (−, +), CCW
  `angular.z` = (−, −); `Joystick.py` stick forward = (−, +). Matches the reconciliation section.
- No hardware code changed in this merge; no machine paths or secrets in the added files.
- Correction: the entry above cites `b62df9a`, which is on no remote branch. The commit in
  `claude/workspace` is `d291125`. The entry is left as written (append-only).
- DISCUSSION: T1 note (model setting needs the user; stays open). T6 reply (reconciled; `turn_dir=+1`
  stays; asked Codex to confirm; open until robot day). T7 `agree` to the rules as written; asked Codex
  to re-review and reply `agree`; **not frozen**.
- HANDOFF: branch table, items 8/9, Codex tasks 11–12, lock released.
- Not touched: `codex/*`, `claude/workspace`, `main`, PRs.

### 2026-10-21 — qa — Close the two scorer gaps the integration review found (21:05 Thai time)
- `8d31ec2` on `claude/qa/arena2-scorer-validation`: `score_entry_v2.py` exits 2 if the same twin run directory or
  Gazebo summary is passed twice (both reference Gazebo runs use seed 0, so a seed check could not catch it).
  `--agent` and `--base-ref` are now required, so the scope check always runs. Reference still scores 66.01,
  scope clean; `check.py` passes 41 tests.
- Correction: the reference commit cited as `b62df9a` in the previous entry was amended; the pushed commit is `d291125`.

### 2026-10-21 — integration — Merge Arena 2 scorer gap fixes (T7) (21:01–21:01 Thai time)
- Model: Claude Opus 5.5 (`integration` subagent). Worktree `/tmp/claude-0/wt_hub`.
- Lock: free. Claimed in `19fc5c8` (21:01), pushed.
- Merged `origin/claude/workspace` (`3b2cad5`, feature `8d31ec2`) with `--no-ff`: merge `da04d16`.
  The only conflict was in `logs/claude.md`; both sides were kept in full.
- `python3 scripts/check.py`: PASS (41 unit tests).
- Re-verified: a repeated Gazebo file → exit 2; a repeated twin directory → exit 2; missing `--base-ref`
  or `--agent` → argparse error, exit 2; full reference → 66.01, `out_of_scope` empty.
- Remaining limit (noted in T7, not blocking): duplicates are found by resolved path, so a copy under
  another name passes. The dedupe has no unit test.
- Log note: the qa entry above is stamped 21:05, but its commit `3b2cad5` was made at 21:00 Thai time.
- DISCUSSION: T7 note that both gaps are fixed; Codex to review the scorer as it stands; **not frozen**.
- HANDOFF: branch table, item 9, Codex task 11, lock released.
- Not touched: `codex/*`, `claude/workspace`, `main`, PRs.

### 2026-10-21 — qa — Missing-seed gap from Codex's T7 re-review (21:33 Thai time)
- Codex (`e05738f`) agreed in T6 and requested one more T7 change: a twin repeat with no `seed` field passed `validate()`.
- `f1def1f`: `validate()` rejects a repeat unless every row has an integer seed (`None`, strings, floats and bools are
  rejected); regression test `test_missing_or_non_integer_seed`. `check.py` passes 42 tests; the reference still
  validates and scores 66.01.

### 2026-10-21 — integration — Merge Arena 2 integer seed check (T6/T7) (21:33–21:34 Thai time)
- Model: Claude Opus 5.5 (`integration` subagent). Worktree `/tmp/claude-0/wt_hub`.
- Lock: free (Codex released it at 21:30; hub head `e05738f`). Claimed in `0a46287` (21:33), pushed.
- Merged `origin/claude/workspace` (`abcbb9c`, feature `f1def1f`) with `--no-ff`: merge `8c77425`.
  The only conflict was in `logs/claude.md`; both sides were kept in full.
- `python3 scripts/check.py`: PASS (42 unit tests).
- Re-verified Codex's reproducer: a complete repeat with `seed` removed from every row, plus seeds 1 and 2
  → `validate()` reports "every row needs an integer seed", CLI exit 2. Full reference → 66.01,
  `out_of_scope` empty.
- DISCUSSION: T6 note of Codex's `agree`; open only for robot day. T7 `agree` stands; asked Codex for a
  final `agree` or objection; **not frozen**.
- HANDOFF: branch table, items 8/9, Codex task 11 (final T7 review of the seed check), task 12 done apart
  from robot day; lock released.
- Not touched: `codex/*`, `claude/workspace`, `main`, PRs.

### 2026-10-21 — integration — Freeze Arena 2 (T7) (22:01–22:02 Thai time)
- Model: Claude Opus 5.5 (`integration` subagent). Worktree `/tmp/claude-0/wt_hub`.
- Codex replied `agree` in T7 (hub `779e7e0`, 22:00); Claude had already agreed.
- Lock: free (Codex released it at 21:59). Claimed in `d767eda` (22:01), pushed.
- Freeze commit `9b78f1f` (`arena: freeze Arena 2 rules and scorer`): status line of
  `experiments/arena/2026-10-21_arena2-draft.md` (draft → frozen) and the `score_entry_v2.py` docstring
  only. No rule text or logic changes, no renames. `python3 scripts/check.py`: PASS (42 tests).
- DISCUSSION T7: named `9b78f1f` as the freeze commit; entries `claude/robot/arena2-lag` and
  `codex/robot/arena2-lag` branch from it; SHAs posted in T7; no reading the other branch until both
  are in; the integration role judges with `--base-ref 9b78f1f`, same machine, alternating order. T7 open
  until judging.
- HANDOFF: item 9 frozen; new Codex task 13 (build the Codex entry from `9b78f1f`, post the SHA in T7);
  lock released.
- Not touched: `codex/*`, `claude/workspace`, `main`, PRs. No entry started.

### 2026-10-21 — integration — Post Claude Arena 2 entry SHA (T7) (22:35 Thai time)
- Lock claimed and released; posted only "Claude entry: `claude/robot/arena2-lag` @ `3848164` (from `9b78f1f`)" in T7 (ancestry from the freeze commit checked; content not read). HANDOFF item 9 notes it is waiting for the Codex entry (task 13).

### 2026-10-22 — integration — Judge Arena 2 and post the results (T7) (2026-10-21 23:33 – 2026-10-22 00:29 Thai time)
- Model: Claude Opus 5.5 (`integration` subagent), acting as judge.
- Entries: Claude `claude/robot/arena2-lag` @ `3848164`, Codex `codex/robot/arena2-lag` @ `64dbe7f`; both from
  the freeze commit `9b78f1f`.
- Detached checkouts `/tmp/claude-0/judge_claude` and `/tmp/claude-0/judge_codex`. Built `twin:judge-<agent>` and
  `twin-gz:judge-<agent>` (23:33:35–23:33:43). Image code hashes match the checkouts (claude `62979093515f`,
  codex `abd3c74e45e9`).
- Ran the protocol in alternating order, 23:34:02–00:26:53: twin seeds 0–2, then Gazebo gz1/gz2. All runs
  exited 0. Raw runs are kept in `/tmp/claude-0/judge_runs`.
- Scored in wt_hub at `2afe284` with `--base-ref 9b78f1f` (00:27): Claude 97.84, Codex 60.89. Both in scope;
  no contact. Codex: 5/5 `curve_left`/`fixed` failures. Re-scoring from the committed raw files gives
  identical JSON.
- `check.py` in each entry checkout: Claude PASS (49), Codex PASS (43). Hub `check.py`: PASS (42).
- Hub: claimed the lock in `8d912f8` (00:28). Results and raw data in `a8f1cae`. T7 judge reply; HANDOFF item 9
  and Codex task 14 (cross-check); lock released.
- Neither entry is merged; merging waits for Codex's cross-check and the user's decision.
- Not touched: `codex/*`, the entry branches, `claude/workspace`, `main`, PRs.

### 2026-10-21 — robot — Arena 2 entry (22:05–22:35 Thai time)
- Branch `claude/robot/arena2-lag` from the freeze commit `9b78f1f`. I did not read Codex's branch.
- `3633324`: speed feed-forward (`speed_command()`) plus a higher turn gain and limit in `follow_stop_node.py`; 7 new tests;
  the early-turn test's clock stub supports subtraction. `check.py` passes 49 tests.
- Tuning: a scratch kinematic model, then quick twin runs on curve_left/fixed (turn gain 0.2/0.6 gave max bearing 31°; 0.3/0.8 gave 21.5°).
- Full protocol self-score: **97.87/100** (lag 47.87, reliability 30, behaviour 20, scope clean). Reference: 66.0.
  Thin margin: in crossing on diff_drive the distractor passes 0.42 m from the robot's centre (contact line 0.40 m).
- Details: `experiments/arena/entries/claude.md`. The judge (integration) runs the official score after both entries are in.

### 2026-10-22 — integration — Merge the Arena 2 winner (T7) (00:59–01:00 Thai time)
- Model: Claude Opus 5.5 (`integration` subagent). The user decided to merge the winning entry now
  (relayed by the coordinator).
- Lock: free. Claimed in `35fa722` (00:59), pushed.
- Merged `origin/claude/robot/arena2-lag` (`3848164`) with `--no-ff`: merge `d8401a9`. The only conflict
  was in `logs/claude.md`; both sides were kept. `experiments/arena/entries/claude.md` kept its Arena 1 part
  (no lines removed).
- `python3 scripts/check.py`: PASS (49 tests). `zlac_joystick_bridge.py`: no diff. No paths or secrets added.
- DISCUSSION T7: named `d8401a9` and recorded Codex's relayed cross-check (codex/workspace `8509c82` at 00:54;
  re-score 97.84 / 60.89 with an empty out_of_scope; check.py 49 on `3848164`; no blocking problem). Codex's own
  post waits for its push approval. The Codex entry `64dbe7f` stays unmerged. T7 open until Codex posts `agree`.
- HANDOFF: branch table (49 tests, `d8401a9`), item 9 merged, Codex task 14 → post the `agree` in T7; lock
  released.
- Not touched: `codex/*`, `claude/workspace`, `main`, PRs.

### 2026-10-22 — integration — Arena 2 closed (01:19 Thai time)
- Codex posted `agree` in T7 at 01:05 (`8311dcb`): re-scored 97.84 / 60.89, 49 tests on `3848164`, no merge blocker. T7 resolved.
- The Claude entry is merged on the hub (`d8401a9`, user's decision). Synced `claude/workspace` with hub `e504153`.
- Open: T1 (Codex model ID, user), T2 (missing code, local), T3/T4 (Codex twin/Gazebo re-runs), T6 (lifted-wheel check on robot day).
  Robot day: the new follow defaults (linear 1.5, angular 0.3/0.8, speed feed-forward) run on the real robot for the first time.

### 2026-10-22 — research / robot — Dashboard Arena 2, Arena 3 draft, thesis review (01:20–02:28 Thai time)
- Dashboard "Follower Test Bench" (https://claude.ai/artifact/JmYTWLwJiiPDRKiG2L1pdS): Arena 2 score card, per-run card
  (final/median gap, closest person), both Arena 2 entries in the replay (judge's seed-0 runs), unit tests 49/49.
- The user shared their unrevised thesis draft (not committed). `claude/research/thesis-review` (`b73d33f`, `804c515`):
  `docs/thesis_review_2026-10-22.md` attacks the validation and methods against the code and twin. Main points:
  - Pearson r(cx, sector) is circular.
  - dt is callback timing.
  - fusion_prob is not the Bayesian model in the draft.
  - There is no data association.
  - The colour plots show no discrimination.
  - The box clips at 0.5 m.
  - Chapter 4 has no following results.
  The review adds revised experiments E1–E7.
- `claude/research/arena3-draft` (`b670e99`):
  - 4 new twin scenarios with a second person.
  - Clothing chroma `[cx, cy, sector, cb, cr]` in the twin, Gazebo and `ros2_yolo_live.py`.
  - Draft scorer v3 with tests.
  - Reference on the current code: 60.6/100 (identity 6/21). In side_by_side the robot drives into the
    standing target, so contact is with the target, not the other person; an earlier message said otherwise.
  - The frozen Arena 2 scorer still validates its data (66.01).
- `check.py` passes 62 tests. Both branches merged into `claude/workspace`.

### 2026-10-22 — integration — Merge the Arena 3 draft and thesis review; open T8 (02:29–02:34 Thai time)
- Model: Claude Opus 5.5 (`integration` subagent). Worktree `/tmp/claude-0/wt_hub`.
- Lock: free (Codex released it at 01:06 after resolving T7). Claimed in `4828120` (02:29), pushed.
- Merged `origin/claude/workspace` (`04782cd`; features `b670e99`, `b73d33f`, `804c515`) with `--no-ff`:
  merge `6698278`. No conflicts.
- `python3 scripts/check.py`: PASS (62 tests). `zlac_joystick_bridge.py`: no diff. No `.docx`, paths or secrets added.
- Re-scores: v3 on the Arena 3 baseline 60.64 (identical JSON); v2 on the Arena 2 reference 66.01; v2 on the judged
  Arena 2 data 97.84 / 60.89.
- RNG preservation: `sim.twin.world` closed-loop traces for every Arena 2 scenario × seeds 0–2 are bit-identical
  between `4828120` and the merge (15 runs, 4,452 detections). ROS pipeline `straight`/`fixed` seed 0
  (02:30–02:34): 2 pre-merge runs and 3 merged runs have the same spread. Temporary images
  `twin:hub-pre`/`twin:hub-a3` were removed; runs kept in `/tmp/claude-0/judge_runs/a3check`.
- `ros2_yolo_live.py`: only in-repo subscriber (`sync_fusion_node.py`) reads `[:3]`. Findings: `sim/README.md`
  set counts out of date (identity 5, everything 9); identity changes made only in `ros2_yolo_live.py` are not
  scored in the twin.
- DISCUSSION: opened T8 (Arena 3 draft; 4 open questions for Codex; not frozen; thesis review pointer).
- HANDOFF: branch table (62 tests), item 11 (T8), Codex task 15, E1–E7 under the robot-day checklist; lock released.
- Not touched: `codex/*`, `claude/workspace`, `main`, PRs.

### 2026-10-22 — integration — Merge T8 finding fixes (02:35–02:35 Thai time)
- Lock claimed in `f5f886a`. Merged `origin/claude/workspace` (`11056a6`, fix `18e703f`) with `--no-ff`: merge `35c161c`; no
  conflicts. `check.py`: PASS (62). The diff touches only `sim/README.md` and the Arena 3 draft.
- T8: one line that both findings are fixed. HANDOFF: branch row and item 11 updated; lock released.

### 2026-10-22 — qa / research — Codex's T8 review (02:44 Thai time)
- Codex (`4e50317`, 02:42) requested one change: the v3 turn check looked only at fixed-bridge rows. Its reproducer
  (one curve_left/diff_drive row with turned=False) kept behaviour at 20.
- `ffba68c` (arena3-draft):
  - The turn check covers both twin bridges and Gazebo, with a regression test; the reproducer now fails the check.
  - `target_tracked_share` is renamed `target_visible_share` (Codex's point 2); the baseline JSON key is renamed, values unchanged (60.64).
  - The draft records Codex's 4 answers, defers occlusion, and states that the colour model is synthetic and that
    `torso_chroma()` takes a box crop.
- `5b535e7` (thesis-review): new section C3 on box-crop contamination (Codex's addition); E4 now measures it.
- `check.py` passes 63 tests.

### 2026-10-22 — integration — Merge T8 review fixes; Claude agrees to the Arena 3 rules (02:44–02:45 Thai time)
- Lock claimed in `3b63b7b` (02:44). Merged `origin/claude/workspace` (`246ec7e`; `ffba68c`, `5b535e7`) with `--no-ff`:
  merge `4aba2f6`; no conflicts. `check.py`: PASS (63). No `ros2_yolo_ws/` changes.
- Verified: v3 baseline 60.64 (identical after the key rename); Codex's reproducer → "curve_left did not turn in
  every run" (the pre-merge scorer gave none); v2 reference 66.01; no `tracked_share` left in code or data.
- T8: change request fixed, all 4 answers accepted, C3 crop limitation added; Claude `agree`; asked Codex for the final
  `agree`; not frozen. HANDOFF: item 11 and Codex task 15 (final T8 review); lock released.

### 2026-10-22 — integration — Freeze Arena 3 (T8) (03:53–03:54 Thai time)
- Codex replied `agree` in T8 (hub `5e1a57b`, 03:37); Claude had already agreed. Lock claimed in `81f54b5` (03:53).
- Freeze commit `08a7ac8` (`arena: freeze Arena 3 rules and scorer`): the draft's title and status line, and the
  `score_entry_v3.py` docstring only. No rule text or logic changes, no renames. `check.py`: PASS (63).
- T8: named `08a7ac8`; entries `claude/robot/arena3-identity` / `codex/robot/arena3-identity` from it; SHA only; no reading
  the other branch until both are in; the integration role judges with `--base-ref 08a7ac8`. T8 open until judging.
- HANDOFF: item 11 frozen; Codex task 16 (build the Codex Arena 3 entry); lock released.

### 2026-10-22 — integration — Post Claude Arena 3 entry SHA (T8) (06:38 Thai time)
- Lock claimed and released; posted only "Claude entry: `claude/robot/arena3-identity` @ `191d2c1` (from `08a7ac8`)" in T8 (ancestry checked; content not read). HANDOFF item 11: both entries in, judging.

### 2026-10-22 — integration — Judge Arena 3 and post the results (T8) (06:38–07:51 Thai time)
- Model: Claude Opus 5.5 (`integration` subagent), acting as judge. Entries: Claude `claude/robot/arena3-identity` @
  `191d2c1`, Codex `codex/robot/arena3-identity` @ `4d22f41`, both from the freeze commit `08a7ac8`.
- Detached checkouts `/tmp/claude-0/judge3_claude` and `/tmp/claude-0/judge3_codex`. Images `twin[-gz]:judge3-<agent>` built
  06:38:15–06:38:20; code hashes match (claude `fb39c440a943`, codex `549f339b37b1`). `check.py`: Claude 72, Codex 69 (PASS).
- Alternating runs 06:38:27–07:49:10 (twin seeds 0–2 with `everything`/`turning`, then Gazebo gz1/gz2); all exit 0.
  Raw runs kept in `/tmp/claude-0/judge_runs/arena3`.
- Scored at 07:49:16 in wt_hub (`167e0c0`), `--base-ref 08a7ac8`: Claude 99.13, Codex 94.13 (contact on crossing/diff_drive,
  3 seeds). Both in scope. Re-scoring the committed raw files gives identical JSON.
- Hub: lock `3955738` (07:50); results and raw data ``; T8 judge reply; HANDOFF item 11 and Codex task 17; lock released.
- Neither entry merged. Not touched: `codex/*`, entry branches, `claude/workspace`, `main`, PRs.
- Correction: the results and raw data commit in the line above is `a57dff7`.

### 2026-10-22 — robot — Arena 3 entry (03:55–06:37 Thai time)
- Branch `claude/robot/arena3-identity` from `08a7ac8`. I did not read Codex's entry (`4d22f41`).
- `TargetGate` in `sync_fusion_node.py`: lock-on, alpha-beta bearing/range gate, soft chroma cost.
- Give way to a person in the corridor who is nearer than the target.
- Self-checks: 94.21 (contact in crossing/diff_drive) → 82.64 (my bug: gave way using a farther person's range) → **99.15** (submitted).
- Details: `experiments/arena/entries/claude.md`. `check.py` passes 72 tests.

### 2026-10-24 — integration — Merge the Arena 3 winner; resolve T8 (16:27–16:27 Thai time)
- Model: Claude Opus 5.5 (`integration` subagent). The user decided to merge the winner (relayed by the coordinator).
  Codex agreed in T8 (`3b6c5ed`, lock released `ea55a26` at 16:16).
- Lock claimed in `78c9115` (16:27). Merged `origin/claude/robot/arena3-identity` (`191d2c1`) with `--no-ff`: merge `efda1b0`.
  The only conflict was in `logs/claude.md`; both sides kept. The entry note merged cleanly (no lines removed).
- `python3 scripts/check.py`: PASS (72 tests). `zlac_joystick_bridge.py` and `follow_stop_node.py`: no diff. No paths or secrets.
- DISCUSSION T8: merge named, Codex's agree recorded, Codex entry `4d22f41` unmerged; T8 **resolved**.
- HANDOFF: item 11 merged/resolved; branch table 72 tests; robot-day note on the target gate (`target_gate:=false` restores
  the old behaviour; gate values tuned in sim, checked in E5); lock released.
- Not touched: `codex/*`, `claude/workspace`, `main`, PRs.

### 2026-10-24 — integration — Arena 3 closed (16:28 Thai time)
- Codex agreed in T8 (`3b6c5ed`). The user decided to merge; the Claude entry is merged on the hub (`efda1b0`); T8 is resolved.
- Synced `claude/workspace` with hub `8f319b8`. `check.py` passes 72 tests.
- Open: T1, T2, T3, T4, T6. Robot day: E1–E7 checklist and the new target-gate note in HANDOFF.

### 2026-10-24 — research / robot — E7, robot-day kit, dashboard Arena 3 (16:35–17:49 Thai time)
- `claude/research/e7-ablation` (`7d9d9a9`, `eb5ec78`):
  - `run_scenario --ros-param` passes parameters to every robot node.
  - E7 runs the Arena 3 winner with each part switched off, 30 identity runs per condition:
    | Condition | Runs passed | Contacts |
    |---|---|---|
    | full | 30/30 | 0 |
    | no colour | 27/30 | 0 |
    | no give-way | 28/30 | 2 |
    | no gate | 12/30 | 8 |
  - Without colour, stand_aside swaps to the bystander, whose geometric cost is about 8.6 against a gate of 9.
  - Write-up: `experiments/sim/2026-10-24_e7_ablation.md`.
- `claude/robot/robot-day-kit` (`5596d34`, `919123e`):
  - `/yolo_frame` from `ros2_yolo_live.py` and from the twin: capture stamp and boxes with conf and Cb/Cr.
  - `tools/robot_day/analyze.py` (E1–E4).
  - `tools/robot_day/turn_check.py` (T6).
  - `docs/robot_day_protocol.md`.
  - Tested end to end on twin bags.
- Dashboard (https://claude.ai/artifact/JmYTWLwJiiPDRKiG2L1pdS):
  - Arena 3 score card, an identity-runs card and an E7 card.
  - The replay now has the second-person scenarios, plus "Before A3" and the Arena 3 entries.
  - Unit tests 83/83.
- Both branches merged into `claude/workspace`; `check.py` passes 83 tests.

### 2026-10-24 — integration — Merge the robot-day kit and E7; open T9 (17:50–17:52 Thai time)
- Model: Claude Opus 5.5 (`integration` subagent). Worktree `/tmp/claude-0/wt_hub`.
- Lock claimed in `367aec9` (17:50). Merged `origin/claude/workspace` (`b165783`; `eb5ec78`, `919123e`) with `--no-ff`:
  merge `0654471`; no conflicts.
- `python3 scripts/check.py`: PASS (83 tests). `zlac_joystick_bridge.py` and `follow_stop_node.py`: no diff. No paths or secrets.
- Frozen scorers: v2 66.01 (reference), 97.84 / 60.89 (Arena 2 judged); v3 60.64 (reference), 99.13 / 94.13 (Arena 3 judged).
- RNG preservation: `sim.twin.world` closed-loop traces for all 9 scenarios × seeds 0–2 bit-identical between `367aec9` and the
  merge (27 runs, 9,609 detections; cx, cy, sector, cb, cr, ranges, final pose).
- E7 table recomputed from the raw JSON with v3 `passes()`: 30/30, 27/30, 28/30 (2 contacts), 12/30 (8 contacts); matches.
- Review: `analyze.py` imports ROS only inside the bag reader. Findings in T9: E2 trusts the camera stamp (no zero/clock check);
  `turn_check.py`'s final zero Twist can fail after Ctrl-C; it does not wait for the subscriber before step 1.
- DISCUSSION: opened T9. HANDOFF: branch table (83 tests), item 12, Codex task 18, robot-day checklist points to the protocol,
  `turn_check.py` and `analyze.py`; lock released.
- Not touched: `codex/*`, `claude/workspace`, `main`, PRs.

### 2026-10-24 — robot — T9 review fixes (17:53 Thai time)
- `c5bc6f4` on `claude/robot/robot-day-kit`, for the integration review's 3 findings:
  - E2 flags capture stamps that are 0, from another clock or in the future (`bad_stamps`), with a test.
  - `turn_check.py` waits for the bridge's subscription before step 1.
  - The final zero command after Ctrl-C no longer raises.
- `check.py` passes 84 tests.

### 2026-10-24 — integration — Merge T9 finding fixes (17:53–17:53 Thai time)
- Lock claimed in `bb23bc2`. Merged `origin/claude/workspace` (`76416dc`, fix `c5bc6f4`) with `--no-ff`: merge `eb10a9c`; no conflicts.
  `check.py`: PASS (84). Reviewed the `analyze.py` (`bad_stamps`) and `turn_check.py` (subscriber wait, guarded stop) diffs.
- T9: one line that all 3 findings are fixed; open for Codex. HANDOFF: branch rows (84 tests), item 12; lock released.

### 2026-10-24 — robot / research — Codex's T9 objection (18:05 Thai time)
- Codex (`3ada59e`) reproduced the E7 counts, then objected on two points:
  - "No gate" also switches off the give-way.
  - E2's capture→cmd_vel figure added two medians.
- `0f27013` (e7-ablation): the write-up now attributes the gate effect to no-give-way vs no-gate (28 → 12 of 30).
  The 30 vs 12 comparison is the whole change against the old pipeline.
- `ab52a3a` (robot-day-kit): E2 end-to-end is per frame. Codex's reproducer is a test: median 110 ms, not 200.
- `check.py` passes 85 tests. The dashboard E7 label is updated to "no gate + no give-way".

### 2026-10-24 — integration — Merge T9 objection fixes (18:05–18:06 Thai time)
- Codex objected in T9 (`3ada59e`). Lock claimed in `6f5861c` (18:05). Merged `origin/claude/workspace` (`b9eddf5`; `0f27013`, `ab52a3a`)
  with `--no-ff`: merge `9ecaecb`; no conflicts. `check.py`: PASS (85).
- Verified: `analyze.e2_latency` on Codex's reproducer gives a per-frame median of 110 ms (p95 191, n 3). E7 per-scenario: the gate
  adds +18 in side_by_side / side_by_side_same / stand_aside and −2 in crossing (no gate 6/6 vs no give-way 4/6); net +16 (noted in T9).
- T9: both points fixed, Claude agrees with Codex's other findings, final `agree` requested. HANDOFF: branch rows (85), item 12,
  Codex task 18; lock released.

### 2026-10-24 — integration — Merge E7 breakdown fix (T9) (18:07 Thai time)
- Lock `38b7de5`; merged `origin/claude/workspace` (`2402e93`) with `--no-ff`: merge `fc2878c`; `check.py` PASS (85). T9 one-line note; lock released.

### 2026-10-24 — integration — T9 closed (18:09 Thai time)
- Codex agreed and marked T9 resolved (hub `e10cd0d`). Synced `claude/workspace` with the hub.
- Resolved: T5, T7, T8, T9. Open: T1 (Codex model, user), T2 (missing code, Windows), T3/T4 (Codex re-runs), T6 (robot day).

### 2026-10-24 — robot / research — Follow one person at walking pace (18:15–19:38 Thai time)
- The user works alone, so the goal is 100% single-person following first. The user decided to lift the bridge's speed cap.
  The user also chose "Claude builds it directly, Codex reviews" instead of an arena.
- `claude/research/solo-following` (`da2f690`, `7cd44c8`, `c53575d`):
  - Twin: 6 solo scenarios at realistic speeds.
  - Bridge: speed_mode "mps" (m/s, wheel_radius_m, 1.4 m/s cap, 1.0 m/s² ramp; legacy kept).
  - follow_stop: max_decel braking cap.
  - sync_fusion: LiDAR tracking after an edge exit (mid-image loss still stops).
  - record_robot_day.sh: --countdown and --duration. New `speed_check.py`, E6 analysis, and a working-alone plan in the protocol.
- Before: 4/10 solo scenarios pass on the hub code. After, on the mps bridge: solo 30/30, identity 15/15 (seeds 0–2).
- Old bridge: Arena 3 lag drops 99.13 → 95.72 because max_decel is in m/s². `max_decel:=0.0` restores it; this is documented.
- `check.py` passes 97 tests. Write-up: `experiments/sim/2026-10-24_solo_following.md`.

### 2026-10-24 — integration — Merge solo following (walking pace); open T10 (19:38–19:42 Thai time)
- Model: Claude Opus 5.5 (`integration` subagent). User decisions relayed by the coordinator: lift the bridge speed cap;
  Claude builds, Codex reviews (no arena).
- Lock claimed in `d957bac` (19:38). Merged `origin/claude/workspace` (`bd83cad`; `da2f690`, `7cd44c8`, `c53575d`) with
  `--no-ff`: merge `c2c7f09`; no conflicts. `check.py`: PASS (97).
- Frozen scorers unchanged: v2 66.01, 97.84 / 60.89; v3 60.64, 99.13 / 94.13.
- Bit-identity: 9 old scenarios × current/fixed/diff_drive × seeds 0–2 (81 runs, 20,495 detections, wheel RPMs, pose)
  identical before/after; `ramp_rpm` no-op outside mps. Legacy `wheel_commands()` identical over 513,611 inputs.
- Solo/identity counts recomputed from raw JSON (30/30, 15/15). Before-count in the write-up is 4/10; raw data gives 5/10.
- Mock test: `record_robot_day.sh --duration` does not stop on Ctrl-C (timeout's own process group); normal path OK.
- Findings in T10: write-up count, Ctrl-C under --duration, no parameter validation (ZeroDivisionError, silent mps on typo,
  speed_mode/max_decel in two nodes), per-wheel ramp shape, int() truncation (negligible), LiDAR closest-return latch.
- DISCUSSION: opened T10. HANDOFF: bridge default note and first drive at max_speed_mps:=0.5 under the robot-day checklist,
  working-alone plan, item 13, item 12 marked resolved (Codex `2b8b119`), Codex task 19, 97 tests; lock released.
- Not touched: `codex/*`, `claude/workspace`, `main`, PRs.

### 2026-10-25 — robot — T10 review fixes (13:46 Thai time)
- Integration's 6 findings on the solo work, fixed in `2463d0c`:
  - LiDAR tracking takes only person-sized clusters.
  - The bridge rejects bad parameters, and both wheels ramp together (twin too).
  - Ctrl-C stops a --duration recording (timeout --foreground plus an INT trap), and exit_code is still written.
  - The write-up's "before" count is corrected to 5/10.
- A transient failure of the server-side command check blocked shell commands for a while; nothing was lost.
- Rerun (`ea4b277`): solo 30/30 and identity 15/15 on mps. side_step improved: visible 0.99, max gap 0.82 m. `check.py` passes 101 tests.

### 2026-10-25 — integration — Merge T10 finding fixes (13:47–13:49 Thai time)
- Lock claimed in `6035509` (13:47). Merged `origin/claude/workspace` (`cfa81be`; `2463d0c` and write-up commits) with `--no-ff`:
  merge `72c7ea9`; no conflicts. `check.py`: PASS (101).
- Bit-identity re-run: 81 runs identical before/after and to `d957bac`. Recorder mock: Ctrl-C with/without --duration stops in
  1 s, exit_code 0; timer only 2 s; real `ros2 bag record` (Humble, twin image) exits 0 on SIGINT.
- `check_params()` runs before the ZLAC is opened. Probe: an oblique crop-row line forms a 0.45 m "wide" cluster and is
  accepted by `lidar_track()` (width ignores depth); noted in T10 as a follow-up.
- T10 note (6 fixes, request for Codex review). HANDOFF: branch rows (101), item 13; lock released.

### 2026-10-25 — robot — Cluster length (13:55 Thai time)
- `d25d3b1`: the LiDAR cluster size is now its end-to-end length, so a row seen at an angle is rejected. Integration's reproducer is a test.
- Twin (mps, seed 0): side_step, turn_90, zigzag and identity 5/5 still pass. `check.py` passes 102 tests.

### 2026-10-25 — integration — Merge T10 cluster length fix (13:55 Thai time)
- Lock `2611587`; merged `origin/claude/workspace` (`38bccba`, fix `d25d3b1`) with `--no-ff`: merge `9915563`; `check.py` PASS (102).
  Row reproducer now 1.40 m long and rejected; a person at 2 m still tracked. T10 one-line note; HANDOFF 102 tests; lock released.

### 2026-10-25 — robot — Codex T10 objection: stale scan (14:15 Thai time)
- Codex (hub `ef3292a`) showed a 4-s-old cached scan still produced a LiDAR-only fix. `2eaba0b`: scans are timestamped and only a scan at most 0.3 s old is used. Codex's case is a test.
- Twin (mps): side_step and turn_90 still pass. `check.py` passes 103 tests.

### 2026-10-25 — integration — Merge T10 stale-scan fix (14:16 Thai time)
- Codex objected in T10 (`00083ca`). Lock `d68b076`; merged `origin/claude/workspace` (`42cc22e`, fix `2eaba0b`) with `--no-ff`: merge `7e79cea`;
  `check.py` PASS (103). Codex's reproducer on the merged node: stale (4 s) and no scan → no publish; fresh (0.1 s) → publishes. T10 reply; lock released.

### 2026-10-25 — integration — T10 closed (14:17 Thai time)
- Codex agreed and marked T10 resolved (hub `f121c6a`). Synced `claude/workspace`.
- Solo following is ready for robot day: twin solo 30/30 and identity 15/15 on mps.
- Robot day starts with the turn check and the wheel measurement, then `speed_check.py`; the first drive is at `max_speed_mps:=0.5`.
- Open: T1, T2, T3/T4, T6.

### 2026-10-25 — research + robot — Twin realism profile and the fixes it found (Offline 1, 14:56 Thai time)
- `44eddb7`: the twin gains an optional `Realism` profile (`run_scenario --realism`):
  - 0.15 s detection latency, 10% missed detections, 3% false positives;
  - LiDAR noise and ray dropout, 5% wheel slip, posts and bushes beside the path.
- With realism off the runs stay bit-identical (hash over every Arena 2 scenario). Unit tests in `tests/test_sim_twin.py`.
- First realism run on hub code (mps, seeds 0–2): solo 19/30, identity 13/15.
- `45d9d29` fixes these robot-code bugs:
  - **TargetGate rate blow-up:** two boxes on one person, about 1 ms apart, lost the target for good. Steps under 0.05 s now update position only.
  - **Gate never unlocked:** it widened with no limit. It now unlocks after 5 s with no fix and locks again only in the start window.
  - **Give-way phantom:** a false box over the target made the robot reverse. It now needs someone ≥ 0.2 m nearer than the target.
  - **Late edge exit:** LiDAR edge tracking also starts when the predicted bearing is past the edge.
  - **Braking:** the cap allows for latency (`latency_s` 0.2).
- After the fixes:
  - realism: solo 27/30, identity 15/15, no contact;
  - clean twin: solo 29/30 (one side_step timing flake, passes on reruns; side_step and zigzag repeats 6/6) and identity 15/15.
- Still failing with realism: zigzag ×2 and side_step ×1. Fixed turn rates plus 0.2 s latency make the robot turn the wrong way. A proportional bearing controller is left for after E2.
- Write-up: `experiments/sim/2026-10-25_twin_realism.md` and `twin_realism_2026-10-25.json`. `check.py` passes 114 tests.

### 2026-10-25 — robot — One-command bringup and preflight (Offline 2, 14:56 Thai time)
- `4fbfc8d`, `ros2_yolo_ws/launch/follow_bringup.launch.py`:
  - starts YOLO, lidar_sectorizer, sync_fusion, fusion_prob, follow_stop and the ZLAC bridge;
  - arguments: speed_mode, max_speed_mps, wheel_radius_m, turn_dir, port, model_path, target_distance, latency_s, bridge:=false (bench), camera_cmd and lidar_cmd;
  - `speed_mode:=legacy` sets max_decel 0.0 by itself, and numbers are always passed as floats.
- New parameters (defaults unchanged): the bridge's `port` and YOLO's `model_path`.
- `tools/robot_day/preflight.py` checks:
  - the model, the serial port, disk space and the parameters;
  - that `wheel_radius_m = X (measured DATE)` is written in `config/motor_wheel_calibration.md`;
  - with `--live`, every topic's rate, the LiDAR content, and `/cmd_vel` publisher and subscriber.
- Tests in `tests/test_preflight.py`. Smoke test in the twin image: every node starts (YOLO only lacks cv_bridge in the image).
- `docs/robot_day_protocol.md`: section "Starting the robot (one command)". E2 now sets `latency_s`.
- For Codex to review: both items above (T11).

### 2026-10-25 — research — Gazebo solo set, thesis ch3–4 draft, dashboard (Offline 3–5, 18:15 Thai time)
- **Gazebo solo set** (`bb24efd`), on `mps`, seeds 0–2, run one at a time: **27/30**.
  - All 3 failures are `come_back`. The person walks back to the robot and comes within 0.39 m, centre to centre, against the 0.40 m contact limit, in every seed. Reversing (1.5·e plus the ramp) is slower than the person walking up.
  - Left for the user to decide whether the robot should back away faster.
  - A first attempt with three Gazebo containers in parallel overloaded the 4-CPU machine (timeouts, nonsense results). It is discarded and noted in the write-up.
  - Write-up: `experiments/sim/2026-10-25_gazebo_solo.md`.
- **Thesis chapters 3–4 draft** (`4d6c584`), `docs/thesis_draft_ch3_ch4.md`:
  - describes what the code runs: YOLOv8n, bearing association, TargetGate, fused confidence (not Bayes), Follow–Stop with the braking cap, and the m/s bridge;
  - drops the circular correlations and the dt claim;
  - reports simulation results as simulation, with ⟦ROBOT DAY⟧ placeholders for E1–E6.
  - The thesis .docx is not committed.
- **Dashboard:**
  - new section "ตามคนเดียว: ทุกท่าเดิน" (solo following, every walking move): scenario × condition, for twin realism before and after the fixes, the plain twin, and Gazebo;
  - new dataset `solo_runs` (120 runs).
- Note: the first integration attempt for T11 stopped on a usage limit after claiming the lock (hub `a4fb5f4`). It is being resumed.

### 2026-10-25 — integration — Merge twin realism, robot fixes, bringup, Gazebo solo, thesis draft; open T11 (14:57–18:48 Thai time)
- Model: Claude Opus 5.5 (`integration` subagent). Lock claimed in `a4fb5f4` (14:57). Work paused for a usage limit and a machine
  restart; the first, uncommitted merge of `172e06e` was aborted and redone on `0526ab3` (no code changes after `172e06e`).
- Merged `origin/claude/workspace` (`0526ab3`) with `--no-ff`: merge `b23ec2b`; no conflicts. `check.py`: PASS (114).
- Bit-identity (realism off): 81 old-scenario runs on current/fixed/diff_drive identical to `a4fb5f4` and `d957bac`.
- Twin runs (image `twin:hub-t11`, 14:58–15:45, overlapping the coordinator's Gazebo jobs; then `twin:hub-t11b` on an idle machine,
  18:14–18:47, solo only): clean solo 29/30 (side_step s0), realism solo 29/30 with 1 contact (come_back s2, 0.355 m),
  identity 15/15 both. Arena 3 protocol on old bridges with new code: 94.46 (lag only; legacy caveat). Raw runs in
  `/tmp/claude-0/judge_runs/t11` and `/tmp/claude-0/judge_runs/t11q`.
- Probes: `min_rate_dt` 0.05 disables rate estimation at ≥25 fps; `unlock_after_s` re-locks on any person in the lock window.
- DISCUSSION: opened T11 (5 review points, thesis-draft accuracy request, come_back 0.39 m as a design question for the user).
  HANDOFF: branch rows (114), item 14, Codex task 20; lock released.
- Not touched: `codex/*`, `claude/workspace`, `main`, PRs.

### 2026-10-25 — robot — T11 integration findings (18:55 Thai time)
- Integration (hub `5d95e69`) found that the write-up's "realism: no contact" did not reproduce: `come_back` with realism, seed 2, came within 0.355 m. The write-up is corrected. This is the same design question as Gazebo's 0.39 m and is put to the user.
- **Finding 1:** `min_rate_dt` 0.05 switched off rate estimation at 25 fps or more. It is now 0.015 s, with a test at 10, 30 and 60 fps. `check.py` passes 115 tests.
- **Findings 2–5** (re-lock on anyone after 5 s, predicted-edge rule, give-way gap, latency cap using the command and not the wheel speed) are left for Codex's T11 review.

### 2026-10-25 — integration — Merge T11 min_rate_dt fix (18:51 Thai time)
- Lock `e54479d`; merged `origin/claude/workspace` (`5e3a90d`) with `--no-ff`: merge `fba0d89` (log conflict, both sides kept); `check.py` PASS (115).
- Rate reproducer: 0.300 rad/s at 10/20/25/30/60 fps. come_back and side_step (mps, seed 0, sequential, idle machine): both pass.
- T11 one-line note (finding 1 fixed; 2–5 wait for Codex). HANDOFF: item 13 marked resolved (T10), branch rows (115), item 14; lock released.

### 2026-10-25 — robot — Codex T11 objection (19:40 Thai time)
- `88efdd4` answers Codex's objection:
  - **Braking cap:** it now uses an estimated wheel speed (the bridge ramp towards the last command, parameter `bridge_accel_mps2`, set from the launch file's `max_accel_mps2`), not the command. Tests cover Codex's example.
  - **Thesis draft:** corrected to `min_rate_dt` 0.015 s; the mid-image stop now applies only when the target is not moving sideways; the cap is described as an estimate with the `max(0, ·)` clamp; the re-lock and give-way caveats are added; both realism runs are reported.
  - **Robot-day protocol:** gets Codex's operator notes (first drive `straight` at 0.5 m/s; `come_back` last; the re-lock rule).
- **Re-run, one job at a time:** twin realism solo 27/30, no contact (`come_back` 0.42–0.44 m, was 0.355). Gazebo `come_back` is still 0.39 m: the person walks up while the robot is reversing. That is the open design question for the user. `check.py` passes 117 tests.

### 2026-10-25 — integration — Merge T11 objection fixes (19:34–19:37 Thai time)
- Codex objected in T11 (`5e4730d`). Lock `0baff08`; merged `origin/claude/workspace` (`15036d0`, fix `88efdd4`) with `--no-ff`: merge `f52e73f`
  (log conflict, both sides kept). `check.py`: PASS (117). Realism-off bit-identity: 81 runs identical.
- Codex's braking example through `speed_command`: cap 0.0 with the wheel estimate (0.32 with the command). Thesis draft checked for
  0.015 s, the clamp and both realism runs. come_back and side_step (mps, seed 0, sequential): pass.
- T11 reply asking Codex to re-check. HANDOFF: branch rows (117), item 14; lock released.

### 2026-10-25 — integration — T11 agreed (19:55 Thai time)
- Codex replied `agree` (hub `65f577a`) to the T11 objection fixes. Its reproducer: the old command value gives a 0.566 m/s cap, and the wheel-speed estimate gives 0. `check.py` passes 117 tests.
- `claude/workspace` is synced with the hub (`a6615af`).
- Still open, for the user: Gazebo `come_back` reaches 0.39 m when the person walks up to the robot. The choices are to back away faster, or to let the person come close.

### 2026-10-25 — decision — come_back (20:10 Thai time)
- User's decision: do not change the code now. On robot day, do `come_back` last and walk back to the robot slowly at first. Then choose between backing away faster and letting the person come close, based on the real robot.

### 2026-10-25 — robot + research — Bearing steering, Thai cheat sheet (Offline extra 1 and 3, 21:30 Thai time)
- **`follow_stop` `steer_mode:=bearing`** (default still `sector`):
  - turn rate ω = 2.5·θ̂, limited to 0.8 rad/s, where θ̂ is the camera bearing predicted over `latency_s`;
  - 3° deadband;
  - LiDAR edge fixes turn at the sector rate.
- **Tuning.** A 1.2 rad/s limit spun the robot past the target in `side_step`, and the jump to the image edge spoiled the rate estimate. Both are handled.
- **Results** (`mps`, seeds 0–2, one job at a time):
  - twin realism solo: `sector` 27/30 → `bearing` 29/30, no contact (`zigzag` 1/3 → 3/3);
  - identity: 15/15 in both modes;
  - clean twin: 29/30 and 15/15. The one clean `come_back` 0.37 m did not reproduce in 4 reruns (0.43 m).
- Write-up: `experiments/sim/2026-10-25_bearing_steer.md`. The launch file passes `steer_mode`.
- **`docs/robot_day_cheatsheet_th.md`:** a one-page Thai robot-day sheet, with a slot to compare the steering modes.
- `check.py` passes 119 tests.

### 2026-10-25 — research — E7 re-run, thesis update, dashboard (Offline extra 2 and 4, 22:50 Thai time)
- **E7 re-run** on current code (identity set, `fixed`/`diff_drive` with `max_decel:=0.0`, seeds 0–2, one job at a time):

  | Condition | Passed | Contacts |
  |---|---|---|
  | full | 30/30 | 0 |
  | no colour | 27/30 | 3 (`crossing` on `diff_drive`, 0.39–0.40 m) |
  | no give-way | 29/30 | 1 |
  | no gate | 12/30 | 12 |

  The conclusions are unchanged. The addendum is in `experiments/sim/2026-10-24_e7_ablation.md`.
- **Thesis draft:**
  - 4.7 table updated (first run and current code);
  - 3.3.6 describes the optional bearing steering;
  - 4.6 reports the re-run after the wheel-speed cap (27/30, no contact) and bearing steering (29/30).
- **Dashboard:** the "ตามคนเดียว" (solo following) chart adds "สมจริง · หลังแก้" (realism after the fixes, wheel-speed cap) and "สมจริง · เลี้ยวตามมุม" (realism with bearing steering). Dataset `solo_runs` has 150 runs.

### 2026-10-25 — integration — Merge bearing steering, E7 re-run, thesis, cheat sheet; open T12 (22:22–22:26 Thai time)
- Model: Claude Opus 5.5 (`integration` subagent). Lock claimed in `47f017a` (22:22). Merged `origin/claude/workspace` (`b07d679`) with
  `--no-ff`: merge `14c263c`; no conflicts. `check.py`: PASS (119). The merge includes a one-line `CLAUDE.md` change (talk to the user in Thai).
- Bit-identity (realism off, default steering): 81 old-scenario runs identical to `d957bac`.
- Twin realism mps seed 0, sequential (22:23–22:25): sector zigzag/side_step pass; bearing zigzag pass, bearing side_step FAIL
  (final 3.12 m, visible 0.13), matching the write-up's one realism failure. Raw runs in `/tmp/claude-0/judge_runs/t12`.
- Recount: bearing and E7 re-run tables match their JSON; the bearing write-up wrongly lists side_step seed 0 as a clean failure.
- DISCUSSION: opened T12 (3 review points; robot-day trial question; thesis check). HANDOFF: branch rows (119), item 15, Codex task 21;
  lock released. Not touched: `codex/*`, `claude/workspace`, `main`, PRs.

### 2026-10-25 — robot — Codex T12 objection (23:55 Thai time)
- `follow_stop` in `bearing` mode now stops after `target_timeout_s` 0.3 s without a target message. Before, the bridge held the last turn for 1 s. Unit test `target_is_stale`; `sector` mode is unchanged.
- Thesis: 3.3.6 describes the stop, and 4.7 states that `target_gate:=false` also disables give-way (29/30 against 12/30 isolates the gate).
- Re-run (`bearing`, `mps`, seeds 0–2, one job at a time):
  - twin realism solo **30/30** and identity 15/15;
  - clean solo **30/30**;
  - no contact anywhere;
  - `target_loss` now stops in 0.4–0.7 s.
- `check.py` passes 120 tests.

### 2026-10-25 — integration — Merge T12 objection fixes (23:53–23:55 Thai time)
- Codex objected in T12 (`f36336d`). Lock `6d46675` (23:53); merged `origin/claude/workspace` (`c53e7b8`) with `--no-ff`: merge `ac28ea7`
  (log conflict, both sides kept). `check.py`: PASS (120). Bit-identity (default sector, realism off): 81 runs identical.
- Twin realism mps bearing seed 0, sequential: side_step pass (was 3.12 m fail), target_loss pass, stop in 0.5 s; [STALE] stops logged.
- T12 reply asking Codex to re-check. HANDOFF: branch rows (120), item 15; lock released. Raw runs in `/tmp/claude-0/judge_runs/t12b`.

### 2026-10-26 — integration — T12 agreed (00:20 Thai time)
- Codex replied `agree` and marked T12 resolved (hub `022d462`). `bearing` may be tried on robot day after the `sector` runs, at `max_speed_mps:=0.5`, with its behaviour recorded. `sector` stays the default.
- `claude/workspace` is synced with the hub. The Thai cheat sheet's bearing slot is updated to match.

### 2026-10-26 — dashboard — Follower Test Bench v2 (00:30 Thai time)
- The user asked for a better UI, built separately so the old one can be compared; the old dashboard is not changed.
- New dashboard: https://claude.ai/artifact/HTGBVGXXgFjr4S39zD1qA1. Its tabs are พร้อมลงพื้นที่ (ready for robot day), ตามคนเดียว (solo following), เลือกให้ถูกคน (target identity), เล่นซ้ำ (replay), ประวัติ Arena (Arena history) and เทสต์และ CI (tests and CI).
- **First page:** solo-following pass counts and the closest approach to the person per walking move (against the 0.40 m contact line), plus robot-day steps and open questions.
- **Data:** the same as the old dashboard, plus the latest bearing-steering run (30/30), the E7 re-run (with a toggle between the first run and current code) and the current unit tests (120).

### 2026-10-26 — research — Static-object filter from the re-identification paper (01:40 Thai time)
- The user asked whether the system uses the paper *Multi-modal Bayesian Learning, Re-identification and Tracking of a Target Person for Mobile Robots*.
  - Answer: segmentation yes; scan registration, the dynamic-object filter and online re-identification no.
  - The user asked to try the filter.
- Built on `claude/robot/static-filter` (not merged):
  - `StaticMap` in `sync_fusion`, off by default;
  - twin scenario obstacles and the `side_step_bush` scenario;
  - unit tests (123 pass). Old scenarios are bit-identical.
- **Result:** not adopted. The robot never chased the bush without the filter. The filter made the clean twin worse (3/3 → 1/3), likely because dead reckoning from `/cmd_vel` makes a followed person look static. It needs real wheel odometry or scan registration first.
- Write-up: `experiments/sim/2026-10-26_static_filter.md`.

### 2026-10-26 — dashboard — Static-filter trial as a graphic (05:55 Thai time)
- Dashboard v2 gets a "ทดลองตัวกรอง" (filter trial) tab:
  - a pass bar chart, filter off against on, for the three test sets;
  - side-by-side top-down maps of `side_step_bush` (robot path, target path, bush), with test-set and seed buttons and a time slider with play.
- New datasets: `static_filter_paths` and `static_filter_runs`.

### 2026-10-26 — dashboard — Paper-style LiDAR view in the filter trial (06:05 Thai time)
- The "ทดลองตัวกรอง" (filter trial) tab now draws, under each top-down map, the LiDAR frame at the chosen time, in the style of the paper's Figure 5:
  - black background;
  - static points white, moving points green;
  - person-sized clusters boxed: the target in yellow, static person-sized clusters in red;
  - the camera's field of view shaded.
- The frames are rebuilt from the logged poses with the twin geometry (no noise) and labelled by the branch's own `StaticMap`; dataset `static_filter_scans`.
- The frames show the failure: at the start the standing target is "static", and while the robot turns the bush reads as "moving" (dead reckoning from `/cmd_vel`).

### 2026-10-26 — dashboard — Fix: filter-trial LiDAR pane stopped the page (06:15 Thai time)
- Error: `fr.points.forEach is not a function`. Nested lists in a file dataset arrive as JSON text. The pane now parses `points` and `boxes` (and `t` as a number) before drawing. Page version 6.

### 2026-10-26 — dashboard — Fix: filter-trial LiDAR drawn over the time slider (06:25 Thai time)
- The LiDAR pane and the top-down map in the filter-trial tab now set their pixel width and height and clip their drawing. Before, the drawing overflowed onto the legend and the time slider.
- The black LiDAR panel has a border, so it shows on the dark theme. Page version 7.

### 2026-10-26 — dashboard — Walls and per-point matching in the filter-trial LiDAR (06:40 Thai time)
- Two crop-row walls are added to the rebuilt LiDAR frames, **for the picture only** (they were not in the runs).
- Each point is now labelled the way the paper does it: static if it matches the scan 1 s earlier.
  - The matching is done twice: with the pose dead-reckoned from `/cmd_vel` (what the robot has) and with the true pose (what odometry would give).
  - A button switches between them.
- With the true pose the walls stay static apart from areas just revealed behind the moving person. With the command-based pose they turn "moving" while the robot turns or accelerates.
- Boxes still show the actual `StaticMap` decision. Page version 8.

### 2026-10-26 — research + dashboard — 2D point-cloud maps and scan matching (07:20 Thai time)
- The filter-trial tab now draws a world-frame 2D point-cloud map per pane, as the user asked:
  - scans once a second over the last 3 s;
  - three crop-row walls added for the picture only;
  - each point is white (static) or green (moving), matched against scans 0.5–1.5 s earlier.
- The pose that lays the scans down can be switched between:
  - dead reckoning from `/cmd_vel`;
  - 2D ICP scan matching against a keyframe refreshed every second, as in the paper;
  - the true pose.
- **End-of-run pose error:** ICP 0.02–0.11 m in all 18 runs. Dead reckoning is 0.03–0.17 m in most runs but up to 1.3 m in some.
- **Bug found and fixed on `claude/robot/static-filter` (`08eb36b`):** `StaticMap` kept integrating the last `/cmd_vel` after follow_stop went quiet, while the bridge had stopped the wheels after 1 s. It now ignores commands older than 1 s. The trial runs on the dashboard predate this fix.
- **Next, if wanted:** put ICP scan matching into `StaticMap` instead of dead reckoning and rerun the trial.

### 2026-10-26 — research — Static filter re-run after the stale-command fix (07:35 Thai time)
- With `08eb36b` (ignore `/cmd_vel` older than 1 s), filter off and on were both re-run from one image, one job at a time:
  - `side_step_bush`: off **5/9**, on **9/9**;
  - the 10 solo moves with realism: off 26/30, no contact; on 25/30, 3 contacts.
- The contacts are not the filter: `walk_1p0` seeds 0 and 2 re-ran at ≥ 0.52 m, seeds 3–7 pass 5/5 both ways, and `come_back` is the known open question.
- Write-up updated (`experiments/sim/2026-10-26_static_filter.md`).
- The dashboard filter tab is rebuilt from the new runs and adds a "ท่าคนเดียว 10 ท่า" (10 solo moves) row. The point-cloud maps now come from these runs: ICP ends within 0.02–0.12 m, dead reckoning within 0.06–1.16 m.
- The filter stays off by default on its branch; it needs review and a robot check.

### 2026-10-26 — research — Read the Kim, Suh and Kwon (2024) paper (12:35 Thai time)
- The user pushed the paper to `codex/robot-backup-quarantine:Paper/` (Git LFS). I read it from a scratch copy; that branch is untouched and the PDF is not copied elsewhere.
- `docs/paper_comparison_kim2024.md` covers:
  - what the paper does: online GMM colour re-identification, ICP-based dynamic non-target detection with a wheel-odometry guess, GNN tracking, and a particle filter with a negative factor for non-targets;
  - how our system compares;
  - what to take from it: wheel odometry as the ICP guess, CT/CL/WT/WL states for E5 and E6, the negative factor, online colour learning;
  - a draft paragraph for thesis chapter 2.
- The paper is an SSRN preprint and has not been peer reviewed.

### 2026-10-26 — robot + research — ICP pose in the static filter, measured (15:15 Thai time)
- **Branch `claude/robot/static-filter`. It is not merged, and the filter stays off by default.**
  - `4e365a9`: `static_pose:=icp` corrects `StaticMap`'s pose with keyframe ICP, using `/cmd_vel` as the guess and fallback. It also adds twin walls and the `side_step_rows` scenario.
  - `1dd263a`, `1e802dc`: `[STATIC]` log every 2 s with the pose, ICP match and failure counts, and the clusters dropped from LiDAR tracking.
  - `c14fb1f`: the ICP keyframe leaves out person-sized clusters that are not static yet. In the clean `side_step_bush` the pose had locked onto the walking person (3.5 m and 110° off). With the fix it stays at 0.11–0.48 m and falls back to the guess instead. `lidar_clusters` is split into `lidar_groups` for reuse.
  - 127 tests pass.
- **Twin (`mps`, `bearing`, seeds 0–4 × 2 repeats):** filter off 27/40, ICP 27/40, no contact.
  - The same seed often flips between repeats, so the filter's effect cannot be separated.
  - Every failure is the target lost after it steps out of view.
- **ICP pose with walls:** about 0.07 m, against up to 1.6 m for `/cmd_vel` with slip.
- **Regression with ICP:** solo 28/30, where the two failures are `come_back` s2 (contact, 0.40 m) and `side_step` s2. Identity 15/15.
- **Conclusion:** keep it off. For the thesis it is future work, with ZLAC wheel feedback as the ICP guess.
  - Write-up: `experiments/sim/2026-10-26_static_filter.md` (Update 2).
  - Dashboard v2, filter tab: new card, dataset `icp_trial_runs`, page version 11.

### 2026-10-26 — research — Clothing colour on the two 2025-04-08 lab videos (22:05 Thai time)
- **Task:** at the user's request, I used `Videos/WIN_20250408_14_00_41_Pro.mp4` and `WIN_20250408_14_10_21_Pro.mp4` from `codex/robot-backup-quarantine`.
  - They came through Git LFS into a scratch copy. That branch is untouched and the videos are not copied into the repository.
- **Data:**
  - Ran the project's YOLOv8n OpenVINO model at 10 fps (914 person boxes) and took each box's torso Cb/Cr, as in `ros2_yolo_live`.
  - Labelled every box by eye: blue top, dark top, or other.
- **Result:** with colour only, the blue-top person is the target and both people are in view.
  - Our Cb/Cr reference ranks the target first in **14–26 %** of frames.
  - The paper's H,S GMM, re-learned from the last 10 boxes, ranks it first in **78–92 %**. Learned once, 58–67 %.
  - With the dark top as the target, both methods reach 88–100 %.
- **Cause:** the blue top reads grey (Cb 128–132) in shade and backlight, which is 26–28 % of its boxes. Lock-on also happened in backlight.
- **Cost:** the GMM re-fit with BIC takes about 0.7 s on 4 cores, so it cannot re-fit every frame.
- **Files:** `experiments/identity/lab_videos_2025-04-08/` (README, scripts, labels, detections, H,S samples).
- **Next, if wanted:**
  - try an H,S colour model in `TargetGate`, re-fit once a second or with a fixed k;
  - re-check on E4 robot-day data.

### 2026-10-26 — robot + research + dashboard — H,S colour histogram in the target gate (23:10 Thai time)
- **Branch `claude/robot/hs-colour` (`f28b011`, `a936d3f`). It is not merged.**
  - `ros2_yolo_live` appends a 12×4 torso hue-saturation histogram after `cb, cr`.
  - `TargetGate` scores colour as half Cb/Cr and half histogram.
    - The histogram is a Hellinger distance to the mean of the target's last 10 learned boxes, with σ 0.2.
    - A box is learned only if it is about as close as those already learned (slack 0.1).
    - `use_hs_hist:=false` goes back to Cb/Cr only. Without a histogram, Cb/Cr counts in full.
  - **Twin:** a matching histogram is drawn from the observed chroma on its own random stream. Every other value is bit-identical, checked open-loop over all scenarios with and without realism.
  - **New `colour` scenario set:** `shade_crossing` and `shade_side_by_side`. The identity set is untouched.
  - 125 tests pass.
- **Evidence:** `experiments/identity/clothing_colour_videos/`, renamed from `lab_videos_2025-04-08`.
  - **Lab clips, colour only, target ranked first:** blue target 14–26 % → 97–99 %; grey target 88–99 % → 97–99 %.
  - **Five held-out clips from `Videos/`** (parking lot, greenhouse path):
    - the histogram alone lost a black tee (37 % kept), so half-and-half was adopted;
    - kept own person 90–100 % (Cb/Cr 99.7–100 %);
    - strangers from other clips ranked below own person 65.9 % (Cb/Cr 60.1 %).
  - **Caveat:** half-and-half was chosen after seeing the held-out clips, with 5 variants tried. E4 on robot day is the real test.
- **Twin closed-loop runs** (colour set, plus identity/solo regression, histogram on and off) are still running. They will be added here and to the dashboard.
- **Dashboard v2:** new tab "สีเสื้อ" (clothing colour) with a crop montage, a Cb/Cr scatter, the methods chart and the held-out chart (page version 12).

### 2026-10-27 — robot + research + dashboard — Colour histogram: twin fixes and results (02:51 Thai time)
- **Branch `claude/robot/hs-colour`:**
  - `34fdcdf`: the twin histogram keeps saturation in shade, calibrated on the lab video.
  - `2547f8b`: `TargetGate` takes a lost target back by colour (paper Algorithm 1): unseen ≥ 1 s, colour cost ≤ 2.0, within 35° of the predicted bearing, histogram only.
  - 127 tests pass.
- **Root cause found with a gate debug log:**
  1. A crosser in shade was accepted once (Cb/Cr cost 1.5).
  2. The track's rates ran off to −30° and −0.27 m.
  3. After the 5 s unlock, the target could only be re-locked at 0.5–1.0 m.
  - This is an old gate weakness and happens with Cb/Cr only too.
- **Twin (`2547f8b`, histogram off → on):**
  - `shade_crossing` realism: 5/10 → 10/10;
  - solo realism: 26/30 (1 contact) → 29/30 (no contact);
  - identity: 15/15 → 15/15;
  - the other colour-set rows: 10/10 both ways;
  - with bearing steering and the histogram on: solo 29/30 (`come_back` s2 contact), identity 15/15.
- **Write-up:** `experiments/sim/2026-10-27_hs_colour_twin.md` and `.json`.
- **Dashboard v2:** "สีเสื้อ" (clothing colour) tab gains a twin card (dataset `colour_twin`, page version 13).
- **Status:** the branch is still not merged. It needs Codex review and E4 on robot day. I have authorisation from the user to keep running and fixing.

### 2026-10-27 — research + robot + dashboard — Crowd video, histogram weight 0.25, dashboard fixes (13:53 Thai time)
- **Dashboard v2, "สีเสื้อ" (clothing colour) tab:**
  - the Cb/Cr scatter no longer spills over the card: axes now come from the data, and the dots are clipped;
  - bar-chart legends wrap as HTML instead of overlapping;
  - all colour cards were rendered in Chromium (wide and phone width) with the real data before publishing;
  - new cards: the vtest crowd and the weight sweep (page version 15).
- **No other videos exist on any branch**, and MOT Challenge and Hugging Face are blocked by the network policy.
  - Used OpenCV's `vtest.avi` from raw.githubusercontent.com, which is PETS 2009 S2.L1 view 1.
  - Labelled 5 recognisable people by eye after splitting the swapping tracklets; the rest are "other".
  - Colour only, own person ranked first (chance 17 %): Cb/Cr 25.9 %, histogram alone 69.8 %, histogram + Cb/Cr 52.8 %, GMM 13.1 %.
- **Weight sweep over all three video sets** (`weight_sweep.py`).
  - `hist_weight` 0.25 keeps every held-out person as well as Cb/Cr (worst 99.7 % vs 89.8 % at 0.5) and keeps the lab gain (96.9 %).
  - Chosen after seeing every set; robot-day E4 is the real test.
- **Branch `claude/robot/hs-colour` (`47553e5`):** `hist_weight` 0.25 and `reacquire_colour_max` 1.0 (79 % of the target's boxes, 2.2 % of others'). 127 tests pass.
- **Twin rerun with `47553e5` is running** (same 215 runs as before). Results and the dashboard twin card follow.
- **Files:** `experiments/identity/clothing_colour_videos/` (README sections "Third set" and "Choosing the histogram's weight", `results_*.txt`).

### 2026-10-27 — dashboard + research — Example images from every test video (14:11 Thai time)
- **Dashboard v2, "สีเสื้อ" (clothing colour) tab** gains a gallery card with one button per video (page version 16).
  - The 7 clips plus vtest, each a strip of crops from the original frames, spread over the clip.
  - Each crop shows its measured Cb/Cr and time.
  - Rendered in Chromium at wide and phone width before publishing.
- **Label fix in `labels_WIN_20241210_13_47_33_Pro.json`**, found from the gallery:
  - boxes 424 and 426 are the beige-tee target (they had O and X);
  - box 436 is the passing worker (it had X).
  - Re-running `heldout.py`, `variants_heldout.py` and `weight_sweep.py` changes only a few pairwise strangers values by ≤ 0.3 points; every summary number is unchanged.
- **Script:** `gallery.py` builds the strips.

### 2026-10-27 — research + dashboard — Colour separability per clip (14:42 Thai time)
- The user asked for a per-clip analysis of how far colour can tell the target from others. Added `separability.py`, which reports the AUC of the gate's colour cost (target box vs other people's boxes) per clip, for Cb/Cr, histogram and the gate's mix.
- **Mix (`hist_weight` 0.25):**
  - ≥ 0.85 in 11 of 14 clip/target cases;
  - fails on black tee 1 (0.36: hue is noise on black) and on the crowd's red top (0.06: Cb/Cr's grey bias on tiny crops);
  - Cb/Cr alone is below 0.5 in 5 cases.
- **Dashboard v2, "สีเสื้อ" (clothing colour) tab:** new card with an AUC overview for every clip, and a per-clip view (page version 17).
  - The per-clip view shows the AUC verdict, the target's and nearest other's colour cost over time with confusion shaded, and the Cb/Cr scatter.
  - Rendered in Chromium before publishing. A bug where the time axis ran backwards on one-person clips was found and fixed: stranger boxes carried another clip's time.

### 2026-10-27 — dashboard — One "photo + Cb/Cr" view per clip (15:09 Thai time)
- At the user's request, the first "สีเสื้อ" (clothing colour) card is now a per-clip viewer covering all 8 videos (page version 18). For each clip it shows:
  - crops from the original frames with their Cb/Cr;
  - the clip's Cb/Cr scatter, coloured per person after their clothes;
  - for one-person clips, other clips' people as faint grey for reference;
  - a short verdict with the separability AUCs.
- The separate gallery card was merged into it.
- **New dataset:** `colour_clip_points`.
- Rendered in Chromium for every clip at wide and phone width: no dots outside the plot, no page errors.

### 2026-10-27 — robot + research — "Bayesian" naming fixed; identity belief tried and not adopted (16:22 Thai time)
- **The user asked whether the system uses anything Bayesian. It does not**, although two places were named so.
  - `fusion_prob` is a weighted mean of two heuristic scores with time smoothing.
  - `follow_stop`'s "sector prior" is turn hysteresis.
  - The thesis draft already said so.
- **The user chose: (1) fix the naming, then (2) try a light, real Bayesian piece.**
  1. `claude/robot/naming` (`27fb26d`): comments only. 120 tests pass.
  2. `claude/robot/identity-belief` (`d282995`, `003f033`, `6102615`), built on `claude/robot/hs-colour`.
     - What it adds: a recursive Bayes belief that the gate's box is still the locked-on person.
       - Likelihood ratio = geometry (χ²(2) vs uniform, held to 0.3–1.5) × a colour table measured on the videos.
       - Switch probability 0.01.
       - With `identity_belief:=true` (default false), the gate waits for a colour match below 0.15.
     - 131 tests pass.
- **Videos** (leave one clip out):
  - wrong takes fall from 29.2 % to 20.0 %, but the target is kept in only 87 % of frames (worst 10.9 %);
  - no threshold avoids this;
  - as a report-only signal, AUC 0.50.
- **Twin, realism, belief on vs off:**
  - `shade_crossing` 1/10 vs 10/10;
  - `shade_side_by_side` 9/10 (1 contact) vs 10/10;
  - identity 15/15 both;
  - solo 28/30 vs 27/30.
- **Cause:** the belief rests on the same colour evidence the gate uses to choose, so it rises with a wrong pick and falls when the target's own colour changes (deep shade). It needs an independent cue.
- **Decision:** keep it off; the branch stays as a measured negative result. Write-up: `experiments/sim/2026-10-27_identity_belief.md` (+ `.json`).
- **Twin with the histogram at 0.25 (`47553e5`, belief off):** `shade_crossing` realism 10/10 (9/10 without histogram), solo 27/30 (24/30). Dashboard twin card updated (page version 19).

### 2026-10-27 — workspace — Colour gate and naming merged into the workspace for review (16:50 Thai time)
- The user asked to send the colour work to Codex for review.
- Merged into `claude/workspace`:
  - `claude/robot/hs-colour` (`815ec79`): H,S histogram at a quarter weight, colour re-acquisition and the twin `colour` set;
  - `claude/robot/naming` (`ad9cafb`): comments only.
  - 127 tests pass.
- Not merged, kept as measured negative results: `claude/robot/identity-belief` and `claude/robot/static-filter`.
- Next: the `integration` subagent merges `claude/workspace` into `integration-hub` and opens T13 for Codex.

### 2026-10-27 — integration — Colour gate and naming merged into `integration-hub`, T13 opened (16:55 Thai time)
- Lock claimed on `integration-hub` in `4a80e8d` and pushed before the merge.
- Merged `claude/workspace` (`fbf3e73`) into `integration-hub` with `--no-ff`: merge `e48ae4c`. No conflicts.
- Checks on the merged hub:
  - `python3 scripts/check.py` passes, 127 tests.
  - Open-loop twin, hub before (`4a80e8d`) vs after (`e48ae4c`): all 15 pre-merge scenarios, seed 3, 150 steps,
    scan + detections without `hist` + state hashed at every step. Bit-identical: plain `e8cb4b58…`, realism `f749aa20…`.
  - Diff review: no new publishers or wheel commands; no machine paths or secrets.
  - Docker closed-loop spot-check not run (Docker is not running in this session).
- Opened **T13** in `DISCUSSION.md` (`44021e4`) for Codex, with five review points.
- `HANDOFF.md` updated (T12 marked resolved, T13 added, branches table) and lock released in `1636bfd`.

### 2026-10-27 — robot/research — T13 change request addressed: re-acquisition distance rule (18:35 Thai time)
- Codex's review of T13 asked for a change: re-acquisition took a same-clothing stranger at 18°, 7.43 m after 1.2 s unseen.
- `claude/robot/hs-colour` `808dc6c`:
  - re-acquisition now requires the detection to be within 0.8 m + 1.5 m/s × time unseen (cap 3 m) of the last place seen (T_dist, Algorithm 1);
  - 2 gate tests (Codex's case; reach grows and is capped);
  - twin: per-person camera-hidden windows plus scenario `lookalike_after_loss`, with a test. Earlier scenarios are bit-identical (open-loop hash).
- Merged into `claude/workspace` (`45588d5`).
- README (`ecf573a`):
  - 1.0 is stated as not independently validated;
  - the predicted-place claim is corrected: different clothes are rejected (Codex's cost 10.13); same clothes are not.
- **Closed-loop twin with the rule on (Docker, one at a time):**
  - `shade_crossing` 10/10 and `shade_side_by_side` 10/10 (realism);
  - identity 15/15;
  - solo 27/30, no contact.
- **`lookalike_after_loss`:** 9/10 with the rule and 9/10 without.
  - Its failures come from an older weakness: the far look-alike's box borrows the near target's LiDAR range, so the widened normal gate takes it.
  - Written up as a limitation, with a follow-up proposed.
- Results: `experiments/sim/2026-10-27_hs_colour_twin.md` (`765338a`) and `_t13.json`. `check.py`: 130 tests pass.

### 2026-10-27 — integration — T13 change-request fixes merged into `integration-hub` (18:40 Thai time)
- Lock claimed on `integration-hub` in `78dd152` and pushed before the merge.
- Merged `claude/workspace` (`c750734`) into `integration-hub` with `--no-ff`: merge `b102cc7`. No conflicts.
- Checks on the merged hub:
  - `python3 scripts/check.py` passes, 130 tests.
  - Open-loop twin, hub before (`78dd152`) vs after (`b102cc7`): all 17 pre-merge scenarios, seed 3, 150 steps.
    Bit-identical: plain `cb1dc949…`, realism `e96c7f3c…`.
  - Both new gate tests fail with the distance rule disabled, and pass with it on.
  - Recounted `experiments/sim/2026-10-27_hs_colour_twin_t13.json` (85 rows); it matches the stated results.
  - Diff review: no new publishers or wheel commands; no machine paths or secrets.
- Replied in **T13** in `DISCUSSION.md`, answering Codex's six points; status stays open, and Codex is asked to re-review.
- `HANDOFF.md` updated (T13 waiting for Codex's re-review, branches table) and lock released.

### 2026-10-27 — integration — Codex's T13 re-review recorded; T13 resolved (18:55 Thai time)
- Lock claimed on `integration-hub` in `6b6c0d5` and pushed before editing.
- Codex re-reviewed T13 but could not commit (its worktree could not write `.git/worktrees` metadata; GitHub
  unreachable). The user relayed Codex's reply as a screenshot in Thai; recorded it in English in **T13** in
  `DISCUSSION.md`, marked as relayed by the user and recorded by Claude integration.
- Codex: `agree`. On `808dc6c` the same-clothing stranger (18°, 7.43 m, 1.2 s unseen) is rejected: 6.489 m from
  the last-seen place against 2.6 m allowed; both regression tests pass. The LiDAR range borrowing is a separate
  follow-up. Condition: `lookalike_after_loss` is 9/10 with the rule on and off, so there is no end-to-end evidence
  yet; the limitation stays stated.
- T13 status set to resolved (agree) with that condition.
- `HANDOFF.md`: T13 resolved; new open item 17, the follow-up "camera boxes get their own LiDAR range (box-height
  check or nearest LiDAR cluster)", not started, owner Claude; Codex asked to reconcile its uncommitted
  `HANDOFF.md` and `logs/codex.md` drafts. Lock released.
- No code merged; `python3 scripts/check.py` run on the hub before push.

### 2026-10-27 — dashboard — T13 card (18:45 Thai time)
- Dashboard v2 (page version 20): added the T13 card under the twin colour results. It shows the distance rule, the twin table with the rule off and on, and the borrowed-LiDAR-range limitation.
- `integration` merged the workspace into the hub (`b102cc7`) and replied in T13 (`58dcdc3`); T13 awaits Codex's re-review.

### 2026-10-27 — robot/research — T13 follow-up: camera boxes take their own LiDAR range (22:10 Thai time)
- The user asked to continue with HANDOFF item 17.
- `claude/robot/box-range`:
  - `adac5b5`: `box_range` takes a box's range from the LiDAR cluster at its bearing instead of the sector minimum; parameter `box_range_from_scan`.
  - `445b0e9`: prefers the covering cluster after the first version (nearest middle) failed `shade_crossing` 2/20 (found with a debug build that logged gate decisions); +4 tests.
- **Twin:**
  - `lookalike_after_loss` 20/20, against 17/20 with the old matching;
  - `shade_crossing` 20/20; side_by_side 10/10; identity 15/15;
  - solo 29/30, no contact.
- Write-up: `experiments/sim/2026-10-27_box_range.md` (+ `.json`). Merged into `claude/workspace`. `check.py` passes 134 tests.

### 2026-10-27 — integration — box range merged into `integration-hub`; T14 opened (22:17 Thai time)
- Lock claimed on `integration-hub` in `59d19f4` and pushed before the merge.
- Merged `claude/workspace` (`f6035f9`; `claude/robot/box-range` `adac5b5`, `445b0e9`; workspace merge `24e0d4e`)
  with `--no-ff`: merge `059c549`. Only conflict: `logs/claude.md`, both appended entries kept.
- `codex/workspace` (`86a2201`) not merged; its `HANDOFF.md` is identical to the hub's at `5d8e62e`, so no conflict.
- Checks on the merged hub:
  - `python3 scripts/check.py` passes, 134 tests.
  - Open-loop twin, hub before (`59d19f4`) vs after (`059c549`): 18 scenarios, seed 3, 150 steps. Bit-identical:
    plain `27db4268…`, realism `5143d0f7…`.
  - Recounted `experiments/sim/2026-10-27_box_range.json` (222 rows); it matches the write-up.
  - Diff review: no new publishers or wheel commands; no machine paths or secrets. Noted for Codex: default true,
    frames skipped when no cluster is near the box (also skips give-way for that box), long chained clusters,
    scan/camera timing, duplicated cluster split.
- Opened **T14** in `DISCUSSION.md` for Codex (points a–e). `HANDOFF.md`: item 17 implemented, awaiting Codex in T14;
  branches table updated. Lock released.

### 2026-10-28 — robot/research/dashboard — box range near-box rule; live monitor (00:15 Thai time)
- `claude/robot/box-range` `d23e7b2`: a box's range now counts only LiDAR returns within 5° of the box, so a person against a crop row gets the range at the box (integration T14 review); +1 test, 135 pass.
- **Twin:**
  - `lookalike_after_loss` 20/20;
  - `shade_crossing` 29/30;
  - identity 15/15;
  - solo 26/30;
  - solo seeds 3–7 with box ranges on vs off: 47/50 vs 48/50, no contact. The solo dip is variation.
- Write-up update: `experiments/sim/2026-10-27_box_range.md`. Merged into `claude/workspace`.
- **Dashboard v2 (page version 23):** new first tab "ติดตามสด" (live monitor).
  - Shows the experiment design as a diagram (variants, settings, scenario mini-maps, pass criteria), progress, a per-run grid, and a top-down replay of any run with a gap chart and a criteria checklist.
  - Datasets: `live_experiments`, `live_runs`, `live_tracks`, `past_tracks`, `live_scenarios`, built by a scratchpad generator from the twin run folders.
  - Claude pushed updates about every 4 minutes while the solo on/off run (100 runs) went.

### 2026-10-28 — integration — box range near-box rule merged into `integration-hub`; T14 updated (00:14 Thai time)
- Lock claimed on `integration-hub` in `c318090` and pushed before the merge.
- Merged `claude/workspace` (`00ad52e`; `claude/robot/box-range` `d23e7b2`, research `26f8eef`, workspace merge `50b54c0`)
  with `--no-ff`: merge `6cc9769`. Only conflict: `logs/claude.md`, both appended entries kept.
- Checks on the merged hub:
  - `python3 scripts/check.py` passes, 135 tests.
  - Open-loop twin, hub before (`c318090`) vs after (`6cc9769`): 18 scenarios, seed 3, 150 steps. Bit-identical:
    plain `27db4268…`, realism `5143d0f7…`.
  - The new crop-row test fails with the old `min(r for _, r in c)` restored on a scratch copy, and passes on `d23e7b2`.
  - Recounted `experiments/sim/2026-10-27_box_range.json` (`d23e7b2`, 195 rows); it matches the write-up. The
    `shade_crossing` seed-0 reruns are not in the JSON.
  - Diff review: no publishers or wheel commands; no machine paths or secrets; the filtered `min` cannot be empty.
- Added a Claude Code entry to **T14** (status open, Codex to review). New integration question for Claude: `side_step`
  fails 5 of 8 seeds with box ranges on but 0 of 5 off (seeds 3–7), with peak bearing 60–62° vs 41–44° and visible
  share 0.88–0.90, so "`box_range` unused" does not fit; more seeds or a trace are needed.
- `HANDOFF.md`: item 17 still awaiting Codex in T14, latest commit `d23e7b2` / merge `6cc9769`; branches table and test
  count updated. Lock released.

### 2026-10-28 — research — side_step on vs off; cause found (00:50 Thai time)
- Integration's T14 question: `side_step` failed 5/8 with box ranges on against 2/8 off.
- **Run:** seeds 8–27, on vs off, shown live on the dashboard. On 12/20, off 13/20. All seeds: 15/28 vs 18/28, Fisher p = 0.59.
- **Cause, from a debug build that logged gate decisions:** the fast sidestep at 0.7 m moves the bearing 21° in 0.3 s. The 5° bearing gate rejects the box even though its range is right. The LiDAR out-of-view tracking does not start, because the last accepted bearing was not near the edge.
- Not box ranges. Proposed next: a gate on lateral distance in metres.
- Write-up: `experiments/sim/2026-10-27_box_range.md`.

### 2026-10-28 — integration — side_step check merged into `integration-hub`; T14 answered (00:52 Thai time)
- Lock claimed on `integration-hub` in `00bf5ca` and pushed before the merge.
- Merged `claude/workspace` (`1fd081c`; research `543cc38`, workspace merge `6181627`) with `--no-ff`: merge `a601da7`.
  Only conflict: `logs/claude.md`, both appended entries kept. Changes only the write-up and the log.
- `python3 scripts/check.py` passes, 135 tests. Diff review: no code, topics or wheel commands; no machine paths or secrets.
- Verified: on seeds 0–7 in the JSON is 3/8, so 15/28 holds; Fisher p = 0.587 recomputed; gate cost 13.4 matches the
  formula (widen 1.1). Not verifiable from the repo: the 40 new runs (seeds 8–27) are not in the JSON, the debug log is
  not committed, and off seeds 0–2 (needed for 18/28) are in no data file. The write-up's "2 of 8 off" does not match
  integration's question (0 of 5 off); asked Claude to fix it (non-blocking).
- Added a Claude Code entry to **T14** with the answer; status stays open for Codex (a)–(e).
- `HANDOFF.md`: item 17 updated; new item 18 "gate on lateral distance (`side_step`)", not started, owner Claude.
  Lock released.

### 2026-10-28 — research — side_step count corrected (01:00 Thai time)
- Integration found a miscount in the side_step answer: off is 19/28, not 18/28. The off seeds 0–2 come from the T13 run, `808dc6c`, where they pass 1/3.
- Corrected values:
  - Fisher p = 0.41; still no difference;
  - integration's question was on 3/8 vs off 5/5, not "2 of 8".
- Added the 43 side_step runs to `experiments/sim/2026-10-27_box_range.json`.

### 2026-10-28 — tests/research — T14 objections addressed (06:20 Thai time)
- Codex objected in T14 (`c83633a`, review `codex/workspace` `6fd14e1`). Changes on `claude/robot/box-range`, merged into the workspace:
  1. **Regression test:** uses the production sector median (Codex's flat-return replay).
     - The old path borrows 0.8 m and the gate takes the look-alike; `box_range` gives 7.43 m and it is rejected.
  2. **Data:** the 43 side_step runs are in the JSON (since `b627a55`). The debug gate traces and the patch that makes the debug build are in `experiments/sim/box_range_debug/`.
     - Wording changed to "no effect detected" (p = 0.41, −14 points, not excluded).
     - The wrong claim that `box_range` is unused in the failing solo moves is withdrawn.
  3. **Limits kept in the write-up:** legs and a neighbour's leg, skipping removes give-way, the stale-scan fallback, physical alignment.
- `check.py`: 135 tests pass.

### 2026-10-28 — integration — T14 review changes merged; Codex's objections answered (06:20 Thai time)
- Fast-forwarded the hub worktree to `c83633a` (Codex's T14 objection). Lock claimed in `458690f` and pushed.
- Merged `claude/workspace` (`1f94cf4`) with `--no-ff`: merge `f0a79ab`. No conflicts. `codex/workspace` not merged.
- `python3 scripts/check.py` passes, 135 tests.
- Verified: side_step in the JSON is on 15/28, off 19/28 (43 rows added: 40 `d23e7b2` + 3 `808dc6c`); Fisher p = 0.412;
  `808dc6c` vs `d23e7b2` differ outside `box_range` only in comments; the regression test asserts the old path
  (median 0.8 m, accepted) before the new one (7.43 m, rejected); traces hold the cost-13.44 rejection; no paths or secrets.
- Ran Codex's `t14_gate_review.py` (from `codex/workspace`) with `-I` on a scratch copy of `f0a79ab`, output to a
  scratch path, not committed: exit 0, replay and limits reproduce. Its Fisher value and evidence inventory are stale
  by construction (hard-coded old totals; counts only `d23e7b2` rows).
- Added a Claude Code reply in **T14** answering requested changes (1)–(3); asked Codex to re-review. T14 stays open.
- `HANDOFF.md`: item 17 awaiting Codex's re-review; lock released.

### 2026-10-28 — robot/research — HANDOFF 18: gate on lateral distance; T13 rule-off correction (08:28 Thai time)
- `claude/robot/lateral-gate` (`efa24f1`): the bearing sigma is now max(5°, `lateral_sigma_m` 0.15 / range). Nothing changes beyond about 1.7 m, and 0 restores the old gate.
  - `TargetGate` tunables are now declared ROS parameters (`GATE_PARAMS`), and a test keeps them in step with the gate's defaults.
  - 138 tests pass.
- **Found:** before this, a `-p` to the gate was silently ignored, so T13's "rule off" twin runs had the rule on. Corrected in `experiments/sim/2026-10-27_hs_colour_twin.md`.
- **Twin (realism, one at a time, shown live on the dashboard):**
  - `side_step` 19/20 vs 5/20 with the old gate, interleaved, p = 1e-5;
  - identity 15/15;
  - solo 27/30;
  - `zigzag` 8/10 vs 6/10;
  - `shade_crossing` 9/10;
  - `shade_side_by_side` 10/10;
  - look-alike 20/20;
  - the T13 rule really off: 0/20 with 18 contacts, against 20/20 on.
- Handoff note and write-up: `experiments/sim/2026-10-28_lateral_gate.md` (+ `.json`). The run scripts are in `experiments/sim/scripts/`.

### 2026-10-28 — integration — lateral target gate merged; T15 opened; T13 correction pointer (08:45 Thai time)
- Fast-forwarded the hub worktree to `13f570b` (Codex's T14 agree). Lock claimed in `6a29b8f` and pushed.
- Merged `claude/workspace` (`24e121e`) with `--no-ff`: merge `8b946b7`. No conflicts. `codex/workspace` not merged.
- `python3 scripts/check.py` passes, 138 tests.
- Open-loop twin hash before (`6a29b8f`) vs after (`8b946b7`), 18 scenarios, seed 3: bit-identical, plain `27db4268…`,
  realism `5143d0f7…`; `sim/` unchanged.
- Verified: `lateral_sigma_m` 0 matches `TargetGate` from `13f570b` exactly (120,000 random `cost`/`accept` calls,
  0 mismatches in cost, accept or state). Recounted all 165 rows of `2026-10-28_lateral_gate.json`: every write-up
  number matches (side_step 19/20 vs 5/20, p 1.0e-5; zigzag 8/10 vs 6/10, p 0.63; rule off 0/20 with 18 contacts).
  `run_scenario` passes `--ros-param` as `-p` to every robot node; at `808dc6c` the gate declared none of the names,
  so the T13 correction is accurate (T13 table 18/20, all rule on).
- Found: at 0.7 m with no colour help the gate now accepts up to 0.445 m sideways (was 0.19 m); the grey person
  at 10° / 1 m costs 9.37 (thin margin); test track cost 10.67/1.83 vs trace 13.4/~3; minor write-up formatting;
  the hs_colour_twin line-123 claim lacks an inline pointer; the workspace log entry is stamped 08:35, after the
  merge time. All in T15.
- Opened **T15** for Codex (questions a–d); added a correction pointer to **T13** (stays resolved).
- `HANDOFF.md`: item 18 implemented, awaiting Codex in T15; item 16 correction note; lock released.

### 2026-10-28 — research — lateral gate write-up fixes after integration review (08:30 Thai time)
- Disclosed: at 0.7 m with no colour cost, the gate now accepts someone up to 0.445 m to the side (0.19 m before).
- Said that the 13.4 / "about 3" costs come from the debug trace; the unit test's synthetic track gives 10.67 / 1.83.
- Fixed the table, ticked steps 5–6, added a pointer at the old T13 "not a test of the rule" line, and corrected this log's earlier timestamp.

### 2026-10-28 — robot/research — T15 round 2: ambiguity-aware lateral gate (11:51 Thai time)
- Codex objected: with 0.15 a same-clothes stranger 0.44 m beside the target was published.
- **Added:**
  - Codex's constructor test;
  - the effective gate settings logged as `[GATE]`;
  - twin attribution of each `/synced_target` to a person, and the `published_other` score;
  - scenario `close_pair_same`.
- **Sweep 1 (130 runs):** a plain floor loses the pair (0.10: 3/10 with 201 wrong publications; 0.15: 2/10 with 648).
- **Round 2b:** the floor applies only when no second person is near the predicted target (1 s window). 130 runs: `side_step` 20/20 vs 7/20 and the pair 10/10, but 50 distractor publications, all from a lock-on bug.
- **Fixed in `5aa4f65`.** Confirmation (50 runs): `side_step` 10/10 vs 5/10, the pair 15/15 for both, 0 distractor publications.
- 142 tests pass. Merged into `claude/workspace`.

### 2026-10-28 — integration — T15 round 2 merged, Codex's objection answered (11:55 Thai time)
- Claimed the lock (`f3555f8`). Merged `claude/workspace` `3cd0870` into `integration-hub` with `--no-ff` (`c3ce609`); no conflicts. `codex/workspace` not merged.
- `python3 scripts/check.py` passes (142 tests). Open-loop twin hash on the 18 earlier scenarios (plain and realism) is bit-identical before and after.
- Recounted every Round 2 table from the three JSON files (130 / 130 / 50 runs): all match. Every row's `[GATE]` line matches its parameters. Distractor-only counts come from `state.jsonl` and could not be recounted; `published_other` includes false-positive boxes.
- Review finding (offline): a same-clothes stranger who arrives beside the target, with their box first in the first shared frame, is accepted and pulls the track. A pair that is together from the start is safe (39/39 rejected). Minor: the runners' `\b` grep would accept `=0` for `0.15`.
- T15: answered Codex's requests (1)–(3), stated the decision (`amb` default) and the limits, and asked Codex to re-review. T15 stays open.
- `HANDOFF.md`: item 18 awaiting Codex re-review; noted unmerged `claude/dashboard/source` (`be8729c`, `tools/dashboard/`) for the Codex validator. Lock released.

## 2026-10-28 11:56 — Integration of T15 round 2 reported
- Integration merged T15 round 2 into `integration-hub` (`c3ce609`, tip `912b7f7`). `check.py`: 142 tests pass; twin bit-identical. T15 waits for Codex's re-review.
- Integration's new finding: a stranger who walks up beside the target mid-run is taken if their box comes first in the first shared frame. Proposed as the next item; waiting for the user's go-ahead (quota).

## 2026-10-28 12:59 — T15 tidy-up (integration findings 3 and 4)
- Runner scripts: the `[GATE]` check matched `lateral_sigma_m=0` against a log saying 0.15 (`\b` stops at the dot). It now needs the exact value followed by a space or the line end. Checked on real round-2c logs.
- `2026-10-28_lateral_gate.md`: Round 2 marked done (re-review pending), Next lists ticked, reach recomputed with `TargetGate.cost` at 0.7 m: 0.442 m (was 0.445) with the new gate, 0.183 m (was 0.19) with the old one.
- `check.py`: 142 tests pass.

## 2026-10-28 14:10 — Walk-up stranger (integration finding 1), branch `claude/robot/walk-up`
- `cd6eead`: the node checks the scan before each box; someone besides the box near the predicted target keeps the plain gate. Node-level tests through `try_sync_from_yolo`; twin scenario `walk_up_same`; runner `run_walk_up.sh`.
- Round 1 (radius 1.0): `walk_up_same` scan 10/10, noscan 2/10 (573 wrong publications), old 10/10. `side_step` scan 7/10 vs noscan 10/10: a post near the step.
- `1be3357`: `crowd_radius_m` 0.5. Round 2: `side_step` 13/20 vs 20/20, `walk_up_same` 10/10, `close_pair_same` 5/5.
- `0d74732`: only boxes near the prediction are checked (a false box made the target's own returns a crowd). Round 3 running.

## 2026-10-28 14:33 — Reviewed Codex's dashboard PRs 5 and 6
- PR 5 (live validator): PR's `gen_live.py` on the real registry (14 experiments, 1,070 runs, one live) → validator PASS. OK to merge. My side: write `live: false` in the registry, sync `tools/dashboard/live/registry.json`, and watch `past_tracks` (5.3 of 8 MB).
- PR 6 (CI generator): fields match `drawCI()`. Needs #5's head merged in (only `logs/codex.md` conflicts; 152 tests pass merged). My side: show `fetched_utc` on the CI tab and update the dataset description before publishing.

## 2026-10-28 14:43 — Walk-up rounds 3 and 4
- Round 3 (`0d74732`): `side_step` scan 10/20 vs noscan 18/20; `walk_up_same` 10/10; `close_pair_same` 5/5.
- Offline check (`experiments/sim/walk_up_debug/spread_check.py`): with realism the box is 0.15 s behind the scan, so the target's own returns looked like a second person during the step.
- `1466559`: the returns within 0.5 m of the prediction must span ≥ 0.55 m. Round 4 running (same 55-run set).

## 2026-10-28 15:15 — Walk-up round 4 and write-up
- Round 4 (`1466559`, spread rule): `walk_up_same` 10/10, `side_step` 18/20 vs 19/20 without the check, `close_pair_same` 5/5, no contact. Meets the rule set before the run, so `crowd_from_scan` stays on.
- Write-up `experiments/sim/2026-10-28_walk_up.md`, data `2026-10-28_walk_up.json` (220 runs, four rounds). Fixed the runner's broken usage line.
- Reviewed Codex's PR 7 (unit_tests generator): 154/154 in a clean worktree; OK to merge.

### 2026-10-28 — dashboard — dashboard source into the repository (11:04 Thai time)
- The user asked for the first parallel-work step: move the dashboard out of Claude's session scratchpad.
- Branch `claude/dashboard/source` (`76ef97e`) adds `tools/dashboard/`:
  - `index.html` (store v24);
  - `datasets.json` (snapshot of the dataset records);
  - `live/gen_live.py` (`--runs-root`, `--out`);
  - `live/registry.json`;
  - README with the publish procedure (Claude only) and the schema of the live JSON.
- `.gitignore`: `dashboard/` anchored to the root (`/dashboard/`), since it was also hiding `tools/dashboard/`.
- `gen_live.py` checked against the scratchpad generator:
  - `past_tracks` identical (25,127 rows);
  - the other differences are only runs that finished in between, and `close_pair_same`, which is not on this branch.
- 138 tests pass. Not merged into the hub yet.

### 2026-10-28 — integration — walk-up and dashboard source merged (15:25 Thai time)
- Model: Claude Opus 5.5 (`integration` subagent). Worktree `wt_hub`.
- Claimed the lock (`f518483`). Merged into `integration-hub` with `--no-ff`: `claude/workspace` `1b61abe` (`5ace9be`; `logs/claude.md` conflict, both sides kept), `claude/robot/walk-up` `bdf15ff` (`6becee0`; clean), `claude/dashboard/source` `f4f0c27` (`8d35db4`; `logs/claude.md` and `logs/codex.md` conflicts, both sides kept, no duplicate headings). Codex's branches were not touched.
- `python3 scripts/check.py` passes (166 tests: 142 + 8 walk-up + 16 dashboard).
- Open-loop twin hash (seed 3, plain and realism) on the 19 earlier scenarios is bit-identical before and after; the 20-scenario hash changes only by the added `walk_up_same`. Only `sync_fusion_node.py` and `sim/twin/scenarios.py` change outside docs, tests and `tools/dashboard/`; no hardware command or bridge change.
- Walk-up review: recounted all four rounds from `2026-10-28_walk_up.json` (220 rows); every table number, the medians and the wrong-publication counts match the write-up. `scan_crowded` cost measured offline: about 0.5 ms per box at 720 returns, 2 ms at 1440, 10 ms at 3600 (the sort is redone per box). Confirmed offline that a stale scan (0.5 s) lets the stranger through (documented fallback; no unit test). Found that `test_a_crop_row_beside_the_target_does_not_count_as_a_person` passes with the 1.5 m width rule disabled (row outside the 0.5 m radius); with the row at 0.45 m the rule is exercised. Not blocking; owner Claude (workspace).
- Dashboard review: the CI NumPy step (`a682ad9`) is identical to Codex's PR 3 (`272ff22`, same blobs), so the hub has one copy and PR 3 becomes a no-op. `gen_ci.py` uses no credentials. No new absolute paths or secrets in the added files.
- `DISCUSSION.md` T15: walk-up note for Codex with results and limits; asked Codex to re-review T15 including it. T15 stays open.
- `HANDOFF.md`: hub, `claude/workspace` and `claude/dashboard/source` rows; item 18; the dashboard source now lives on the hub and the next publish is generated from a hub commit. Lock released. The dashboard artifact was not published. No twin sweep was run.

## 2026-10-28 15:25 — Dashboard published from integration-hub 51e4e15
- Generated from the hub checkout: `gen_live.py` (14 experiments, 1,235 runs, all done) and `validate_dashboard_live.py` PASS; `gen_ci.py --fetch` (60 runs, fetched 15:23 Thai); `generate_dashboard_unit_tests.py` 166/166 on a clean tree.
- Uploaded 7 assets, one atomic batch: datasets ci_runs v2, unit_tests v2, live_experiments v44, live_runs v44, live_tracks v42, past_tracks v6, live_scenarios v3, and page `files/index.html` v25 (= hub `tools/dashboard/index.html`, with the snapshot-time lines). Deleted the 7 old blobs.
- `tools/dashboard/datasets.json` refreshed from the store.

## 2026-10-29 14:46 — Dashboard live_tracks fix; walk-up test gaps from integration
- The page showed `live_tracks` as a load failure: the published file was `[]` (no live experiment). The newest experiment (`walk_up_r4`) now keeps `live: true`; README says why. Regenerated (validator PASS; experiments, runs and scenarios unchanged), uploaded live_tracks (v43) and past_tracks (v7), deleted the two old blobs, refreshed `tools/dashboard/datasets.json`.
- `tests/test_walk_up.py`: the crop row is now 0.45 m beside the target, inside the radius, and the test shows it would count without the width rule; new test for the stale-scan fallback. 167 tests pass.

## 2026-10-29 20:58 — T15 change request from Codex addressed
- `try_sync_from_yolo`: with `crowd_from_scan` on and no fresh scan (stale, missing, dated ahead), the gate keeps the plain bearing gate (`note_crowded`); the stale scan is not read. Tests through the node path: stale/missing/future (stranger first rejected, target accepted; fail on the old code), `crowd_from_scan:=false` keeps round 2, recovery with a fresh solitary scan. 169 tests pass.
- `2026-10-28_walk_up.json`: every row has `published_by` and `published_unmatched` from its `state.jsonl` (checked against `published`/`published_other` for all 220). Write-up wording corrected: `?` is not in `published_other`; stranger published 0 times in all 40 runs with the check, 571 without (round 1).
- Smoke only (2 runs, image with the fix): `walk_up_same` s0 pass, `side_step` s8 pass. Not a comparison.

## 2026-10-29 21:03 — integration — claude/workspace 210f422 merged into integration-hub (T15 fix, dashboard live); T15/T16 replies
- Lock claimed (`a8fd11c`), released in the closing handoff commit. Merge `--no-ff` of `claude/workspace` `210f422` (contains `f741ea6` and hub `c265d9a`) into `integration-hub`: merge `51f5dff`.
- Review: call site in `sync_fusion_node.py` (no fresh scan → `gate.note_crowded`, stale scan not read; `ty` and `scan_time` are both arrival times on the node clock, so "dated ahead" needs a clock jump); `tests/test_walk_up.py` re-run on `1466559`: exactly the 3 no-fresh-scan sub-cases fail. Recounted `published_by`/`published_unmatched` from all 220 `state.jsonl` files in the scratchpad walk-up runs: 220/220 match, and the JSON is self-consistent with `published`/`published_other`. Stranger counts in the write-up confirmed (0 with the check; 571 + 2 false boxes = 573 without; round 4 numbers as stated).
- Checks on `51f5dff`: `scripts/check.py` 169 tests OK; Virtual Office `node --test` 9/9 (Node 22.22.0). Twin hash (plain and realism, seed 3, all scenarios) identical to `c265d9a`; no `sim/` change.
- T16: re-checked the reply against the code; reproduced `readMessage` accepting a `text/plain` cross-origin body with a foreign `Host`. One wording fix: the 500-character cut is in `server.mjs` (`stderr.slice(-500)`), which is all `classifyModelError` sees.
- `DISCUSSION.md`: T15 reply (open, awaiting Codex re-review) and T16 cross-review (open, change requested, owner Codex). `HANDOFF.md`: lock, hub and `claude/workspace` rows, item 18, Virtual Office section, next dashboard publish must come from a hub commit containing `f741ea6` (`51f5dff` or later).
- Not done: no twin sweep, no dashboard publish, nothing to `main`, Codex branches untouched.

## 2026-10-29 21:52 — integration — T16 re-review of PR #14: agree
- Lock claimed (`ba2905f`), released in the closing commit. No merge; no PR merged; Codex branches untouched; nothing to `main`.
- Checked in clean detached worktrees: PR #14 `a6a10fb` (= `1664217` + hub `c07ca78`) Node 12/12, `scripts/check.py` 169 OK; PR #13 `d6ed026` (on top of `a6a10fb`) Node 20/20, `scripts/check.py` 169 OK; both trees clean.
- Re-read the guard in `server.mjs` and re-ran the earlier repro. `readMessage` returns 415. `handleRequest` returns 403 for the foreign Host and 415 for a local `text/plain` POST. `changesMatchMode` is tested for all four cases. PR #13: the guard covers the office routes; the `officeLogName` regex is UUID-shaped plus `-(krit|mew|boss).txt`; seat checks strip the API-key variables and run in the user's own checkout (README wording note).
- `DISCUSSION.md` T16: reply "agree", status open until Codex integrates PR #14 (#13). `HANDOFF.md`: Virtual Office line updated, lock released.

## 2026-10-29 22:10 — Dashboard refresh from hub af95e3e; past_tracks budget
- From the hub checkout at `af95e3e`: `gen_ci.py --fetch` (60 runs, fetched 22:08 Thai, last 15: 8 success, 7 running, 0 failure) and `generate_dashboard_unit_tests.py` (169/169, clean tree). Live datasets regenerated and validated: identical to the published ones, so not re-uploaded; page unchanged. Uploaded ci_runs (v3) and unit_tests (v3), deleted the two old blobs.
- `gen_live.py`: `fit_past_tracks` keeps `past_tracks` under 6.5 MB by thinning the oldest finished experiments from 1 Hz to 0.5 Hz, one at a time. Today's file is 5.6 MB, so the output is unchanged (byte-identical, validator PASS). New `tests/test_dashboard_past_tracks.py` (3). 172 tests pass.

## 2026-10-29 22:11 — Robot-day prep for the crowd check (E4b)
- `sync_fusion_node.py`: one `[CROWD] on t=… reason=scan|no-fresh-scan|gate` / `[CROWD] off t=…` line per change of the forced plain gate. Logging only; the gate's decisions are unchanged. Test `test_crowd_changes_are_logged_once_each`. 173 tests pass.
- `docs/robot_day_protocol.md`: new E4b (four 30 s recordings: target alone walking and side-stepping, a pair at 0.4 m, a person joining from behind), what to read from the `[CROWD]` lines and what to change if legs read as two people.

## 2026-10-29 22:15 — integration — claude/workspace 39444d9 merged; T17 opened
- Lock claimed in `253b164` and pushed. Merged `claude/workspace` `39444d9` (`94d084b` past_tracks budget, `39444d9` `[CROWD]` log + E4b) with `--no-ff`: merge `3b13465`, no conflicts. No Codex branch merged; `main` untouched.
- Checks on `3b13465`: `scripts/check.py` 173 tests OK; Virtual Office `node --test` 20/20; open-loop twin hash (seed 3, 20 scenarios, 150 steps) identical to `af95e3e` (plain `ccfc03e4…`, realism `c2a5ddd9…`).
- Review: `crowded` reads `gate.locked` / `gate.ambiguous_until` only; logged once per change, not per box; changes made inside `accept` show at the next box as `reason=gate`. `fit_past_tracks` keeps `t` increasing per run and registry order. Change requested: E4b says "stop it with the e-stop", but the project has no physical E-stop. Opened **T17** (owner Claude workspace).
- `HANDOFF.md`: hub and `claude/workspace` rows, dashboard row (ci_runs/unit_tests republished from `af95e3e`, CI 22:08 Thai, 169/169), item 18 points to E4b, new item 19 (T17); lock released.

## 2026-10-29 22:15 — T17: E4b safety line reworded
- `docs/robot_day_protocol.md` E4b no longer mentions an e-stop (the project has none, HANDOFF *Plan*). It now says: isolated field with spotters; people step out of the path and the operator stops the bringup; the bridge zeroes the wheels on shutdown and after 1 s without `/cmd_vel` (checked in `zlac_joystick_bridge.py`), which is software only.

## 2026-10-29 22:20 — integration: `claude/workspace` 783c1a6 (T17 E4b safety line)
- Lock `3b12ae8`; merged `783c1a6` into `integration-hub` with `--no-ff` at `f6bdc90`. `scripts/check.py` 173 tests OK.
- Review against `zlac_joystick_bridge.py` and `follow_bringup.launch.py`: no e-stop claim, isolated field and spotters, operator stops the bringup, shutdown writes zero directly then `0x200E=7` (software only): correct. Change requested: "within 1 s of the last `/cmd_vel`" is exact only in `legacy`; in the default `mps` mode the target goes to zero after 1 s and the output ramps at 1.0 m/s² (about 1.6 s total at 0.5 m/s, 2.5 s at 1.4 m/s). T17 stays open (owner Claude workspace).
- E-stop grep over `docs/` and other `.md` files: only `docs/PLAN.md` lines 13/16/18, which state the no-E-stop decision. No other contradiction.
- `HANDOFF.md`: hub and `claude/workspace` rows, item 18 note, item 19 (T17); lock released.

## 2026-10-29 22:17 — T17: E4b stop timing corrected
- E4b now says the bridge writes zero at once on shutdown, and without `/cmd_vel` starts ramping to zero 1 s after the last command at 1 m/s² (about 1.5 s to stop at 0.5 m/s, 2.5 s at 1.4 m/s in `mps` mode; `legacy` zeroes at once). Checked in `zlac_joystick_bridge.py` `update_loop`.

## 2026-10-29 22:18 — integration: `claude/workspace` ab22dd7 (T17 resolved)
- Lock `317005c`; merged `ab22dd7` into `integration-hub` with `--no-ff` at `9184db7`. `scripts/check.py` 173 tests OK.
- E4b timing checked against `zlac_joystick_bridge.py` (`destroy_node` zero at once; `update_loop` target zero after `TIMEOUT` 1.0 s, ramp 1 m/s²: about 1.5 s at 0.5 m/s, 2.5 s at 1.4 m/s; legacy no ramp): correct. T17 closed (resolved). The previous entry's 22:20 stamp was really about 22:16 Thai time.
- `HANDOFF.md`: item 19 resolved, item 18 E4b ready for the robot day, hub and `claude/workspace` rows; lock released.

## 2026-10-29 23:04 — Dashboard: every tab dated, current code shown everywhere
- User asked that no tab lag behind. New dataset `current_runs` (`tools/dashboard/live/gen_current.py`, from the running whole-twin baseline on hub `5c72c4d`): a "ทุกฉาก ด้วยโค้ดปัจจุบัน" card on the ready, solo, identity and colour tabs, a first KPI and a takeaway line built from it. Older cards say their date (25 Oct solo, Arena 3 24 Oct, colour 26–27 Oct); replay, filter and arena tabs carry a history banner. Ready tab open items gain E4b.
- Published page v26 and `current_runs` v1 (45 of 100 runs so far, 43 pass); it will be refreshed when the baseline ends. Live tab, unit tests (173/173) and CI were refreshed earlier from hub `5c72c4d`.

## 2026-10-29 23:09 — Dashboard: no pill shapes
- The clip selector on the colour tab wraps to three lines inside a 999px-radius outline, so it rendered as a large oval that clipped the selected button. All controls now use a 6px radius (segments, chips, tabs, badges, status pills); the two clip selectors (`tb-wrap`) drop the shared outline and border each button. Legend dots stay round. Published page v27.

## 2026-10-29 23:22 — Dashboard tabs named after the features in development
- User found the tab names confusing. New names and order: ภาพรวมความพร้อม, ตามคน (ตัวควบคุม), เลือกเป้า (target gate), แยกคนด้วยสีเสื้อ, กรองจุดนิ่ง (ทดลอง), การทดลองที่กำลังรัน, เทสต์และ CI, then history: เส้นทางโค้ดรุ่นก่อน, Arena (ปิดแล้ว). Tab ids unchanged. Published page v28.

## 2026-10-29 23:36 — Whole-twin baseline on hub 5c72c4d: 98/100
- Every scenario, realism, seeds 0–4: 98/100 pass, no contact. Only `zigzag` fails: seed 0 (visible 0.889, just under 0.9) and seed 1 (visible 0.472).
- Published: `current_runs` v2 (all 100 runs), live datasets with the finished baseline.

## 2026-10-29 23:45 — zigzag cause found; LiDAR assist ported (branch `claude/robot/lidar-assist2`)
- Debug build on hub code, `zigzag` realism seeds 0–7: s2 failed (visible 0.47). Gate log: the robot was turning right at 0.5–0.7 rad/s, so the target's bearing in the image swept from −13° to +28° in 0.4 s from the robot's own rotation. The gate's prediction does not include the robot's turn, so every box cost 11–36 and was rejected. LiDAR edge tracking did not start either (last bearing −13°, prediction −17°, both inside the 27° edge). The robot kept turning away and stopped.
- The LiDAR assist draft (`2eb6e9d`) addresses this: each scan moves the track to the target's own cluster, measured in the robot's current frame. Cherry-picked onto `claude/workspace` `e22307e`; 176 tests pass. Whole-twin run with the assist on to follow.

## 2026-10-30 01:13 — blind_corner round 1; obstacle stop fixed (`claude/robot/obstacle-stop` `c0be756`)
- Round 1 on `4f573e8` (realism, s0–4, interleaved): stop off — 1 contact (s2, 0.24 m); stop on — 1 contact (s0, 0.34 m). Neither setting passes on following: the bystander's returns shorten the target range at the corner (give-way), the robot backs off, and the target walks beyond the 3 m reacquire limit.
- Cause of the stop-on contact: one false box set a 0.5 m/s command, then target messages stopped; the command ran until the stale stop and the bridge ramp. The target exclusion (0.45 m) also covered the bystander.
- Fix: each scan re-checks the last moving command; exclusion 0.30 m. 184 tests pass. Pushed. Round 2 and the LiDAR-assist full run (`3cae4f3`, s0–4) are running.

## 2026-10-30 01:19 — blind_corner round 2 on `c0be756` (realism, s0–4, interleaved off/on)
- Stop off: contact 2/5 (s0 0.376 m, s2 0.384 m); min range 0.376–0.468 m.
- Stop on: contact 0/5; min range 0.561–0.640 m.
- Both lose the target at the corner (visible share about 0.45): the bystander stands 0.45 m from the target's path, so a 47 cm robot cannot follow through without contact. Passing needs avoidance (steer around), not a stop. Results in scratch `bc2/`. Assist full run started.
## 2026-10-29 23:27 — Obstacle stop (branch `claude/robot/obstacle-stop`), not yet run in the twin
- `follow_stop_node.py`: subscribes `/scan`; any return in the corridor ahead (half width 0.35 m), or behind when reversing, other than returns within 0.45 m of the target, caps the speed so the robot stops 0.45 m short (`obstacle_speed_cap`, same deceleration and latency as the braking cap). No fresh scan (> 0.3 s) means no motion. Applied to the normal command and the 1 s HOLD. Parameters `obstacle_stop` (true), `obstacle_half_width_m`, `obstacle_stop_m`, `obstacle_target_exclude_m`, `scan_topic`, `lidar_angle_offset_deg`, `scan_max_age_s`; `[OBST] on/off` log lines.
- `tests/test_obstacle_stop.py` (8); sensor_msgs stubs added to two older tests. 181 tests pass.
- Twin scenario `blind_bystander` (set `obstacle`): a person the camera never sees stands on the path; the target walks round them. To run: off vs on, plus every scenario with the stop on against the baseline.

## 2026-10-29 23:41 — Obstacle stop, first twin result: the stop as written hurts following
- `blind_bystander` realism seeds 0–4, interleaved: stop off 5/5 pass, no contact (closest to the bystander 0.47–0.54 m centre to centre; contact is < 0.40). Stop on 0/5 pass, no contact: the robot stops behind the bystander (closest 0.56–0.64 m) and the target walks away (final gap 3.9–4.4 m).
- So the scenario does not produce a contact without the stop, and the straight 0.35 m corridor stops the robot for an obstacle it would have passed. Next: a corridor along the commanded arc, its width from the real robot's width, and a scenario where the robot would really hit the bystander. Not merged.

## 2026-10-29 23:44 — Obstacle stop v2: robot size from the thesis slides, corridor along the turn
- The user shared the thesis progress slides (Canva): robot 47 cm wide, 52 cm long, 87 cm tall; wheels Ø13 cm front, Ø10 cm rear (the bridge assumes `wheel_radius_m` 0.085, Ø17 cm — to confirm which wheels drive). The slides' scope lists slowing/stopping for obstacles with LiDAR as an evaluation item.
- `obstacle_half_width_m` 0.30 (half of 47 cm + 6.5 cm). The corridor now bends with the commanded turn (curvature = angular_z / linear_x), so a turn that passes an obstacle does not stop the robot.
- Scenario `blind_bystander` (no contact without the stop) replaced by `blind_corner`: `turn_90` with an undetected person at the inside of the corner, where the baseline robot's corner-cutting path passes. 182 tests pass.

## 2026-10-30 01:39 — obstacle avoid started (`claude/robot/avoid` `88af833`)
- User asked to continue with avoidance. New branch merges LiDAR assist (`lidar-assist2`) and the obstacle stop (`c0be756`).
- follow_stop_node: when the path is blocked within 1.6 m, score swerves (k for 0.8 m, -k for 0.8 m, then straight) by free path, minus a turning cost; a swerve that turns more than 0.8 rad from the target is not taken. `obstacle_avoid:=false` keeps the stop alone. 192 tests pass.
- Twin: `blind_corner` avoid off/on s0–4 queued after the LiDAR-assist full run.

## 2026-10-30 02:18 — LiDAR assist full run; assist fix; avoid round 2
- Assist full run (`3cae4f3`, 20 scenarios × s0–4, realism): 91/100 vs baseline 98/100. zigzag fixed (both baseline failures pass, 5/5). crossing s1–4 failed with contacts and shade_crossing s0–4 failed: a passer-by covering the target from the LiDAR was taken as the target's cluster.
- Fix `9cb32f2` (lidar-assist2): a cluster 0.2 m nearer than the predicted range, or farther from the last fix than 1.5 m/s allows, is not taken. Test added; 177 pass. Merged into `claude/robot/avoid`.
- Avoid round 1 (blind_corner): no contacts, but swerve/straighten alternated each frame and the corner still lost the target (needs going wide, beyond a reactive swerve).
- `f1e1511`: swerve hysteresis; new scenario `pass_by` (hidden worker 0.42 m off a straight line). Running pass_by off/on s0–4 and blind_corner with avoid s0–4.

## 2026-10-30 02:31 — avoid rounds 2–3 and redesign (`claude/robot/avoid` `dcd58e0`)
- Round 2 (`f1e1511`): pass_by avoid on 4/5, off 0/5 (stop, target lost), no contacts. blind_corner avoid on 0/5, no contacts (min 0.57 m).
- `cb9af55`: start from a near stop (pass_by s4 stood 5 s beside the worker: the ramp asked for 0.05 m/s with a turn into the worker). Round 3: pass_by 5/10, no contacts; swerve arcs fought the sector steering.
- `dcd58e0`: redesign. Aim at a point beside the target (smallest clear sideways shift, side kept, within 0.5 rad), steer there by bearing; hold 0.5 s after clear. 194 tests pass. Round 4 (pass_by s0–9, blind_corner s0–4) running.

## 2026-10-30 03:48 — avoid rounds 4–5, full run, crossing fix (`claude/robot/avoid` `b618b40`)
- Round 4 (`dcd58e0`, aim beside the target): pass_by 8/10, no contacts. s3/s8 stopped for good level with the worker (inside the 0.30 m corridor, outside the 0.235 m body).
- `f6373c4`: returns within the body's length count only inside the body's half width. Round 5: pass_by 10/10 (min 0.54 m, gap ~0.52 m, visible 1.0); blind_corner 0/5 following, no contacts.
- Full run on `f6373c4` (22 scenarios × s0–4): 99/110, no contacts. Baseline set 94/100 (baseline 98): zigzag s0 now passes; crossing s2–4, shade_crossing s1–2 lose the target (avoid aimed beside a walker crossing; target went to the image edge; LiDAR edge tracking followed the walker); zigzag s1 visible 0.85.
- `b618b40`: avoid only after the path is blocked 1 s (`avoid_delay_s`). Targeted run (crossing, shade_crossing, pass_by, zigzag × s0–4) running.

## 2026-10-30 05:25 — integration — LiDAR stop, avoid and assist merged into integration-hub (T18)
- Read `AGENTS.md`, `agents/roles/integration.md`, `HANDOFF.md` and `DISCUSSION.md`; fetched `integration-hub` (now `5dc8ec4`, Codex's review request for draft PRs #9–#12, lock `ready`) and `claude/workspace` `e22307e`.
- Claimed the lock at `8aabceb` (`handoff: claim LiDAR stop/avoid/assist integration`), pushed.
- Reviewed `claude/robot/avoid` `c2899c7` against `origin/integration-hub`. One should-fix before robot day: `recheck_last_cmd` republishes capped commands with no age limit, so the bridge's 1 s timeout is refreshed and the last message keeps `angular.z` (scratch probe: 20 extra `/cmd_vel`, ending `(0.00, 0.60)`). Not blocking the hub merge (it only lowers speed). Minor notes: legacy-mode units, avoid minimum speed, two separate `lidar_angle_offset_deg`, `clr=` staleness. Robot code not changed.
- Merged `claude/robot/avoid` into `claude/workspace` with `--no-ff` at `c2c9aa2`; `scripts/check.py` 197 tests OK; pushed.
- Merged `claude/workspace` into `integration-hub` with `--no-ff` at `ad11ba9`; no conflicts; `scripts/check.py` 197 tests OK; diff scan: no machine path, secret or recording. Twin/Gazebo not re-run (no Docker run this session). Pushed.
- `HANDOFF.md`: lock released, branch rows, open item 20 (T18), robot-day note and T18 checks (`[OBST]`, `[AVOID]`, `clr=`, `[GATE]` assist values, LiDAR offset). `DISCUSSION.md`: opened T18 asking Codex to cross-review.
- Follow-ups: Claude (`claude/workspace`) fixes T18 item 1 with a test; Codex cross-reviews T18; Codex's request to review draft PRs #9–#12 is still open for Claude.

## 2026-10-30 05:27 — T18 item 1: per-scan re-check bounded (`claude/workspace`)
- Integration's review: `recheck_last_cmd` resent lowered commands with no age limit (each resend restarts the bridge's 1 s timeout) and could end on a turn in place.
- Fix: re-check only within `recheck_max_s` (1.0 s, the bridge timeout) of the command it lowers; a resend capped to 0 also zeroes the turn. Test added (fails without the fix). 198 tests pass. Twin smoke run follows.

## 2026-10-30 05:38 — integration: merged T18 item 1 fix (`integration-hub`)
- Lock claimed at `1dca3fa`. Reviewed `claude/workspace` `d46914d` (re-check bounded by `recheck_max_s` 1.0 s; a stop zeroes the turn): addresses T18 item 1; residual note that a lowered resend just inside the window can run up to ~2 s total (below the cap).
- Merged with `--no-ff` at `ef6054c`; no conflicts; `scripts/check.py` 198 tests OK; diff scan clean. Twin smoke from the author (pass_by, crossing, turn_90, stop_and_go 2/2 each; blind_corner 0/2 following; 0 contacts in 10 runs); not re-run here.
- `DISCUSSION.md` T18: item 1 fixed at `ef6054c`, Codex cross-review still open. `HANDOFF.md`: hub and workspace rows, item 20, robot-day note (`recheck_max_s`), lock released. Pushed.

## 2026-10-30 06:52 — T18 Codex change request: stopped turn and /scan QoS (`claude/workspace`)
- Codex (T18, 06:22): (1) a zero speed cap still sent the requested turn, also with no fresh scan; (2) the new `/scan` subscription asked for reliable QoS, which a best-effort LiDAR driver never connects to.
- Fix: a command that does not move forward or back may turn in place only with a fresh scan and nothing but the target within `spin_clear_radius_m` (0.40 m: corners sweep 0.35 m); otherwise both components are 0 (fused, avoid and `[HOLD]` paths). `/scan` uses `qos_profile_sensor_data`.
- Tests: `StoppedTurnTest` (no scan, post inside the spin circle, post outside it, QoS) — 3 fail and 1 errors without the fix. Two older tests given a fresh scan / qos stub. 202 tests pass. Full twin run follows.

## 2026-10-30 08:00 — full run after the T18 fixes; dashboard source for the LiDAR-map tab
- Full twin run on `a4ce8a5`: 104/110, 0 contacts; baseline set 99/100 (`zigzag` s1). `zigzag` s0–9 re-run on the same image: 10/10, so s1 was run-to-run variation. Added to the write-up.
- Dashboard source: tab renamed "แผนที่ LiDAR (จุดนิ่ง · หยุด/หลบ)"; stop/avoid/assist card and an obstacle current-code table first, static filter (experimental) below; `gen_current.py` group `obstacle`; overview takeaway lists failing scenarios.

## 2026-10-30 08:03 — integration: merged T18 answer to Codex's change request (`integration-hub`)
- Lock claimed at `c99e295` (pushed first). Reviewed `claude/workspace` `545abfb` (fix `a4ce8a5`) against Codex's two T18 findings: both addressed — `linear.x` 0 keeps its turn only with a fresh scan and a clear `spin_clear_radius_m` (0.40 m) circle on the fused, avoid and `[HOLD]` paths; `/scan` uses `qos_profile_sensor_data`.
- Residual found (scratch probe on `1fe91f2`, test stubs): a near spin (`(0.03, −0.8)`, `(0.06, −0.8)`, `(−0.03, −0.8)`) is not checked against the spin circle and passes with a post 0.31 m beside the rear quarter; should fix before robot day (author's workspace). Notes: 0.40 m may refuse turns in narrow rows; LiDAR self-returns would refuse every turn.
- Merged with `--no-ff` at `1fe91f2`; no conflicts; `scripts/check.py` 202 tests OK; diff scan clean (no path, secret, recording, wheel/serial command or new external URL). Twin numbers from the author (104/110, 0 contacts; `zigzag` s0–9 10/10); not re-run here.
- `DISCUSSION.md` T18: answer with evidence and the near-spin residual; Codex asked to re-review (agree / change requested / question); thread open. `HANDOFF.md`: hub and workspace rows, item 20, robot-day note (`spin_clear_radius_m`) and checks (`/scan` best effort, spin circle), lock released. Pushed.
