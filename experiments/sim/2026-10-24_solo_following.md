# Following one person at walking pace (twin)

- **Date:** 2026-10-24
- **Branch:** `claude/research/solo-following`
- **Goal:** the user works alone, so the first target is following **one person** reliably, at
  realistic walking speeds. **Simulation only.**

## New single-person scenarios (`SOLO_SCENARIOS`, set `solo`)

| Scenario | The person… |
|---|---|
| `walk_0p6`, `walk_1p0` | walks straight at 0.6 m/s and 1.0 m/s. The older scenarios walk at only 0.3 m/s. |
| `turn_90` | turns at a right angle. |
| `come_back` | walks away, then comes 1.5 m back towards the robot (to load it). |
| `side_step` | steps 1 m sideways, which takes them out of the camera's view at this range, then walks on. |
| `zigzag` | weaves ±0.6 m. |

The `solo` set also includes `straight`, `stop_and_go`, `curve_left` and `target_loss`.
`ALL_SCENARIOS` is unchanged (the frozen Arena 3 scorer checks runs against it).

## Before: current hub code, old bridge (`fixed`, seed 0)

5 of 10 pass: `straight`, `stop_and_go`, `curve_left`, `target_loss` and `zigzag`. The failures
(corrected after the integration review):

| Scenario | Result |
|---|---|
| `walk_0p6` | target pulls away to 3.2 m (target visible 64%) |
| `walk_1p0` | target pulls away to 5.8 m (target visible 39%) |
| `turn_90` | loses the target (final 2.7 m) |
| `side_step` | target visible only 72% |
| `come_back` | contact. This run used the first version of the scenario, where the person walked back *through* the robot, so it is not comparable with the corrected scenario. |

The root cause of the speed failures is the bridge. It caps each wheel at 40 RPM, about 0.36 m/s
with the assumed 0.085 m wheel, and a person walks at 1.0–1.4 m/s.

## Changes (the user decided to lift the speed cap)

1. **`zlac_joystick_bridge.py`, `speed_mode` "mps" (default).**
   - `/cmd_vel` is m/s and rad/s, and is turned into RPM with `wheel_radius_m`.
   - Each wheel is capped at `max_speed_mps` (1.4) and ramped at `max_accel_mps2` (1.0).
   - `speed_mode:=legacy` keeps the old mapping.
   - The twin and Gazebo have the same mode, `--bridge-mode mps`, including the ramp.
2. **`follow_stop_node.py`, `max_decel` (0.8).** The forward speed is capped at what can still stop
   within the gap, √(2·a·error). At 1.4 m/s with a 1.0 m/s² ramp the robot needs about 1 m to stop.
   Without this cap it ran into a person who stopped.
3. **`sync_fusion_node.py`, LiDAR tracking out of view.**
   - **When it runs:** the target leaves the image **at its edge**, meaning within 8° of the ±35°
     limit.
   - **What it does:** the LiDAR keeps the target near its predicted bearing and range (±25°,
     ±0.5 m) for up to 5 s, and the robot turns towards that side at full turn rate.
   - **What it doesn't do:** if the target vanishes mid-image, the detector failed, so the robot stops
     as before. `target_loss` still stops in 1.2–1.3 s.
4. **`come_back` made realistic.** The person comes back 1.5 m and stands, instead of walking through
   the robot.

## Results: new code, `mps` bridge, seeds 0, 1 and 2

**Solo set: 30/30 pass.** Mean of the median gaps, worst values across seeds:

| Scenario | Median gap | Max gap | Closest | Visible | Top speed |
|---|---|---|---|---|---|
| straight | 0.55 | 0.80 | 0.63 | 1.00 | 0.50 m/s |
| stop_and_go | 0.55 | 0.80 | 0.62 | 1.00 | 0.50 |
| curve_left | 0.55 | 0.80 | 0.61 | 1.00 | 0.50 |
| target_loss | 0.55 | 1.51 | 0.62 | 1.00 | 1.10 (stops in 1.2–1.3 s) |
| come_back | 0.45 | 0.80 | 0.43 | 1.00 | 0.58 |
| side_step | 0.42 | 1.80 | 0.61 | 0.94 | 1.25 |
| turn_90 | 0.54 | 0.80 | 0.61 | 1.00 | 0.53 |
| walk_0p6 | 0.46 | 0.88 | 0.57 | 1.00 | 0.78 |
| walk_1p0 | 0.45 | 1.35 | 0.53 | 1.00 | 1.18 |
| zigzag | 0.53 | 0.80 | 0.61 | 1.00 | 0.67 |

Gaps are surface to surface, in metres. "Closest" is centre to centre to the person; contact is
below 0.4 m.

**Identity set on `mps`:** 15/15 pass (5 scenarios × 3 seeds).

## Regression check on the old bridges

- **Arena 3 protocol, twin on `fixed` and `diff_drive`, seeds 0–2, scored with the judged Gazebo
  runs:** 95.72, against the judged 99.13. Identity is still 21/21 and behaviour 20. Only lag drops:
  the median gap rises to 0.73–0.90 m.
- **Cause:** `max_decel` is in m/s², but on the legacy bridge one unit of `/cmd_vel` is about
  0.36 m/s, so the cap brakes far too early.
- **With `max_decel:=0.0`** the legacy bridge gives the old gaps back: 0.58 / 0.55 / 0.58 m.
- **Rule:** with `speed_mode:=legacy`, also set `max_decel:=0.0`. The real robot now defaults to "mps".

## Limits

- Everything depends on the **real wheel radius**: speed errors scale with it. On robot day run
  `speed_check.py` before following above 0.5 m/s (see `docs/robot_day_protocol.md`).
- The twin has no wheel slip, no motor limit beyond the ramp, and a perfect LiDAR. LiDAR tracking out
  of view assumes nothing else stands near the predicted spot. With a second person nearby that has
  not been tested, apart from the identity set (15/15).
- Following faster than 1.4 m/s is impossible by design (`max_speed_mps`).

Raw summaries: `solo_following_2026-10-24.json`.
