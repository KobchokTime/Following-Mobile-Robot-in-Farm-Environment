# Following one person with a less perfect twin

- **Date:** 2026-10-25
- **Branch:** `claude/research/twin-realism`
- **Goal:** the solo set passed 30/30 in a twin with perfect sensors. Before robot day, check how the
  same code behaves when the sensors and wheels are imperfect. **Simulation only.**

## The realism profile (`--realism`)

`sim/twin/world.py` `Realism`. It is off by default: old runs stay bit-identical, which was checked by
hashing every Arena 2 scenario. The profile adds:

| What | Value | Why |
|---|---|---|
| Detection latency | 0.15 s, so a frame arrives 0.2 s late at 10 Hz | camera + YOLO on the UP Board (E2 measures the real value) |
| Missed detections | 10% of frames | YOLO misses a person now and then |
| False positives | 3% of frames, one box anywhere | spurious boxes |
| Extra LiDAR noise | 0.03 m | on top of the default 0.03 m |
| LiDAR ray dropout | 2% | rays that return nothing |
| Wheel slip | 5% per wheel (std) | grass and soil |
| Clutter | 8 thin posts and 3 bushes beside the path | farm rows |

Run it with `python3 -m sim.twin.run_scenario --scenario solo --bridge-mode mps --realism --seed N`.

## Pass rule

Same as `2026-10-24_solo_following.md`. A run passes when:
- the target is in the camera's view at the end;
- the final gap is at most 1.5 m;
- there is no contact (closest approach under 0.4 m, centre to centre);
- the target was visible for at least 90% of the run.

## Results (seeds 0, 1 and 2)

| Code | Solo (10 × 3) | Identity (5 × 3) | Contact |
|---|---|---|---|
| Before (hub code) | 19/30 | 13/15 | 0 |
| Fixes 1–2 | 22/30 | 15/15 | 2 (0.38 m and 0.39 m) |
| **Fixes 1–5** | **27/30** | **15/15** | **0** |
| Fixes 1–5, clean twin (no realism) | 29/30 | 15/15 | 0 |

- **Clean-twin failure:** `side_step` seed 1, under the load of 6 runs at once. It passed on 2 reruns.
- **Clean repeats:** `side_step` and `zigzag`, seeds 1–3, pass 6/6.
- **Still failing with realism:** `zigzag` seeds 0 and 2, and `side_step` seed 0.

## What realism found, and the fixes (robot code)

1. **Two boxes on one person lost the target for good (`TargetGate`).**
   - The detector publishes one message per box. A second box on the same person arrives about 1 ms
     after the first.
   - The alpha-beta filter divided by that 1 ms, so the bearing rate jumped to about 10 rad/s.
   - Every later prediction was then far off, the gate never accepted the target again, and the
     pipeline went silent.
   - YOLO produces duplicate boxes on real images too.
   - **Fix:** steps shorter than 0.05 s update the position only (`min_rate_dt`).
   - **Test:** `test_two_boxes_in_one_frame_do_not_lose_the_target` (it fails on the old code).
2. **A false box over the target made the robot back away (give-way).**
   - The box took the target's own LiDAR range, so the code saw "someone in the path, nearer than the
     target". It then treated them as 0.4 m nearer still, and the robot reversed.
   - **Fix:** only someone at least `path_min_gap_m` (0.2 m) nearer than the target counts as being in
     the way. Two bodies in line are at least about 0.4 m apart.
3. **After a long loss the gate accepted almost anything.**
   - Its gates widen 1×/s with no limit. After 7 s unseen, a false box in front of a post 3.5 m away
     was accepted.
   - The robot then drove at 1.4 m/s into the post.
   - **Fix:** after 5 s with no fix the gate unlocks and only locks again in the start window
     (0.5–1.0 m, ±15°), as the controller does. You walk back to the robot to resume.
   - **Test:** `test_long_loss_returns_to_the_lock_on_window`.
4. **Latency in the braking cap (`follow_stop`).**
   - The gap in each message is 0.2 s old, and at 1.1 m/s the robot has closed 0.2 m since.
   - Two runs ended 1–2 cm inside the contact limit.
   - **Fix:** the √(2·a·gap) cap now uses the gap minus `prev_linear × latency_s`, with `latency_s`
     0.2.
   - **Test:** `test_braking_allows_for_the_gap_closed_during_latency`.
5. **Edge exit seen late.**
   - Frames arrive 0.2 s late, so a person stepping out fast is last seen mid-image, and the LiDAR
     tracking (which only starts after an edge exit) never started.
   - **Fix:** the edge test also uses the gate's predicted bearing. A target that is moving fast enough
     to be past the edge by now counts as an edge exit.
   - A target that vanishes mid-image while standing or walking straight still stops the robot.
     `target_loss` still stops in 1.2 s.

## Remaining limits

- **`zigzag` with realism.**
  - The person weaves ±0.6 m within 1 m of the robot, so the bearing swings at about 100°/s.
  - The controller turns at a fixed 0.6 or 0.8 rad/s, chosen by image sector, and with 0.2 s latency it
    sometimes turns the wrong way and loses the person.
  - A proportional bearing controller, or turning by the gate's predicted bearing, would help. That is
    a bigger change to `follow_stop` and is left for after robot day: the real latency (E2) decides
    how much it matters.
- **`side_step` seed 0 with realism.** Same cause: an overshoot after the turn back.
- **Run-to-run variance.** Runs are not bit-identical across repeats, because of ROS timing with 6
  containers in parallel. Single failures should be rerun before drawing conclusions.
- **`latency_s` is a guess.** Set it from E2 on robot day.

Raw data: `twin_realism_2026-10-25.json` (summaries for every run above).
