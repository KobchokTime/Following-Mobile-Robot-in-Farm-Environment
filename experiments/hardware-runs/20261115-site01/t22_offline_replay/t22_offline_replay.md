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
