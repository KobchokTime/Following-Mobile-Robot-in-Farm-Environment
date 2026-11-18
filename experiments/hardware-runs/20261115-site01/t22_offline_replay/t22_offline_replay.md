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

## Round 7: bddb041 (2026-11-18)

The user chose all three changes for this round:
- **Walk speed.** A remembered box contradicts the LiDAR only if no one could have walked from the box to
  the LiDAR point in the time since the box. The test is d > (1.5 m/s + 0.8 rad/s × r) × age + 0.1 m,
  where d is the smallest distance over the box range and the LiDAR range. The 0.8 rad/s term allows for
  the robot's own rotation.
- **Confirmation for unranged boxes.** A box with no LiDAR range must be confirmed by a second box within
  0.5 s.
- **Logging.** The `[CONFLICT]` line now records the box's age and d.

Claude fixed two things in Codex's round:
- **Argument-order crash.** Codex inserted `age` and `distance` before `lidar_bearing` in
  `_set_camera_lidar_conflict`. The positional `edge` call then raised a TypeError, which would have
  killed `sync_fusion`. The original argument order is restored.
- **Test fixtures.** The opposite-box helper asserted the inverse of what its callers' names say, several
  clusters were too narrow for `lidar_track`, one case ran before `lidar_track_after_s`, and one
  "still blocked" case had become a feasible walk.

**Offline results:**
- `scripts/check.py` passes 276/276, and the new tests fail on ba53ed2.
- The E6 sweep gives 0/24. The robot-day event needs about 4 m/s and is still blocked. `/synced_target`
  summed over the 24 runs is 4456, the highest since round 4.
- **Auditor probes P1 and P6 now publish.** Their synthetic boxes are 0.3 s or more older than the track,
  and a person could walk that far in that time. This is the accepted cost of the walk-speed rule.
  P2, P2b and P5 still fail closed, and P4 remains a known limit.

**Full twin (run 44339360033): 108/110 on the baseline set, 0 contacts, 108/115 overall.** All three
PR CI jobs pass.

| Code | Baseline set | Runs with `[CONFLICT]` | `blind_corner` | `zigzag` | `pass_by` |
| --- | --- | --- | --- | --- | --- |
| 6a64669 (baseline) | 106/110 | — | 1/5 | 5/5 | 5/5 |
| 05bb929 | 107/110 | — | 2/5 | 5/5 | 5/5 |
| b6d1862 | 106/110 | — | 2/5 | 5/5 | 4/5 |
| 2105e58 | 104/110 | 94/115 | 0/5 | 4/5 | 5/5 |
| ba53ed2 | 104/110 | 5/115 | 0/5 | 4/5 | 5/5 |
| **bddb041** | **108/110** | **2/115** | **3/5** | **5/5** | **5/5** |

- **T22 twin criterion met** (at least 106/110 with 0 contacts).
- **The only latches** are in `fast_side_step_left`, s0 and s3. That scenario still fails 0/5 because of
  the clutter in its path, as on every commit.
- **`blind_corner`:** s1 and s2 fail with no latch, at view shares of 0.845 and 0.886 against the 0.9 rule.
  That is the same near-miss this recorded failure has shown before.

## Independent safety audit of rounds 5–7 (bddb041, 2026-11-18)

**Verdict:**
- **bddb041 as the T22 fix:** block.
- **Robot motion:** NO-GO.
- **Read-only hardware run with the drive physically disabled:** nothing in this code stands in its way.
  This is not an authorisation.

Claude reran the auditor's drop-one-frame replay (`audit_tools/replay_drop.py`) and confirmed finding 1.

1. **High. One missed detection brings T22 back.** The walk-speed rule makes the memory a timer. Once
   the person has left the image on the far side, no new box arrives, so `age` only grows. After about
   (d − 0.1)/(1.5 + 0.8r) seconds, any far-side edge track can publish; for the robot-day geometry that
   is 0.345 s. The track in the bag ran at an age of 0.218 s, so the margin is 0.127 s, about one
   camera frame: the bag's box cadence is about 7 Hz, with a median gap of 0.143 s.

   The test drops only the last box (587.757 s) and replays the E6 bag:

   | Timing (delay, phase) | bddb041 | b6d1862 |
   | --- | --- | --- |
   | d20 p75 | wrong turn at 588.0 s | stopped |
   | d15 p70 | wrong turn at 587.99 s | stopped |
   | d0 p0 | stopped | stopped |

   On the auditor's 420-timing sweep with the last box dropped, bddb041 fails 4 timings and b6d1862 none.
2. **Medium, fails open. The P1 case is open again as short turns.** The smallest box age at which an
   edge track publishes:
   - person straight ahead (−2° at 0.95 m) with the track at −31°: 0.17 s while turning, 0.255 s while
     still;
   - the T22 boxes: 0.20–0.33 s.

   About 17% of box gaps are longer than 0.17 s. Each such gap leaks a turn of about 0.2–0.5 s (10–23°).
3. **Medium. The constant turn allowance.** The 0.8 rad/s term shortens the detection window by 25–50%
   while the robot is actually still. It should come from measured yaw (odometry, or bearings rotated by
   the integrated yaw) before any motion test. Removing the term passes every test.
4. **Medium, fails open. Background-ranged boxes are dropped.** A box with range > pr + 1.5 m is never
   remembered, not even as an unranged box. The target's own side-step boxes read 2.85 m against a
   prediction of 1.0 m. They should be recorded as unranged instead.
5. **Medium. The two-frame rule for unranged boxes.** A real person with no range, seen once at the
   image edge, is ignored, which fails open. A phantom seen twice confirms itself, which costs
   availability only.
6. **Medium. Assist can drag the gate again.** Since round 6, the assist moves the gate onto the drifting
   cluster; only publication is guarded, and only inside the walk window. A box that matches the dragged
   prediction can then be accepted, which clears the latch.
7. **Low.** The `memory-track` log line prints the prediction, not the cluster bearing that was tested.
   No crash path was found.

**Test quality.** Mutation testing caught 13 of 16 mutants. Three changes went uncaught: removing the
turn term, removing the separation rule, and dropping the box range from d.

**Evidence.** A single bag passing with a 0.127 s margin does not support "T22 fixed offline". The twin
cannot exercise T22 either: `fast_side_step_left` is 0/5 on every commit, and 113 of 115 runs never latch.

**Before a read-only hardware run:**
- add a drop-one-frame replay case and a measured-cadence test;
- log the cluster bearing;
- record `/target_centroid_sector`, `/scan`, `/cmd_vel` and odom yaw.

## Round 8: 18ec4bc (2026-11-19)

The user chose to make the newest box never age:
- **Newest box blocks at any age.** The newest remembered in-image box since the last fix blocks a LiDAR
  bearing on the separation rule alone, at any age within `lidar_track_max_s`. Older boxes keep both the
  separation rule and the walk rule.
- **Background-ranged boxes.** These are now remembered as unranged instead of being dropped.
- **Assist.** The assist skips a cluster that the newest box contradicts. It neither moves the gate nor
  latches.
- **Logging.** `[CONFLICT]` logs the bearing that was tested, plus `newest=1/0`.

Claude corrected five test fixtures. One of them had flipped a 24° newest-box case to expect a
publication.

**Offline results:**
- `scripts/check.py` passes 282/282.
- The missed-frame tests, with one or two boxes missing, fail on bddb041.
- The auditor's probes P1, P2, P2b, P5 and P6 fail closed again. P4 remains a known limit.

**E6 bag replay:**

| Replay | bddb041 | **18ec4bc** |
| --- | --- | --- |
| 24 timings | 0 | 0 |
| 420 timings (delay 0–100 ms, phase 0–95 ms) | 0 | **0** (`/synced_target` total 78091) |
| Last box dropped, 420 timings | **4** | **0** (77640) |
| Last box dropped, the 4 failing timings | 4 | 0 |
| Last two boxes dropped, 5 timings | — | 0 |

The rows are in `fine_sweep_18ec4bc_nodrop.json` and `fine_sweep_18ec4bc_drop1.json`.

**Full twin (run 44352152144): 106/110 on the baseline set, 0 contacts, 106/115 overall.** All three PR
CI jobs pass.

| Code | Baseline set | Runs with `[CONFLICT]` | `blind_corner` | `pass_by` |
| --- | --- | --- | --- | --- |
| 6a64669 (baseline) | 106/110 | — | 1/5 | 5/5 |
| 05bb929 | 107/110 | — | 2/5 | 5/5 |
| bddb041 | 108/110 | 2/115 | 3/5 | 5/5 |
| **18ec4bc** | **106/110** | **1/115** | 1/5 | 5/5 |

- **T22 twin criterion met** (at least 106/110 with 0 contacts).
- **Every failure in the baseline set is `blind_corner`,** and none of those runs latched. s0 and s1
  reached view shares of 0.897 and 0.893, just under the 0.9 rule. s3 and s4 lost the target, as in
  earlier rounds. This is the scenario's usual variation between runs, not an effect of round 8.
- **The only latch** is in `fast_side_step_left` s1.

## Independent safety audit of round 8 (18ec4bc, 2026-11-19)

**Verdict:**
- **18ec4bc:** approve with changes, offline only.
- **Robot motion:** NO-GO.
- **Read-only hardware run with the drive disabled:** nothing in the code stands in its way. This is not
  an authorisation.

Round 8 closes the earlier audit's findings 1, 2, 4 and 7 against the robot-day evidence. The auditor's
fine sweeps (420 timings each) give 0 wrong turns with no boxes dropped and with the last one or the last
two dropped. Claude reran the auditor's `r8_probe.py` and confirmed finding 1.

1. **High, a new fail-open path.** A newer box near the drifted track demotes the real contradiction.
   - **Mechanism:** `newest_time` is taken over all remembered boxes, before the image and separation
     filters (`sync_fusion_node.py:788`). A newer rejected box within 20° of the LiDAR cluster
     therefore becomes "newest" and is then skipped. That box may be a false positive, a bystander the
     track drifted onto, or the target's own box at +10°. The real contradicting box then falls back to
     the walk timer.
   - **Probes:** the robot-day boxes plus a box at +22° (ranged at 1.6 m, or unranged) publish the far
     edge 0.195 s later. With the extra box in the same frame, the result depends on message order:
     after the real box, it publishes at 0.345 s; before it, the track stays blocked.
   - **Fix, checked by the auditor (mutation q6):** take the newest only over boxes that contradict,
     meaning boxes in the image and more than the separation away. This blocks every probe. One test,
     `test_older_box_uses_turn_allowance_but_still_requires_separation`, relies on the demotion and has to
     be rewritten.
2. **Medium. Three missed detections reopen T22.** This is known limit P4, now measured. With the boxes in
   587.38–587.80 s dropped, 2 of 420 timings turn the wrong way (d55 p85 and d60 p90). The −6.9° box is
   accepted and clears the memory, and nothing contradicts the track after that. A possible guard: refuse
   an edge track more than the separation away from the last accepted camera bearing, with the covered
   branch exempt. Its cost in `blind_corner` would have to be measured. Gaps over 0.4 s are under 1% of
   box gaps in the bag.
3. **Medium, availability (fails closed).** A stop can last about 61 s, until the person re-enters the lock
   window (0.5–1.0 m, ±15°). The first command after recovery is the existing give-way reverse at
   −0.75 m/s. The operator has to be able to see `[CONFLICT]`, the recovery has to be documented, and the
   reverse has to be reviewed before motion.
4. **Low-medium.** The assist uses the full rule, so it over-skips when a bystander is on the other side.
   That costs availability only. The q6 fix also closes the remaining assist drag.
5. **Low.** An isolated unranged newest box is skipped, after which older boxes age as usual. The turn
   allowance is still a constant, though it now applies only to older boxes.

No crash paths were found. The mutation tests caught q1, q2, q3, q4, q5, q8 and q9; q7 survived (low
impact).

**What the evidence supports:** the T22 wrong turn is not reproduced offline on the E6 bag with up to two
missed frames (0 of 420 timings). It does not cover three missed frames, or a second person or false
positive near the drifted track.

## Round 9: 33d4a0e (2026-11-19, applied by Claude at the user's request)

**Change.** This is the auditor's mutation q6. `newest_time` is now taken only over boxes that
contradict the tested bearing: boxes in the image and more than `lidar_conflict_sep_deg` away. The
older-box walk rule now matters only when the newest contradicting box is skipped, which happens when it
is an unconfirmed unranged box.

**Tests.**
- `test_older_box_uses_turn_allowance_but_still_requires_separation` is rewritten for the new rule.
- The new test `test_newer_box_near_the_drifted_track_does_not_demote_the_real_contradiction` has five
  cases. Four of them fail on 18ec4bc. The fifth, a same-frame box arriving before the real one, already
  passed.
- `scripts/check.py` passes 283/283.

**Probes.** Every probe from the auditor's `r8_probe.py` is now blocked, except a single unconfirmed
unranged box or a single background box with nothing before it (finding 5, a known low limit).
P1, P2, P2b, P5 and P6 fail closed. P4 remains a known limit.

**E6 bag, 420 timings each** (delay 0–100 ms, phase 0–95 ms):

| Boxes dropped | 18ec4bc (auditor) | **33d4a0e** | `/synced_target` total, 33d4a0e |
| --- | --- | --- | --- |
| none | 0 | **0** | 79379 |
| last one (587.70–587.80) | 0 | **0** | 78928 |
| last two (587.55–587.80) | 0 | **0** | 78408 |
| last three (587.38–587.80) | **2** (d55 p85, d60 p90) | **0** | 76902 |

The two three-drop timings were rerun with Claude's copy of the harness. 18ec4bc turned the wrong way at
588.01 s in both; 33d4a0e did not. Why q6 also closes the three-drop case has not been analysed. It is
probably because the assist uses the same function and so no longer moves the gate toward the drifting
cluster. This needs a probe before it is relied on. The rows are in
`fine_sweep_33d4a0e_{nodrop,drop1,drop2,drop3}.json`.

**Full twin (run 44368013150): 107/110 on the baseline set, 0 contacts, 107/115 overall.** All three PR
CI jobs pass.
- Every failure is in `blind_corner` (s1, s3 and s4 lost the target). Latches appeared in four runs:
  - the round-3 `edge` rule in `blind_corner` s1 and s4, and in `side_step` s0;
  - `memory-track` in `side_step` s1.

  Both `side_step` runs passed.
- `fast_side_step_left` is 0/5, the clutter-path issue, as on every commit.

| Code | Baseline set | `blind_corner` |
| --- | --- | --- |
| 6a64669 | 106/110 | 1/5 |
| 18ec4bc | 106/110 | 1/5 |
| **33d4a0e** | **107/110** | 2/5 |

**Still open from the audit:**
- **Before a read-only hardware run:** make `[CONFLICT]` visible to the operator, and document the
  recovery. The recovery is to step back into 0.5–1.0 m, centred; until then a stop can last about 61 s.
- **Before any motion test:**
  - measured yaw in place of the constant turn allowance;
  - a decision on the last-accepted-bearing guard (finding 2);
  - a review of the −0.75 m/s reverse after a re-lock;
  - a read-only run with a person side-stepping and leaving the image;
  - the full motion gate.
