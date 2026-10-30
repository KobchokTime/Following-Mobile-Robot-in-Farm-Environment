# Following one person in Gazebo

- **Date:** 2026-10-25
- **Code:** `claude/workspace` `172e06e`, which includes the realism fixes.
- **Bridge:** `mps`.
- **Simulator:** Gazebo (Ignition Fortress), with its GPU LiDAR and walking actors.
- **Seeds:** 0, 1 and 2.
- **Simulation only.**

```bash
python3 -m sim.gazebo.run_gazebo --scenario solo --bridge-mode mps --seed N
```

**Run one Gazebo at a time.**
- A first attempt ran three containers in parallel on the 4-CPU machine, at a load of about 13.
- That run was discarded:
  - two seeds timed out;
  - the third failed almost every scenario.
- Overload slows the simulated world against the nodes' wall clock. It does not show anything about
  the robot.

## Results: 27/30

The pass rule is the same as in the twin write-ups.

| Scenario | Passed | Median gap (m) | Closest, centre to centre (m) | Top speed (m/s) |
|---|---|---|---|---|
| straight | 3/3 | 0.57 | 0.63 | 0.51 |
| stop_and_go | 3/3 | 0.57 | 0.64 | 0.51 |
| curve_left | 3/3 | 0.57 | 0.64 | 0.52 |
| target_loss | 3/3 (stops in 1.2 s) | 0.57 | 0.63 | 1.04 |
| come_back | **0/3** | 0.40 | **0.39** | 0.51 |
| side_step | 3/3 | 0.43 | 0.62 | 0.63 |
| turn_90 | 3/3 | 0.53 | 0.63 | 0.52 |
| walk_0p6 | 3/3 | 0.45 | 0.64 | 0.65 |
| walk_1p0 | 3/3 | 0.45 | 0.63 | 1.01 |
| zigzag | 3/3 | 0.57 | 0.63 | 0.58 |

## The one failing scenario: `come_back`

- **What happens.** The person walks 1.5 m back towards the robot and stops. For a moment they are
  0.39 m from the robot, centre to centre. The contact limit is 0.40 m.
- **It is the same in all three seeds**, so it is not noise. In the twin the closest approach was
  0.41–0.43 m.
- **Why.** Reversing is proportional: v = 1.5·e, plus the 1 m/s² ramp. That is slower than a person
  walking up. At the end the robot settles at a 0.40 m gap, the edge of the tolerance band.
- **Not changed yet.** In the field this is the person walking up to the robot, for example to load
  it. Whether the robot should back away faster, or let the person come close, is the author's
  decision.
  - Faster: raise the reverse gain or the bridge ramp.
  - Let them come close: leave it, and count only the robot moving towards the person as contact.

Raw summaries: `gazebo_solo_2026-10-25.json`.
