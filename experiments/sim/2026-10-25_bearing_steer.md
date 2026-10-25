# Steering by bearing instead of by image sector (twin)

- **Date:** 2026-10-25
- **Branch:** `claude/robot/bearing-steer`
- **Simulation only.**

## The change: `follow_stop` `steer_mode:=bearing`

**Default.** The default stays `sector`, the original logic.

**How it turns.**
- **Rate.** ω = 2.5 · θ̂, limited to ±0.8 rad/s.
- **Bearing.** θ̂ is the target's camera bearing (pinhole model, 70°, 640 px) plus its rate in the image
  times `latency_s`. This is where the target is now, rather than where the late frame showed it.
- **Small offsets.** Bearings under 3° give no turn.
- **LiDAR edge fixes.** When `sync_fusion` reports the image edge (cx 0 or 639), the robot turns at the
  sector rate (0.8) and the rate estimate is reset.

**Tuning found on the way.**
- **A 1.2 rad/s limit lost the target in `side_step`** (0/3). The image moved faster than the target
  gate follows. The bridge then kept the last turn command for 1 s and the robot spun past the person.
- **The jump to the image edge spoiled the rate estimate** until edge fixes were handled separately.

## Results (`mps`, seeds 0–2, one job at a time)

| Set | `sector` (current default) | `bearing` |
|---|---|---|
| Twin realism, solo | 27/30, no contact | **29/30, no contact** |
| Twin realism, identity | 15/15 | 15/15 |
| Clean twin, solo | 29/30 | 29/30 (see note) |
| Clean twin, identity | 15/15 | 15/15 |

- **Where `bearing` helps.** `zigzag` passes 3/3 with realism (`sector`: 1/3). The robot turns in
  proportion to the bearing and leads the target by the latency, instead of turning at a fixed rate.
- **What still fails.**
  - `side_step` with realism, seed 0.
  - In the clean twin, `side_step` seed 0, and `come_back` seed 2 at 0.37 m, which counts as a contact.
- **The `come_back` contact did not reproduce.** Four reruns of `come_back` seed 2 (2 × `sector`,
  2 × `bearing`) all came no closer than 0.43 m. It is ROS timing variance, not the steering.

## Recommendation

- **On robot day:** compare both modes on `zigzag` and `side_step`. Add `steer_mode:=bearing` to the
  `follow_stop` parameters; the launch file passes it through, see the cheat sheet.
- **Default:** make `bearing` the default only after Codex's review and the robot result.
