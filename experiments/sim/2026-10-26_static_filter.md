# Static-object filter for LiDAR tracking (twin): tried, not adopted

- **Date:** 2026-10-26
- **Code:** branch `claude/robot/static-filter` (`70ed63b` and the obstacle fix after it). It is **not merged**. In that
  branch `static_filter` defaults to off.
- **Idea.** The dynamic non-target detector in *Multi-modal Bayesian Learning, Re-identification and
  Tracking of a Target Person for Mobile Robots*, Figure 5:
  - register 2D scans over a time window;
  - points that match are static, points that don't are moving;
  - segment the moving points and give only those to the tracker.
- **Simulation only.**

## What was built

- **`sync_fusion` `StaticMap`:**
  - it integrates the robot pose from `/cmd_vel`, because the robot has no odometry;
  - it keeps LiDAR clusters in that frame;
  - a cluster that stays within 0.3 m of where it was first seen for 2 s is static;
  - LiDAR edge tracking skips static clusters.
- **Twin:**
  - static `obstacles` in a scenario: the LiDAR sees them, the camera ignores them;
  - a `side_step_bush` scenario: `side_step` with a person-sized bush at (2.2, 1.6), beside where the
    target leaves the view. It is not part of the solo set.

## Results (`side_step_bush`, `mps`, seeds 0–2, one job at a time)

| Set | Filter off | Filter on |
|---|---|---|
| Clean twin, `sector` | **3/3** | 1/3 (target visible 0.87) |
| Realism, `bearing` | 2/3 | 2/3 |
| Realism, `sector` | 2/3 | 1/3 |

- **Without the filter the robot never went after the bush.** Its closest approach to the bush is
  0.72–1.1 m. The existing gate (person-sized clusters only, ±25° and ±0.5 m around the prediction)
  already keeps the bush out.
- **The failures without the filter are the known steering weakness.** In realism `sector` seed 1
  the target was still in view at 14–19° when the robot stopped turning.
- **The filter made the clean twin worse.** The likely cause, not yet confirmed from the logs, is
  odometry:
  - the pose comes from the *commanded* velocity, while the wheels ramp and (with realism) slip;
  - a person followed at a steady gap barely moves in the robot frame;
  - with an odometry error they can look static in the "world" frame and be filtered out.

## Conclusion

- **Not adopted.** The current gate already handles this bush. The filter as built removes the
  target in some runs.
- **To work it needs real ego-motion:** wheel speeds from the ZLAC8015D feedback, or scan
  registration (ICP) as in the paper.
- **For the thesis:** related work (chapter 2) and future work. The problem the paper's detector
  solves is real for a cluttered farm, but it needs odometry this robot does not have yet.
