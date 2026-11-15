# Static-object filter for LiDAR tracking (twin)

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

## Update: the first result was a bug (`08eb36b`)

- **The bug.** Drawing the point-cloud maps showed that `StaticMap` kept integrating the last
  `/cmd_vel` after `follow_stop` went quiet, while the bridge had stopped the wheels after 1 s.
  - The pose drifted metres away, so the followed person and the walls looked like they were moving
    or static at random.
  - It now ignores commands older than 1 s.
- **Re-run.** Same image, one job at a time, `mps`, seeds 0–2. Filter off and on were both re-run.

| Set | Filter off | Filter on |
|---|---|---|
| `side_step_bush`, clean twin | 1/3 | **3/3** |
| `side_step_bush`, realism, `sector` | 2/3 | **3/3** |
| `side_step_bush`, realism, `bearing` | 2/3 | **3/3** |
| All 10 solo moves, realism, `sector` | 26/30, no contact | 25/30, 3 contacts |

- **The off-filter failures in `side_step_bush`.** The robot lost the target near the bush and stopped
  0.8–1.4 m from it. It never drove into the bush.
- **The 3 contacts with the filter on are not the filter.**
  - Two re-runs each of `walk_1p0` seeds 0 and 2 came no closer than 0.52 m.
  - Five more `walk_1p0` seeds (3–7) pass 5/5 with the filter on and off alike (closest 0.58 m).
  - `come_back` seed 1 touched again in 1 of 2 re-runs. That is the known `come_back` question, and it
    also happens with the filter off (0.355 m in integration's run).
- **Scan matching would be better than dead reckoning.**
  - The dashboard's point-cloud maps compare three pose sources: dead reckoning from `/cmd_vel`, 2D
    ICP against a keyframe refreshed every second (as in the paper), and the true pose.
  - Over every run, ICP ends within 0.02–0.12 m of the true pose. Dead reckoning ends within
    0.06–1.16 m.
  - The ICP runs offline on rebuilt scans in a field with walls. It has not been tried in the node.

## Conclusion (updated)

- **Promising, still off by default.** With the fix the filter fixes `side_step_bush` (9/9 against
  5/9) and does not make the solo set worse beyond run-to-run variance.
- **Before turning it on:**
  - a review (Codex);
  - a robot-day check;
  - preferably real ego-motion: ZLAC wheel feedback or ICP in `StaticMap`.

## Update 2: ICP pose in the node (`4e365a9`, `c14fb1f`, `1e802dc`)

- **What changed on `claude/robot/static-filter`:**
  - `static_pose:=icp` (the default when the filter is on) corrects `StaticMap`'s pose with 2D
    point-to-point ICP against a keyframe refreshed every second. The `/cmd_vel` pose is the initial
    guess and the fallback when fewer than 40 points match.
  - The twin gains LiDAR-only walls and `side_step_rows`: `side_step_bush` between two crop-row walls.
  - Every 2 s `sync_fusion` logs the filter's pose, ICP matches and failures, and how many clusters it
    kept from LiDAR tracking as static (`[STATIC]`).
- **All runs:** `mps`, `steer_mode:=bearing`, one job at a time. The pose error compares the logged pose
  with the twin's true pose.

### First run: ICP matched the walking person (`4e365a9`, seeds 0–4)

| Set | Off | `/cmd_vel` pose | ICP pose | ICP pose error at the end |
|---|---|---|---|---|
| `side_step_rows`, clean | 4/5 | 3/5 | 4/5 | 0.07–0.11 m |
| `side_step_rows`, realism | 5/5 | 4/5 | 4/5 | 0.07–0.18 m (`/cmd_vel`: 0.20–1.62 m) |
| `side_step_bush`, clean | 4/5 | 5/5 | 4/5 | **1.3–3.5 m, 66–110°** |
| `side_step_bush`, realism | 3/5 | 3/5 | 5/5 | 0.65–0.99 m |

- **With walls ICP is accurate** and never fell back to the guess.
- **With only one bush and the target in range, ICP locked onto the walking person** and the pose
  followed them.
- **Fix (`c14fb1f`):**
  - A person-sized cluster (0.15–0.8 m) enters the keyframe only after `StaticMap` calls it static.
  - Walls and rows always count. Their cluster position shifts as the robot drives past, so
    `StaticMap` cannot vouch for them.
  - With too little left, ICP fails and the guess is kept.

### After the fix (`c14fb1f` + `1e802dc`, seeds 0–4, each run twice)

| Set | Off | ICP | ICP failed (kept the guess) | ICP pose error, median of the run maxima (worst) |
|---|---|---|---|---|
| `side_step_rows`, clean | 9/10 | 6/10 | 0% | 0.34 m (0.69) |
| `side_step_rows`, realism | 4/10 | 5/10 | 0% | 0.07 m (0.38) |
| `side_step_bush`, clean | 9/10 | 10/10 | 54% | 0.19 m (0.75) |
| `side_step_bush`, realism | 5/10 | 6/10 | 28% | 0.41 m (0.60) |
| **Total** | **27/40** | **27/40** | | |

- **No contact in any run.**
- **Regression (`c14fb1f`, realism, `bearing`, seeds 0–2):**
  - solo: 28/30, against 30/30 with the filter off in `2026-10-25_bearing_steer.md`;
  - identity: 15/15;
  - the two solo failures are `come_back` seed 2 (contact, closest 0.40 m, the known `come_back`
    question) and `side_step` seed 2 (target lost).
- **The bush no longer drags the pose away**, but the fallback is used for half the scans there.
- **In the clean rows the pose got worse than before the fix** (median 0.34 m against 0.07–0.11 m).
  The likely cause, not checked: parts of a wall cut by occlusion look person-sized and are dropped.
- **The runs are too random to separate the filter's effect.**
  - The same seed passed in one repeat and failed in the other in 1–4 of 5 seeds, in every set but
    ICP in the clean bush.
  - Every failure, filter on or off, is the same: the target is lost when it steps out of view
    (target visible about 20% of the run).
- **The diagnostic log gives a hint, not proof.** ICP runs that lost the target dropped somewhat more
  clusters as static than runs that passed: 1–13 against 1–3 in the bush with realism, and up to 49
  in one rows run. A dropped cluster may be the target.

## Conclusion (update 2)

- **Keep the filter off.** In the twin it gives no measurable gain: 27/40 both ways.
- **ICP is a good pose source where there is fixed structure** (walls: 0.07 m against up to 1.6 m for
  `/cmd_vel` with slip), and a poor one in an open field.
- **For the thesis:** a tried-and-measured extension. The paper's idea needs both wheel odometry and
  enough fixed structure. Report it as future work together with ZLAC wheel feedback as the ICP guess.
- **Data:** dashboard v2, filter tab ("รอบล่าสุด" card, dataset `icp_trial_runs`).
