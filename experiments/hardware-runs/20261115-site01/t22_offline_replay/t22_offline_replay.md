# T22: offline bag replay of the edge-track fix (PR #21)

On 2026-11-18, Claude ran this on the laptop. It used no robot, no ROS and no motors.

Two code trees were compared:
- **026fe17**: the robot-day code, which had the wrong turn on 2026-11-15.
- **05bb929**: the head of PR #21 (`codex/robot/t22-edge-track`), with all three CI jobs green.

The bags come from `C:\Users\Time\Documents\robot_day_data\20261115-site01\`. Their md5 values match
`MANIFEST.md5`:
- `20261115T060903Z_e6_session` (`9f5d58be…`)
- `20261115T041627Z_follow_first_short/recording` (`2558dbc4…`)

## Result

**The T22 done criterion is not met yet.** The E6 bag still has one wrong-direction turn at ≥ 0.9 m under
05bb929, in one of 24 timings. The mechanism is new: the prediction drifts towards the edge, and the
latch does not cover that case. Details are below. The first-follow bag replays from a cold start and
cannot reproduce its failure in either version, so it says nothing about the fix. The twin score
(baseline 106/110, 0 contacts) has not been run. It needs ROS in Docker, and this laptop has neither.

## Method

`offline_replay.py` loads the four node scripts from the code tree under test, unchanged:
`lidar_sectorizer`, `sync_fusion`, `fusion_prob` and `follow_stop`.
- **Stubs:** stub `rclpy` and message modules replace ROS, and all nodes share one simulated clock.
- **Inputs:** the same as `sim/replay/replay_bag.py`: `/scan`, `/target_centroid_sector` and
  `/target_centroid`, at their bag receive times.
- **Timers:** they fire at their periods between messages.
- **Parameters:** the robot-day run of `start_follow.sh on sector` plus the E6 overrides:
  `lidar_angle_offset_deg 6.2`, `lidar_angle_sign −1`, `target_distance 1.0`,
  `front_band_radius 2` and `wide_front_radius 2`, with `obstacle_stop` on and `avoid_trail` off. The
  first-follow bag uses `target_distance 0.5` and the default bands.
- **Rule:** the `e6_check.py` rule with its constants. A wrong turn has |wz| > 0.05 rad/s, a fused range
  ≥ 0.9 m, and a turn opposite to the side of the largest `/yolo_frame` box, where that box is more than
  7.8° off centre.

**Fidelity.** With 026fe17 and no timing shift, the replayed `/synced_target` and `/cmd_vel` match the
recording to within about 20 ms per message, up to t = 586.4 s. This is clear in
`trace_e6_026fe17_d0_p0.csv`. After that point they diverge: the real run moved the track to the left
edge, and this timing did not. Real ROS delivers messages asynchronously, and the bag does not record
YOLO latency or timer phase. So the replay sweeps both:
- the YOLO delay, 0–100 ms, applied to the centroid topics;
- the phase of the 0.1 s track timer, 0–75 ms.

That gives 24 timings per bag (`sweep.py`).

## E6 bag: wrong-direction turns per timing

Each cell is the number of wrong `/cmd_vel` messages. Every one is at t = 587.4–588.0 s (bag time),
which is the event recorded on 2026-11-15.

| YOLO delay \ timer phase | 026fe17 0 | 25 | 50 | 75 | 05bb929 0 | 25 | 50 | 75 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 ms | 0 | 0 | 0 | 7 | 0 | 0 | 0 | 0 |
| 20 ms | 7 | 0 | 7 | 1 | 0 | 0 | 0 | **1** |
| 40 ms | 7 | 8 | 0 | 0 | 0 | 0 | 0 | 0 |
| 60 ms | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 80 ms | 0 | 0 | 7 | 0 | 0 | 0 | 0 | 0 |
| 100 ms | 0 | 0 | 7 | 7 | 0 | 0 | 0 | 0 |
| **failing timings** | **9 / 24** | | | | **1 / 24** | | | |

The recording itself has 5 wrong messages, at 587.51–588.01 s. The rows are in
`sweep_e6_026fe17.json` and `sweep_e6_05bb929.json`. The 05bb929 fix removes the long wrong turn,
about 0.6 s at 0.8 rad/s, in all 8 of those timings. In those runs the latch stops the robot.

## The remaining case (delay 20 ms, phase 75 ms)

This case is in `probe_05bb929_d20_p75.txt` and `trace_e6_05bb929_d20_p75.csv`.

1. **586.6–586.9 s:** the robot is turning left. Boxes at +22° down to +9° are rejected. The
   prediction runs on from +27° to +34.5°, because the gate's angular velocity is still from the turn.
2. **587.09 s:** a box at +3.0° and 0.95 m is accepted. This becomes `last_camera_fix`, and the latch
   clears.
3. **587.26–587.78 s:** boxes at −6.9°, −17.3°, −26.6° and −30.5° are rejected. The person is walking
   right. The prediction is +18.9° to +25.2°, still inside `edge_rad` (27°). `camera_lidar_conflict()`
   needs the prediction beyond the edge, so **the latch does not set**. Nothing is published, and the
   robot is stopped.
4. **587.995 s:** with no newer box, the prediction crosses the edge (+27.9°). `track_with_lidar` takes the
   LiDAR cluster and publishes the **left edge, cx = 0, at 0.92 m**. `follow_stop` turns left at
   0.8 rad/s while the camera's last box is at −30.5°.
5. **588.095 and 588.195 s:** more track publications follow, at cx = 75 and cx = 147. The turn lasts
   about 0.2 s, roughly 9°.

In short, the latch only tests a rejected box against the prediction **at the moment of rejection**.
Opposite-side boxes rejected before the prediction reaches the edge are forgotten. A LiDAR edge track
that starts later on the far side is then allowed. This fits the known limit "no camera box", but here
the boxes existed; they came a little too early.

**Suggested direction (for Codex; not implemented):** fail closed in `track_with_lidar` and
`assist_with_lidar` whenever a camera box has been rejected since `last_camera_fix` and that box was
inside the image on the opposite side of, or centred relative to, the bearing the track would publish.
Doing this does not require the prediction to be past `edge_rad` when the box is rejected. It needs a
unit test built from this sequence, and the sweep above should show 0 / 24 for the E6 bag.

## First-follow bag

The recording has 5 wrong messages, at t = 1.74–1.94 s. The replay starts with fresh nodes, so the
gate locks later than on the robot: 110 replayed `/cmd_vel` against 164 recorded. Neither version
reproduces the event, with 0 / 24 for both. **Inconclusive.** It is neither a pass nor a fail for the fix.

## Still to do for T22

- Close the remaining case: the next round for Codex, with the probe sequence as a test.
- Re-run this sweep, with a target of 0 / 24 on the E6 bag.
- Run the full twin, 110 runs in the robot-day configuration, on a machine with Docker or as a CI job.
  The target is at least 106/110 with 0 contacts.

Re-run, from this folder, using a Python environment with `rosbags` and `numpy`:

```
python sweep.py <bag dir> <code>/ros2_yolo_ws/scripts e6 <out dir>
python probe_d20_p75.py <code>/ros2_yolo_ws/scripts
```

## Round 4: b6d1862 (2026-11-18)

Codex's round 4 implements the suggested direction:
- `sync_fusion` remembers in-image camera boxes that the gate rejected since the last accepted camera fix.
  It keeps only boxes within `lidar_track_max_s` of that fix, and within the new parameter
  `lidar_conflict_range_tolerance_m` (default 0.5 m) of the predicted range.
- Before `track_with_lidar` publishes, or `assist_with_lidar` moves the gate, a remembered box on the
  opposite side, or in the centre, sets the fail-closed latch.

Claude's changes on top:
- **Guard.** The memory now consults the gate only when it is locked and has a time. Without the guard,
  `_predict` raises after an unlock whenever `lidar_track_max_s` is longer than `unlock_after_s`. A new
  test covers this.
- **Test fixtures.** The fixtures now use the plain gate while someone is beside the target, as in the
  bag. The tests count publications per call, and an out-of-range box is not remembered.

All four new tests fail on 05bb929. `scripts/check.py` passes 260/260. The commit is pushed to PR #21.

| Bag (24 timings each) | 026fe17 | 05bb929 | **b6d1862** |
| --- | --- | --- | --- |
| `e6_session`, timings with a wrong turn | 9 | 1 | **0** |
| `e6_session`, `/synced_target` summed over 24 runs | — | 4490 | 4436 (−1.2 %) |
| `follow_first_short` (cold start, inconclusive) | 0 | 0 | 0 |

At the timing that used to fail (delay 20 ms, phase 75 ms), the robot now stops (0, 0) at 587.40 s and stays stopped. It no longer turns left at 587.995 s; see `trace_e6_b6d1862_d20_p75.csv`.
The rows are in `sweep_e6_b6d1862.json` and `sweep_first_b6d1862.json`.

**Still to do:** the full twin in the robot-day configuration, with a target of at least 106/110 and
0 contacts. The new memory can stop a legitimate LiDAR edge track. The scenarios at risk are
`blind_corner`, `crossing`, `pass_by`, `fast_side_step_left` and `walk_up_same`. This needs ROS in
Docker, which this laptop does not have.

## Full twin, robot-day configuration (2026-11-18)

**Protocol.** This uses `experiments/sim/scripts/run_baseline.sh`, the same protocol as the 6a64669
baseline:
- every scenario in `SCENARIO_LOOKUP`, seeds 0–4;
- the realism profile and the mps bridge;
- the node defaults, which are the robot-day settings;
- scoring with the pass rule in `experiments/sim/scripts/collect_runs.py`.

**How it ran.** It ran on GitHub Actions with the workflow `.github/workflows/twin-full.yml`, one job
per seed. Each job builds its own image, so each seed has its own image id; the ids are in the run
artifacts. The workflow runs only on a push to `claude/twin-full/**`, never on PRs, and it is not part of
PR #21. There were two runs:
- `claude/twin-full/t22-b6d1862`: run 44312067240;
- `claude/twin-full/t22-05bb929`: run 44314564394.

| Code | Baseline set (22 scenarios × 5) | Contacts | All 23 scenarios | `blind_corner` | `pass_by` | `fast_side_step_left` |
| --- | --- | --- | --- | --- | --- | --- |
| 6a64669 (2026-11-01 baseline) | 106/110 | 0 | — | 1/5 | 5/5 | — |
| 05bb929 (round 3) | 107/110 | 0 | 107/115 | 2/5 (s2, s3) | 5/5 | 0/5 |
| **b6d1862 (round 4)** | **106/110** | **0** | 106/115 | 2/5 (s1, s4) | 4/5 | 0/5 |

The rows and summaries are in `twin_full_rows_<code>.json` and `twin_full_summary_<code>.md`.

- **T22 twin criterion met.** The criterion is "not worse than 106/110 with 0 contacts", and b6d1862 scores
  106/110 with 0 contacts.
- **`blind_corner`:** 2/5 on both commits, on different seeds. This was already a recorded failure, and
  the result on any given seed changes from run to run. On 2026-11-01, repeating `bdae2c1` gave
  110 and then 109.
- **`pass_by` s0, b6d1862 only:** the view share is 0.874 against the 0.9 rule, the final gap is 0.539 m,
  and there was no contact. At t = 12.1–12.6 s the robot stood still next to the hidden worker, who was at
  0.63 m and +58°, until the target was more than 2 m away. The worker is never detected by the camera,
  so no rejected box exists, and the round-4 memory is unlikely to be the cause. A stop near the worker
  looks more likely, but this is not proven. One rerun of `pass_by` on both commits would settle it.
- **`fast_side_step_left`, the T22 scenario: 0/5 on both commits.** This is not a fusion fault. The
  target's path, from (2.4, 1.4) to (4.0, 2.2), passes between two realism clutter objects: the post at
  (3.0, 1.4, r 0.06) and the bush at (2.5, 2.2, r 0.3). The robot stops at (2.45, 1.31) with LiDAR
  clearance 0.41–0.46 m, which is `obstacle_stop_m` 0.45. It backs off slowly, and the target walks
  out to 4.2 m. Every published target is the real target. The obstacle stop is right to stop here; the
  scenario's path needs to be moved clear of the clutter, or the scenario needs to be marked as an
  obstacle case.

**CI on PR #21 at b6d1862:** `check`, `twin` and `gazebo` all pass.

## Correction (2026-11-18, after the safety audit)

The full-twin section says that in `fast_side_step_left` "every published target is the real target". That
is not exactly right. On b6d1862, s3 published 1 of its 152 messages as someone other than the target;
the other seeds had none. Across all runs, `published_other > 0` appears in 46 of 115 runs on b6d1862 and
62 of 115 on 05bb929. This has not been explained yet. The conclusion that the stop comes from the
obstacle stop, triggered by the clutter at 0.45 m, still holds. The stop is still not a fusion fault.

## Independent safety audit of round 4 (safety-auditor, 2026-11-18)

**Verdict:**
- **PR #21 at b6d1862, offline:** approve with changes.
- **"T22 fixed":** needs evidence. What the evidence supports is "not reproduced offline on the E6 bag".
- **Robot motion:** NO-GO.

**Auditor's own checks:**
- `check.py`: 260/260.
- A finer sweep, 420 timings: b6d1862 0/420; 05bb929 7/420, all at 587.86–588.06 s.
- A mutation test of each new guard.

Claude re-ran the auditor's probes (`audit_tools/probes.py` in the session scratchpad) against b6d1862
and confirmed 1, 2, 6 and 7 below.

1. **Fails open, range tolerance.** A rejected opposite-side box is not remembered when its range differs
   from the prediction by more than 0.5 m. Two cases were tested: 0.6 m beyond, and 0.40 m against a
   predicted 0.95 m. A box with no LiDAR range returns before the gate and is never remembered. In both
   cases the node publishes the left edge, cx 0. In a fast side step, the box range often points at
   background: in this same bag, the target's own boxes read 2.85 m against a predicted 1.0 m.
2. **Fails open, sign-only side test.** Boxes rejected at −1.5 to −2.5°, a person straight ahead, do
   not block a track that drifted to the right edge. The node publishes cx 639.
3. **`pass_by` s0 unexplained, and the latch is not logged.** A `[CONFLICT]` log line is needed, then a
   `pass_by` rerun.
4. **Availability.** In the replay at delay 20 ms and phase 75 ms, the robot stays stopped for 61 s, until
   the next lock-on. The first command after recovery is the existing give-way reverse at −0.75 m/s.
5. **Over-trigger.** The assist latches before its other filters. This costs availability only.
6. **Bad tolerance values.** A negative or NaN tolerance silently turns the memory off, and the value is
   not in the `[GATE]` log. Remembered bearings are not corrected for the robot's own rotation.
7. **Pre-existing.** The give-way path ignores the memory. A probe published the stale camera column,
   cx 107 at 0.5 m, while opposite boxes were remembered.

**Test quality.** All four new tests fail on 05bb929, but only with an AttributeError. Several
behaviours are not pinned by any test:
- where the assist check sits;
- `<=` against `<` for a centred box;
- expiry of the memory after `lidar_max`;
- the order of boxes within one frame;
- give-way with remembered boxes.

**Before any robot test:**
- fix 1–3, or accept them in writing;
- do a read-only hardware run with the drive disabled and the latch logged;
- then the full motion gate.

## Round 5: 2105e58 (2026-11-18)

Round 5 is Codex's answer to the audit, plus Claude's fixes:
- **Unlock crash:** the gate is checked again after `accept()`.
- **Memory bug:** the give-way check had been deleting the box it skips from the memory.
- **Fixtures:** three test fixtures were corrected.

**Offline results:**
- `scripts/check.py` passes 271/271.
- The auditor's probes P1, P2, P2b, P5 and P6 now publish nothing and latch. P4 remains a known limit.
- The E6 sweep gives 0/24; `/synced_target` summed over the 24 runs is 4426.

**Full twin (run 44323782326): 104/110 on the baseline set, 0 contacts, 104/115 overall.** This is
below the T22 criterion of 106/110.

| Code | Baseline set | `blind_corner` | `pass_by` | `zigzag` |
| --- | --- | --- | --- | --- |
| 05bb929 | 107/110 | 2/5 | 5/5 | 5/5 |
| b6d1862 | 106/110 | 2/5 | 4/5 | 5/5 |
| **2105e58** | **104/110** | **0/5** | 5/5 | **4/5** (s4: gap 3.84 m, view 0.247) |

**Cause: the memory over-triggers.** `[CONFLICT] on` appears in 94 of 115 runs: 528 times with
`memory-assist` and only 3 with `memory-track`. It appears in single-person scenarios too (`straight`,
`walk_1p0`, `zigzag`). The counts are in `conflict_counts_2105e58.txt`. When the gate rejects the
target's own box near the image centre for one frame, that box is remembered. The ±10° centre band then
latches the next LiDAR assist, even onto the same person: in `zigzag` s4, a box at −7.1° and 1.67 m
latched a cluster at −12.7°. Each latch cuts the LiDAR assist until the next accepted camera box. That
costs the robot the cases that need the LiDAR, `blind_corner` and fast turns. There are still no
contacts.

**Design options for round 6 (not yet implemented):**
- **A.** Use the memory only to stop a LiDAR-only publication, in `track_with_lidar`, which already checks
  before it publishes. Do not use it to latch from `assist_with_lidar`. The auditor judged the assist
  check to be an availability matter, not a safety one.
- **B.** Replace the centre band and the sign rule with an angular separation rule. A box contradicts a
  LiDAR bearing only when |box − LiDAR| is more than X°, for example 15–20°. P1, with the box at −2° and
  the track at −31°, is still caught. The same person, with the box at −7° and the cluster at −13°, is not.

## Round 6: ba53ed2 (2026-11-18)

The user chose to make both changes, A and B, in this round:
- **A:** the memory now blocks only a LiDAR-only publication in `track_with_lidar`. It no longer latches
  from `assist_with_lidar`.
- **B:** a box contradicts a bearing only when the two are more than `lidar_conflict_sep_deg` apart
  (default 20°). This replaces the centre band and the sign rule.

Claude corrected the fixtures of two of the new tests.

**Offline results:**
- `scripts/check.py` passes 272/272.
- The new tests fail on 2105e58.
- The auditor's probes still fail closed.
- The E6 sweep gives 0/24.

**Full twin (run 44330591298): 104/110 on the baseline set, 0 contacts.** All three PR CI jobs pass.

| Code | Baseline set | Runs with `[CONFLICT]` | `blind_corner` | `zigzag` |
| --- | --- | --- | --- | --- |
| 05bb929 | 107/110 | (not logged) | 2/5 | 5/5 |
| b6d1862 | 106/110 | (not logged) | 2/5 | 5/5 |
| 2105e58 | 104/110 | 94/115 | 0/5 | 4/5 |
| **ba53ed2** | **104/110** | **5/115** | 0/5 | 4/5 (s3) |

- **The over-trigger is gone.** There are 5 `memory-track` latches and 1 `edge` latch, in 5 runs:
  `blind_corner` s0, s2 and s4, `zigzag` s3, and `fast_side_step_left` s4.
- **`blind_corner` is 0/5,** but s1 and s3 failed without any latch. `blind_corner` already varies
  between runs (1, 2, 2, 0 and 0 out of 5 across the five commits). That the latch is the cause in s0,
  s2 and s4 has not been shown.
- **`zigzag` s3 fails because of round 6.** It is a single-person scenario. The target's own rejected box
  was more than 20° from the LiDAR bearing during a fast swing, so `memory-track` latched twice. The robot
  stopped, and the view share fell to 0.745. The separation rule cannot tell the target's own box from
  another person's.
