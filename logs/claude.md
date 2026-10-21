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
