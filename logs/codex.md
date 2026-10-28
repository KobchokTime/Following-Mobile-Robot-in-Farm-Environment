# Codex — action log

Append-only. Only Codex edits this file. The format and rules are in `AGENTS.md` → *Logging*.
Earlier history: `history-2026-10-16.md`.

---

### 2026-10-20 — integration — Sync workspace and review T1
- Merged `origin/integration-hub` into `codex/workspace` with merge commit `b637929` and pushed it to `origin/codex/workspace`.
- On `integration-hub`, reviewed T1: agreed with the branch layout, role scopes and per-agent logs; left the thread open because this session cannot inspect or set Codex's exact model configuration. The runtime identifies only as GPT-6.
- Ran `python3 scripts/check.py`: compilation passed, 18 quest tasks loaded and all 8 unit tests passed. `git diff --check` passed for the review changes.

### 2026-10-20 — integration — Clean requested wording
- Updated the communication preference in `AGENTS.md` and removed or revised related text across repository guidance, reports, code comments, and Thesis Desk data.
- Removed the dedicated note and one archived quest item. Preserved runtime behavior while renaming internal labels.
- Checked JSON parsing, Python compilation, and `git diff --check`; did not run the test suite.

### 2026-10-20 — week-1 — Sync and complete available repository tasks
- Merged `origin/integration-hub` into `codex/workspace` (merge `dc7ad46`), then merged the `research` raw-data index, `robot` recording script, and `thesis-desk` quest updates into `codex/workspace`.
- Added `experiments/raw_data_index.md`; no backup recordings were mounted in this cloud workspace, so it records the inventory limitation and storage recommendation rather than claiming a full local backup inventory.
- Added `ros2_yolo_ws/scripts/record_robot_day.sh` to record ROS 2 topics in MCAP and capture scenario, commit, and configuration metadata. Shell syntax and help output passed; ROS 2 is unavailable here, so a robot recording was not run.
- Updated Thesis Desk: removed quests 11–12 and restored quest 13 as Main Quest 5; the eight Main Quest IDs and order now match the plan.
- Windows-only source and tests could not be imported: this environment has no access to the listed Windows checkout, mounted source archive, or robot SSH endpoint. The requested integration-hub discussion/review remains pending because this work is limited to `codex/workspace` until the user authorizes writing to `integration-hub`.
- Checked JSON parsing, Python compilation, `bash -n` and `--help` for the recorder, and `git diff --check`. Did not run the test suite.

### 2026-10-20 — integration — Merge week-1 work and review T2
- Merged `codex/workspace` commit `3949ddc` into `integration-hub`; integration commit and push recorded after finalizing this entry.
- Replied to T2: the plan and task ownership are clear; `tools/robot_console/` is a reasonable default, but source recovery and hardware feasibility remain unconfirmed because the Windows checkout, backup, and robot endpoint are unavailable in this cloud session.
- Updated `HANDOFF.md` to reflect the integrated work and release the integration lock.
- Ran `python3 scripts/check.py` on `integration-hub`: compile passed, 16 quest records loaded, and all 8 unit tests passed. `git diff --check` passed. The recorder's ROS execution remains unverified in this environment.

### 2026-10-20 — integration — Judge Arena 1 entries
- Pushed `codex/workspace` sync `793d716` and Codex entry `52edffb` before posting the submission in T5. The arena entry remains separate and unmerged.
- Re-ran all five twin scenarios with both bridge modes, seed 0, on both submitted branches. Codex scored 99.44/100; Claude scored 99.41/100; neither had regression failures. `scripts/check.py` passed on each branch (19 and 22 tests respectively).
- Verified both branches descend from `d623baf`; `git diff --name-only --no-renames` reports only allowed paths, and neither changes `zlac_joystick_bridge.py`.
- Gazebo cross-check could not be run independently: building its Docker image exhausted the daemon's available disk. Since the frozen scores differ, the Gazebo tie-breaker was not applied.
- Replied in T5 and updated `HANDOFF.md`; integration lock released. Awaiting the user's judgment before merging either entry.


### 2026-10-21 — integration — Sync and resolve T5
- Merged `origin/integration-hub` `1ad3470` into `codex/workspace` with merge `59471a6` and pushed the workspace before replying to T5.
- Verified the combined controller is byte-identical to `52edffb`, its early-turn test body is AST-identical, and the three perception/fusion files are byte-identical to `929096d`.
- `python3 scripts/check.py` passed all 23 tests. Built the twin with `INSTALL_MCAP=0` and ran `curve_left/diff_drive` with seeds 0, 1 and 2: all turned, retained the target in FOV, and ended at gaps 0.5862, 0.5865 and 0.5892 m with no contact.
- Accepted the frozen-score verdict and the user's combined-fix decision in T5; marked the thread resolved and released the integration lock. Did not independently repeat the entire robustness matrix or Gazebo runs; the reply distinguishes those author-reported results from the new focused checks. Both original entry branches remain unmerged.

### 2026-10-21 — integration — Sync and review T6/T7
- 20:14 Thai time: fetched `origin`, merged `origin/integration-hub` into `codex/workspace` with merge `aab2725`, and pushed `codex/workspace`.
- 20:16 Thai time: `python3 -m unittest tests.test_drive_bridge_mixing` passed 9 tests; `python3 scripts/check.py` passed all 32 tests. Built `following-robot-twin` successfully. The requested twin run did not start because the 32 GB execution overlay had no free space; removed the temporary image, and did not claim a simulation result.
- 20:19 Thai time: claimed the `integration-hub` lock in `cc9f563` before editing the review threads.
- 20:22 Thai time: replied in T1 that the session exposes only the runtime label `GPT-6`, with no exact model ID or model-switch control; T1 remains open. Replied `agree` in T6 with default `turn_dir=+1` under the bridge's forward mapping, documented the conflicting `0x2089` calibration sign, and left T6 open for reconciliation. In T7, requested changes because the scorer accepts incomplete sample sets; answered all three draft questions and left rules unfrozen. Updated `HANDOFF.md`. No feature branch or Arena 2 entry was started, and no Claude branch was touched.

### 2026-10-21 — integration — Re-review Arena 2 scorer and calibration
- 21:24 Thai time: fetched `origin/integration-hub` at `2026540`, merged it into `codex/workspace` with merge `0853b53`, ran `python3 scripts/check.py` (41 tests passed), and pushed `codex/workspace`.
- 21:27 Thai time: claimed the `integration-hub` lock in `4f8d568`; ran `scripts/check.py` again before pushing the claim (41 tests passed).
- 21:29 Thai time: rebuilt temporary summary files from `experiments/arena/baseline_arena2_2026-10-21.json`; the scorer returned 66.01 with empty `out_of_scope`. Confirmed duplicate resolved input paths and missing `--agent`/`--base-ref` each exit 2. Found a `validate()` gap: removing all `seed` fields from one complete twin repeat while the other two use seeds 1 and 2 still returns no validation errors.
- 21:30 Thai time: replied `agree` in T6 that the reconciliation resolves the written calibration point; the physical turn check remains for robot day. Replied `change requested` in T7 with the missing-seed reproducer; rules remain unfrozen and no entry was started. T1 was not changed because this session still exposes no exact model ID. Updated HANDOFF and released the lock after the review.

### 2026-10-21 — integration — Final T7 scorer review
- 21:54 Thai time: fetched `origin/integration-hub` at `e2a63cb`, merged it into `codex/workspace` with merge `5d24c3a`, ran `python3 scripts/check.py` (42 tests passed), and pushed `codex/workspace`.
- 21:57 Thai time: reran the missing-seed reproducer; `validate()` now reports the missing integer seed and the CLI exits 2. Reconstructed the full-protocol baseline summaries and reran the scorer: 66.01, empty `out_of_scope`.
- 21:58 Thai time: claimed the integration lock in `5eb7c8a`; ran `scripts/check.py` (42 passed). Replied `agree` in T7. Kept the rules unfrozen and started no entry; the integration role is to name the freeze commit. Updated HANDOFF and released the lock.

### 2026-10-21 — integration — Post Codex Arena 2 entry
- 23:05 Thai time: fetched `origin/integration-hub` at `00a0584`, merged it into `codex/workspace` with merge `d2d0351`, ran `python3 scripts/check.py` (42 passed), and pushed the workspace.
- 23:07 Thai time: created `codex/robot/arena2-lag` directly from frozen base `9b78f1f`. Raised the Follow-Stop `linear_gain` default to `5.0` and added an offline command regression test. `scripts/check.py` passed 43 tests.
- 23:10 Thai time: attempted the twin Docker build for full-protocol self-scoring. The daemon failed while copying scripts with `no space left on device`; removing the unused old image also failed because Docker could not write its metadata. No twin/Gazebo summaries or self-score were produced; the integration judge must score both entries.
- 23:12 Thai time: committed and pushed the in-scope entry as `64dbe7f4a823d3662a4a5c36ea160b2b049bdea9`. The changed paths are the follower controller, its test, and `experiments/arena/entries/codex.md`. Did not read or fetch Claude's feature branch.
- 23:13 Thai time: claimed the integration lock in `2e246ef`, posted only the Codex entry SHA in T7, recorded the storage limitation in HANDOFF, and released the lock after `scripts/check.py` passed 42 tests. No entry branch was merged.

### 2026-10-22 — integration — Arena 2 cross-check
- 00:54 Thai time: merged `origin/integration-hub` (`8cce968`) into `codex/workspace` with merge `8509c82`, ran `python3 scripts/check.py` (42 tests passed), and pushed `codex/workspace`.
- 00:53 Thai time: rescored the committed raw summaries against base `9b78f1f`: Claude `3848164` scored 97.84 and Codex `64dbe7f4a823d3662a4a5c36ea160b2b049bdea9` scored 60.89; both had empty `out_of_scope`. Reviewed Claude's controller and tests; `scripts/check.py` on a read-only archive of `3848164` passed 49 tests. No Claude branch was changed.
- 01:01 Thai time: claimed the `integration-hub` lock to post the independent cross-check in T7 and update HANDOFF task 14.
- 01:02 Thai time: posted `agree` in T7 with both reproduced scores (97.84/60.89), empty `out_of_scope` results, the 49-test Claude snapshot check, and the conclusion that there is no merge blocker. Marked HANDOFF task 14 done; the Claude entry was already merged in `d8401a9`.
- 01:03 Thai time: released the `integration-hub` lock after the T7 reply and HANDOFF update.

### 2026-10-22 — integration — Resolve Arena 2 T7
- 01:04 Thai time: fetched `origin/integration-hub` at `f502cb5` and confirmed Claude's entry is merged at `d8401a9`. Claimed the integration lock to mark T7 resolved after the review and merge decision.
- 01:05 Thai time: set T7 to resolved, recording that the re-scored results agree and no issue blocks the already completed Claude entry merge; updated HANDOFF task 14.
- 01:06 Thai time: released the `integration-hub` lock after pushing the T7 resolution.

### 2026-10-22 — integration — Arena 3 and thesis review (T8)
- 02:36 Thai time: fetched `integration-hub` at `bbc3a8f`, merged it into `codex/workspace` with merge `7ff51ef`, ran `python3 scripts/check.py` (62 tests passed), and pushed `codex/workspace`.
- 02:38 Thai time: reconstructed scorer inputs from the committed baseline JSON files. Arena 3 scorer returned 60.64 and frozen Arena 2 scorer returned 66.01, both with empty `out_of_scope`. Reproduced that `turned=False` on a `curve_left/diff_drive` run leaves the Arena 3 behaviour check at 20 points when contacts are cleared.
- 02:40 Thai time: claimed the integration lock to post the T8 review, four answers, and thesis-review comment.
- 02:42 Thai time: posted a `change requested` review in T8 with an isolated reproducer for the `diff_drive` turn-check omission; answered all four open questions and noted the thesis review's missing rectangular-crop contamination limitation. Kept the Arena 3 rules unfrozen and started no entry.
- 02:43 Thai time: released the `integration-hub` lock after pushing the T8 review and HANDOFF update.

### 2026-10-22 — integration — Final Arena 3 T8 review
- 03:32 Thai time: fetched `origin/integration-hub` at `181e06e`, merged it into `codex/workspace` with merge `ac9f479`, ran `python3 scripts/check.py` (63 tests passed), and pushed `codex/workspace`.
- 03:34 Thai time: reran the baseline reproducer; the scorer now reports `curve_left did not turn in every run` and behaviour 15. Rebuilt temporary summaries from the committed Arena 3 baseline JSON; v3 returned 60.64 with an empty `out_of_scope`.
- 03:36 Thai time: claimed the integration lock to post the final T8 `agree`; rules remain unfrozen and no entry was started.
- 03:38 Thai time: reran the `diff_drive` turn reproducer (now reports `curve_left did not turn in every run`), re-scored the v3 baseline at 60.64 with empty `out_of_scope`, and posted `agree` in T8. Updated HANDOFF task 15; left freeze naming to the integration role and started no entry.
- 03:39 Thai time: released the `integration-hub` lock after pushing the final T8 review.

### 2026-10-22 — integration — Post Codex Arena 3 entry SHA
- 04:06 Thai time: merged `origin/integration-hub` (`53c4b08`) into `codex/workspace` with merge `50b6552`, ran `python3 scripts/check.py` (63 tests passed), and pushed the workspace.
- 04:08 Thai time: created `codex/robot/arena3-identity` from `08a7ac8`; pushed entry `4d22f4157bb61843d749f0089d07fd29f218c208`. The feature diff stays within allowed paths and `scripts/check.py` passes 69 tests. The full protocol could not run because the root overlay has 0 bytes available and `rclpy` is unavailable; this is stated in the entry note.
- 04:08 Thai time: claimed the integration lock to post only the entry SHA in T8 and update HANDOFF task 16.
- 04:09 Thai time: posted only entry SHA `4d22f4157bb61843d749f0089d07fd29f218c208` in T8 and updated HANDOFF task 16 with the recorded full-protocol limitation.
- 04:10 Thai time: released the integration lock after posting the Codex Arena 3 entry SHA.

### 2026-10-24 — integration — Arena 3 judging cross-check
- 16:11 Thai time: fetched `origin/integration-hub` at `caaf30f`, merged it into `codex/workspace` with merge `a43b4b2`, ran `python3 scripts/check.py` (63 tests passed), and pushed `codex/workspace`.
- 16:13 Thai time: re-scored committed Arena 3 raw summaries against base `08a7ac8`: Claude `191d2c1` scored 99.13 and Codex `4d22f4157bb61843d749f0089d07fd29f218c208` scored 94.13, both with empty `out_of_scope`. `scripts/check.py` on a read-only archive of Claude's commit passed 72 tests. Reviewed TargetGate, corridor give-way logic, and tests; found no merge blocker.
- 16:14 Thai time: claimed the `integration-hub` lock to post `agree` in T8 and update HANDOFF task 17.
- 16:15 Thai time: posted `agree` in T8 with the reproduced scores, scope results, 72-test Claude snapshot check, and no-merge-blocker review; marked HANDOFF task 17 done. Left both entry branches unmerged pending the user's decision.
- 16:16 Thai time: released the `integration-hub` lock after pushing the T8 cross-check.

### 2026-10-24 — integration — Robot-day kit and E7 review (T9)
- 17:58 Thai time: fetched fresh `origin/integration-hub` at `61443cf`, merged it into `codex/workspace` with merge `eeb630d`, ran `python3 scripts/check.py` (84 tests passed), and pushed `codex/workspace`.
- 18:00 Thai time: recomputed E7 using frozen `sim.arena.score_entry_v3.passes()`: full 30/30, no colour 27/30, no give-way 28/30 with 2 contacts, and no gate 12/30 with 8 contacts; all rows carried the expected `ros_params`. Reviewed robot-day kit and tests. No ROS 2 installation or twin bag was available.
- 18:01 Thai time: reproduced that `capture_to_cmd_vel_ms_median` sums component medians (200 ms) while paired capture-to-next-command latencies have a median of 110 ms. Claimed the integration lock to post the T9 review.
- 18:03 Thai time: posted an `object` in T9: E7 totals match, but `target_gate:=false` disables both data association and the nested give-way path; reported the E2 median-sum reproducer and recommended correcting or removing that aggregate before citing it. Confirmed the three previous findings are fixed; no ROS 2/twin bag was available; `scripts/check.py` passed 84 tests.
- 18:03 Thai time: released the integration lock after pushing the T9 review.

### 2026-10-24 — integration — T9 final review
- 18:07 Thai time: fetched `origin/integration-hub` at `cb8fe7d` and fast-forwarded local `integration-hub`; reviewed the revised E7 attribution and per-frame E2 calculation with its 110 ms regression test.
- 18:08 Thai time: ran `python3 scripts/check.py` (85 tests passed), claimed the HANDOFF lock in `b04a073`, replied `agree` in T9, and marked T9 resolved.
- 18:08 Thai time: pushed the T9 resolution in `2b8b119` and released the HANDOFF lock.

### 2026-10-25 — integration — T10 solo-following review
- 14:12 Thai time: fetched `origin/integration-hub` at `85a7757`, merged it into `codex/workspace` as `d6840d8`, ran `scripts/check.py` (102 tests), and pushed the workspace; claimed the integration lock in `30a95ea`.
- 14:12 Thai time: reviewed T10 code, protocol, tests and raw solo JSON. Frozen v3 `passes()` confirms post-fix solo 30/30 and identity 15/15, with no contacts.
- 14:13 Thai time: reproduced that LiDAR edge tracking publishes from a four-second-old cached scan without a freshness check. Posted `object` in T10 and recorded the requirement for the first drive.
- 14:13 Thai time: pushed the T10 objection in `00083ca` and released the integration lock.
- 14:17 Thai time: fetched `origin/integration-hub` at `675a49e`, reran the stale-scan reproducer (old/missing scans publish nothing; 0.1 s scan publishes), and ran `scripts/check.py` (103 tests). Claimed the HANDOFF lock in `61aa332`, replied `agree` in T10, and marked it resolved.
- 14:17 Thai time: pushed the T10 resolution in `e97c215` and released the integration lock.

### 2026-10-25 — integration — T11 review
- 19:08 Thai time: fetched `origin/integration-hub` at `34f9f65`, fast-forwarded local integration-hub, reviewed T11 robot fixes, bringup, preflight, thesis draft and the two simulation reports. Ran `python3 scripts/check.py` (115 tests passed); no simulator rerun.
- 19:08 Thai time: claimed the HANDOFF lock in `fe861fc`. Objected in T11 with code/draft reproducers and answers to the four open points, including the close-approach limit for robot day.
- 19:09 Thai time: pushed the T11 review in `5e4730d` and released the HANDOFF lock.
- 19:42 Thai time: fetched `origin/integration-hub` at `6ca5003`, reviewed the wheel-speed model, tests, thesis edits, robot-day notes and new realism result; reran the braking reproducer (cap 0 versus the old 0.566 m/s) and `scripts/check.py` (117 tests). Claimed the HANDOFF lock in `0eb9c31` and replied `agree` in T11. No simulator rerun or feature merge.
- 19:43 Thai time: pushed the T11 reply in `65f577a` and released the HANDOFF lock.

### 2026-10-25 — integration — T12 bearing steering review
- 22:58 Thai time: fetched `origin/integration-hub` at `d8a421e`, fast-forwarded local integration-hub, reviewed bearing steering, launch, E7 addendum, thesis and Thai cheat sheet. Recounted committed JSON with frozen v3 `passes()` and ran `scripts/check.py` (119 tests). No simulator rerun or feature merge.
- 22:58 Thai time: claimed the HANDOFF lock in `b62d071`, then objected in T12 to trying bearing mode before a target-message freshness stop. Flagged the clean-twin result label and thesis 4.7 attribution.
- 22:59 Thai time: pushed the T12 review in `f36336d` and released the HANDOFF lock.
- 23:57 Thai time: fetched `origin/integration-hub` at `50eba89`, reviewed the bearing-only stale-message timer and document fixes. Reproduced one zero command at 0.4 s after a 0.3 s timeout and recounted new JSON: clean solo 30/30, realism solo 30/30, realism identity 15/15, no contacts. `scripts/check.py` passed 120 tests. Claimed the lock in `df448d4`, replied `agree` in T12, and marked it resolved. No simulator rerun or feature merge.
- 23:58 Thai time: pushed the T12 resolution in `c9006fc` and released the HANDOFF lock.

### 2026-10-26 — thesis-desk — web dashboard prototype
- 00:24 Thai time: fetched `origin/integration-hub` and synced `codex/workspace`; reviewed the existing Claude Thesis Desk data, Tkinter tracker, and Godot app. No web dashboard was present in the repo.
- 00:28 Thai time: created `codex/thesis-desk/web-dashboard` (`5d52cbc`) with a static Thai dashboard in `tools/thesis_desk/web_dashboard/`: overview, quest roadmap, search/filter, task editor, evidence index, browser-local persistence, JSON export, and preview. Merged it into `codex/workspace` without editing the original tracker or seed data.
- 00:28 Thai time: `python3 scripts/check.py` passed 120 tests; Node syntax check passed. Opened the page in headless Chromium, confirmed all 16 tasks loaded, and exercised search, detail editing, and persistence across reload. Preview captured in `preview.png`.

### 2026-10-27 — integration — T13 colour-gate review
- Synced `codex/workspace` with `origin/integration-hub` (`56656ba`) in a separate worktree; reviewed only the merged `integration-hub` code and evidence. Did not check out or edit Claude's unmerged branches.
- On `integration-hub`, ran `scripts/check.py` with bundled Python and writable temp variables: **127 passed**. Re-ran `gate_replay.py`, `heldout.py` and `weight_sweep.py` with `SYNC_FUSION` set to the hub's `sync_fusion_node.py`; all three outputs match their committed result files.
- Recounted 215 rows in `experiments/sim/2026-10-27_hs_colour_twin_w025.json`; group pass counts match the stored flags and available numeric conditions. JSON does not include final target bearing/FOV.
- Built a gate-level `sim.twin.World` occlusion case with realism enabled. A same-clothing stranger at 18°, 7.43 m after 1.2 s unseen was re-acquired 5/5 seeds with the histogram (colour cost 0.098–0.393); no-hist was 0/5. Posted `change requested` in T13: re-acquisition needs a plausible track/range condition or explicit ambiguity plus a regression case. Also clarified the predicted-place cost and synthetic-model limits.
- Timed `torso_hs_hist` on this Windows host, not the robot: median/p95 0.135/0.148 ms for 2,800 ROI pixels; 0.283/0.361 ms for 7,840; 0.582/0.674 ms for 17,640 (OpenCV 5.0.0, NumPy 2.5.4, single-thread). Robot-PC timing is still needed.
- Full ROS closed-loop twin could not run: Docker and `rclpy`/ROS 2 are absent and WSL returned `E_ACCESSDENIED`. The gate-level reproducer and recount are not described as closed-loop results. Claimed the integration lock (`f065741`), posted the T13 review and released the lock; T13 stays open for the design response, explicit threshold-tuning wording and full closed-loop/robot-PC checks.

### 2026-10-27 — integration — T13 re-review
- Reviewed the T13 response at `58dcdc3` and merged change at `b102cc7`. This entry preserves the earlier uncommitted re-review draft; the user relayed its agreement, recorded on `integration-hub` in `5d8e62e`.
- At detached commit `808dc6c`, replayed the same-clothing candidate with true range: 18°, 7.43 m, 1.2 s unseen; `TargetGate.accept` rejected it. The measured separation from last fix was 6.489 m versus 2.6 m allowed reach (0.8 m + 1.5 m/s × 1.2 s). `track_unchanged=True`.
- Ran `test_a_look_alike_far_away_is_not_taken_back` and `test_reacquisition_reach_grows_with_time_but_is_capped`: 2 tests passed.
- Reviewed the 85-row T13 twin evidence and fusion association. `lookalike_after_loss` is 9/10 both with and without the distance rule. Its far box can borrow the near target's LiDAR range, pass the normal gate, and bypass re-acquisition. This is a real end-to-end association weakness, but a separate upstream camera/LiDAR range-association defect; it does not invalidate the narrower tested re-acquisition change. Recommend closing T13 only with this limitation explicitly retained and tracking correct per-box range association as a follow-up. No end-to-end identity guarantee is claimed.
- Full `scripts/check.py`, ROS closed-loop reruns and robot-PC CPU timing were not repeated in this re-review; the current discussion reports the 130-test integration check and the closed-loop runs, while the gate tests above were reproduced independently.

### 2026-10-27 — integration — Reconcile T13 resolution and review drafts
- Reconciled the earlier uncommitted `HANDOFF.md` and `logs/codex.md` drafts against hub commit `5d8e62e`. Preserved the re-review evidence above and discarded the stale, unpublished Codex integration-lock claim. The local hub worktree is clean at `5d8e62e`.
- Synced `origin/integration-hub` into `codex/workspace`. `HANDOFF.md` retains the hub's exact state: lock ready/unowned, item 16 T13 resolved with the stated limitation, and item 17 the separate per-box LiDAR range follow-up (owner Claude, reviewer Codex). The follow-up remains not started; the 9/10 rule-on/rule-off result is not end-to-end proof of the distance rule.
- Ran `python scripts/check.py` on the synchronized workspace with writable temp variables: all 130 tests passed. The reconciliation is a merge commit on `codex/workspace`; no new review verdict or source-code fix was added.

### 2026-10-27 — research — Prepare to continue Claude's work
- At the user's request, fetched the latest pushed refs and synced `codex/workspace` with hub `ea1fc96` in merge `ad99acc`. T14 is open; hub lock is ready and unowned. No Claude branch was edited.
- Created `codex/research/claude-continuation` and wrote `docs/CODEX_CONTINUATION.md`: exact branch/commit snapshot, T14 review queue, evidence provenance, pending long-cluster patch `d23e7b2`, runtime requirements, sequential twin commands and coordination rules. The pending patch remains unmerged and has not been independently validated in this preparation.
- Ran `python scripts/check.py` on the synced hub code with writable temp variables: 134 tests passed. Verified the continuation note's local links and that HANDOFF exactly matches the fetched hub. Docker/ROS closed-loop work and robot-PC timing remain unavailable locally; no new T14 verdict was posted and no quest status changed.
- Prepared the documentation for a merge back into `codex/workspace` and publication there. Refresh refs before taking over because Claude's unpushed cloud work is not visible in this snapshot.

### 2026-10-28 — research — T14 independent review evidence
- Synced hub `d328ca7` into `codex/workspace` (`f7809ef`) and created `codex/research/t14-review`. Read T14, `d23e7b2`, the sectorizer, fusion callback, tests, launch defaults, robot-day protocol and the committed twin results. No Claude branch or robot source was edited.
- Saved a standard-library reproducer, JSON output and review report under `experiments/reviews/`. The reviewed fusion source matches `d23e7b2`; the borrowed-range replay takes 7.43 m rather than a sector median of 0.8 m and rejects the stranger (6.489 m displacement versus 2.6 m reach). Synthetic leg/neighbor, bearing-frame and skip/give-way checks expose the documented heuristic limits.
- Recomputed Fisher p=0.5874826431 conditional on reported 15/28 vs 18/28, and reproduced the stated bearing rejection at cost 13.355 (13.223 even with zero range error). The JSON lacks the 40 new side-step rows and off seeds 0–2; the debug traces are absent. Found that the existing borrowed-range regression uses a minimum to model the production sector median. Verdict prepared: object until the evidence/fixture are corrected or the unsupported claims narrowed.
- On clean `integration-hub` at `d328ca7`, `python scripts/check.py` passed 135 tests with writable temp variables. Executed the new gate-level harness successfully; no ROS closed-loop or hardware run was claimed. T14 reply and hub coordination update will be published separately under the integration lock.

### 2026-10-28 — integration — T14 verdict
- Reviewed hub `d328ca7` / fusion code `d23e7b2`; hub `python scripts/check.py` passes 135 tests. Saved independent synthetic review evidence in Codex research commit `1b4b1f0`, merged/pushed to `codex/workspace` as `d6f7cb0`.
- Claimed the free integration lock in `5e67160` and posted **object to closing T14**. The requested borrowed-range case passes: 7.43 m is rejected (6.489 m displacement vs 2.6 m reach), whereas the sector median of 0.8 m is accepted. Answered legs, bearing-frame and skip/fallback questions with measured synthetic limits and explicit hardware limits.
- Reproduced conditional Fisher p=0.5874826431 and bearing-gate rejection cost 13.355, but the repo lacks 40 new trial rows, off seeds 0–2 and debug traces. Requested data or narrower claims and corrected seed accounting. Also found the old-sector regression uses a minimum although the production sectorizer publishes a median; requested a production-faithful fixture.
- Released the lock ready/unowned; T14 stays open for those validation corrections. HANDOFF item 18 remains a separate proposal. No Claude branch, robot source, hardware or closed-loop runtime was changed by this review.
- Synced the published T14 verdict back into `codex/workspace`, retaining both the existing research/history entries and the hub verdict entry when resolving the append-only log conflict.

### 2026-10-28 — research — T14 re-review of corrected records and debug traces
- Synced response `61a1181` / merge `f0a79ab` into `codex/workspace` and created `codex/research/t14-rereview`. Updated `t14_gate_review.py` to derive cohort counts and exact Fisher p from records, explicitly including historical `808dc6c` off seeds 0–2 rather than hard-coding 18/28 or filtering only `d23e7b2`.
- Recounted 56 unique on/off observations: 15/28 vs 19/28, Fisher p=0.4121129454; no missing seeds or duplicates. The 43 added rows include 40 new trials and the three historical rows, which match their T13 source at recorded precision. Current-code seeds 3–27 give 15/25 vs 18/25, p=0.5512; the 40 new trials alone give 12/20 vs 13/20. AST comparison confirms off-mode operational equivalence and unchanged sim code, while historical-session limitations remain.
- Added `t14_trace_audit.py` and a new re-review report/JSON artifacts. Applied the debug patch only to a temporary copy; patched/unpatched state/publications match in nine fixed callback cases. Verified angular-only rejection lower bounds above 9 in both failing traces. All debug scores are separate instrumented reruns, not counted cohort trials; seed 12 reverses outcomes and is explicitly kept separate.
- Executed the actual sectorizer callback: median 0.8 m for the revised fixture. The new regression passes and an old-sector-only mutant fails it. The full-histogram gate replay still accepts borrowed 0.8 m but rejects 7.43 m without changing the track. Hub `python scripts/check.py` passes 135 tests. No fresh ROS closed-loop or physical run was performed.
- Prior objection prepared for withdrawal: records, regression and retained limits address the requested changes. New report verdict is agree within the documented software scope. The old review/output remain labeled historical; the new results do not claim equivalence, calibrated legs or physical alignment. Hub reply/status update will follow under the integration lock.

### 2026-10-28 — integration — Resolve T14 after independent re-review
- Re-reviewed Claude response `61a1181` / merge `f0a79ab`; hub `python scripts/check.py` passes 135 tests. Updated audit and evidence are in Codex research commit `8c27493`, merged/pushed to `codex/workspace` as `79b331b`. The obsolete hard-coded 18/28 table and code-only inventory were replaced with dynamic, cross-version per-seed counts.
- Verified 43 added records and 56 unique cohort observations: on 15/28, off 19/28, Fisher p=0.4121129454. Historical off seeds match the T13 source; source AST/sim parity supports the off-mode comparison, while session differences remain disclosed. Contemporary subsets also detect no difference; no equivalence claim is made.
- Applied the debug patch only to a scratch copy and compared nine callback cases; state/publications match. Checked both failing trace mechanisms with rounding-aware bearing-only lower bounds above the gate. Recorded that all four traces are separate instrumented reruns, including reversed seed-12 outcomes; they are not added to the counted trials.
- Confirmed actual sectorizer median 0.8 m, revised regression pass, old-sector-only negative-control failure, and the full-histogram 7.43 m rejection. Leg/frame/skip/fallback limits remain documented. No robot source or Claude branch changed, and no fresh ROS/hardware run was performed.
- Claimed the integration lock in `ae877c5`, posted **agree** and resolved T14. Updated HANDOFF item 17 to the corrected current state; item 18 remains proposed and not started. Released the lock ready/unowned.
- Synced hub resolution `13f570b` back into `codex/workspace`; retained both the research and integration log additions when reconciling the append-only conflict.

### 2026-10-28 — research — Adversarial T15 review
- Fetched and synced hub `207ceda` (merges `8b946b7`, `a059bcc`) into `codex/workspace`; reviewed AGENTS/HANDOFF/T15, gate source/tests, both experiment scripts and the T13 correction. Created `codex/research/t15-review`; added reproducible offline audit, JSON output and report under `experiments/reviews/`.
- Hub and workspace `python scripts/check.py` pass 138 tests. Recounted all 165 records: side_step 19/20 vs 5/20, Fisher p=0.0000100211; zigzag 8/10 vs 6/10, p=0.628483; actual rule off 0/20 with 18 contacts vs on 20/20. Checked unique cohort/seed coverage and parameters; flags cannot be fully re-scored because final FOV/unrounded inputs were discarded. No Docker/ROS executable is available; no fresh closed-loop/hardware run claimed.
- Verified radians/mean-range/floor arithmetic; 20,000 synthetic old-vs-zero-lateral frames have identical cost/accept/state. T13 full-histogram 18-degree/7.43-m replay rejects at 6.489181 m displacement vs 2.6 m reach, accepts with reach 100.0. Historical correction adequately retracts the invalid ablation and distinguishes current-code evidence.
- Reproduced a close-person regression through production box_range and try_sync_from_yolo: circular people at (1,0)/(1,0.44), disjoint silhouettes fully in view, own ranges 0.8/0.89257 m, matching colour. At lateral 0.15 the stranger costs 5.8499 and becomes last_target after the genuine target's callback; 0/0.10 reject (22.9424/12.6862). The current pass metric does not count wrong-person publications. Prepared object to closing on 0.15 pending targeted identity regression/default comparison; a narrower value is a candidate, not validated replacement.
- Existing parameter guard catches dictionary name/default changes but stays green if declarations or forwarding are removed. Real constructor with strict stubs forwards all ten overrides currently. Preparing a permanent constructor-level guard on a separate QA branch; robot source/defaults and Claude branches remain unchanged.

### 2026-10-28 — qa — Guard actual ROS-to-gate parameter wiring
- Created `codex/qa/t15-parameter-wiring` from `codex/workspace` after merging review evidence `23ae14b`. Extended the ROS-free loader with an injectable node base and added a test executing the actual SyncFusionNode constructor with distinct non-default overrides for all ten GATE_PARAMS names. A strict declaration stub raises on undeclared reads; the constructed gate's full state must match the requested overrides.
- `python scripts/check.py` passes **139 tests**, and `git diff --check` passes. Temporary source mutants prove the new test fails when forwarding is replaced by TargetGate(), declarations are removed, or parameter reads use defaults. The production control passes. Mutants were created only in a temporary scratch directory and removed; no robot source changed.
- This is an offline wiring regression test, not actual rclpy CLI/type/service validation. The 0.15-m default remains unchanged pending the T15 close-person/default comparison requested in the review; this QA commit is ready for integration separately from that design decision.
