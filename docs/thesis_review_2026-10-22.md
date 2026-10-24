# Thesis draft review: methods under attack, and the revised experiments

- **Draft:** *Development of a Person-Following Robot for Farm Transport Using Real-Time Visual
  Processing and Wireless Control in Outdoor Environments* (unrevised; the cover still says 2023).
- **Review:** Claude Code, 2026-10-22.
- **Checked against:** the code on `integration-hub` and the offline twin (`sim/`).

Each point gives the thesis claim, why it does not hold, the evidence, and the fix or experiment that
would make it hold. **Nothing here was measured on the robot.** Numbers marked *twin* come from
simulation.

## Summary

The draft's ideas are sound: angular sectors, YOLO plus 2D LiDAR fusion, a confidence score, and
clothing colour in YCbCr. The **evidence** for them is weak, and the **code** does something else.

1. The two validation numbers in chapter 4 cannot detect the failures they are meant to rule out.
   - Pearson r > 0.95 between `c_x` and the sector ID is true by construction.
   - The "4–6 ms" offset is callback timing, not sensor timing.
2. The "Bayesian tracking module" in chapter 3 does not exist in the code. The node with that role
   is a weighted average with smoothing, and it cannot detect a wrong person.
3. Nothing selects **which** person to follow. Every detection is sent to the controller. In the
   twin, a second person beside the target makes the robot run into the target, then follow the
   other person.
4. The colour analysis shows only the target, so it says nothing about telling two people apart.
5. Chapter 4 has no following results: no gap error, no ID-switch count, no success rate.
   Objectives 3–4 and problem statement 3 (multiple people) have no evidence. Chapter 5 is empty.

## A. Sensor alignment

### A1. "Pearson r > 0.95 between `c_x` and sector ID" (4.2, 4.4.2) is circular

- **Why it fails.** `sector_id = floor(c_x × 9 / W)` (`ros2_yolo_live.py`, `compute_sector_id`).
  Any step function of `c_x` correlates with `c_x`; random `c_x` gives r = 0.994. The number
  measures the formula, not the camera or the LiDAR.
- **Evidence it misses real faults.** The twin (2026-10-20, finding 1) found that the camera
  sector index and the LiDAR sector index ran in **opposite directions** with different widths. The
  robot could not turn. That code had the same r > 0.95.
- **Fix: experiment E1.** Measure bearing error against ground truth instead.

### A2. "ρ(θ_cam, θ_lidar) ≈ 0.95" (3.3.5) cannot see offset or scale errors

- A 10° mounting offset, or a 2× scale error, still gives r = 1.0. Correlation is the wrong
  statistic for agreement.
- **Fix.** Report mean absolute error and bias (Bland–Altman) in degrees, and the share of frames
  where the chosen LiDAR return is actually the person (E1).

### A3. "dt ≈ 4–6 ms" (3.3.4, 4.4.1) is not sensor synchronisation

- `sync_fusion_node.py` stamps both streams with the **time it receives them** (`now_sec()`).
  `/target_centroid_sector` is an `Int32MultiArray`, which has no header, so the camera capture
  time is lost before fusion.
- If the two streams were independent, the nearest 12 Hz scan would be on average about 21 ms away
  (up to 42 ms). A tight 4–6 ms cluster points to callback scheduling, not alignment.
- The latency that matters is from camera capture, through YOLO on the UP Board, to `/cmd_vel`.
  It was not measured. `Check Hz/Check_Hz.py` already notes that the YOLO publisher should carry
  `header.stamp`.
- **Fix: E2.** Stamp detections with the image header and measure capture → `/cmd_vel`.

## B. Tracking and identity

### B1. The "Bayesian Tracking Module" (3.3.5) is not what runs

`Image/fusion_prob_node.py`, the node in that slot, computes:

1. `P_C = exp(−center_penalty·dx²)`. The penalty defaults to 0, so `P_C` is always 1.
2. `P_L = 1 − d / 2 m`. A **closer** person gets **higher** confidence.
3. `P_obs = 0.7·P_C + 0.3·P_L`, so `P_obs` is at least 0.7 whenever any detection arrives.
4. Exponential smoothing with the previous value.

There is no colour, no size, no motion and no Bayes rule. Since `P_obs ≥ 0.7` is above the 0.6
stop threshold, the confidence **cannot** fall because the wrong person is seen. It falls only when
detections stop. Either the code must implement the model, or the thesis must describe the code.

### B2. The model as written would be overconfident

- **No transition model.** With `P(T_t) = C_{t−1}`, a few consistent frames push C to about 1,
  and a wrong person then needs many frames to pull it down. A standard fix is a switch
  probability ε: `P(T_t) = (1−ε)·C_{t−1} + ε·(1−C_{t−1})`.
- **The independence assumption is false for these features.** Box size and LiDAR distance are
  physically coupled (box height ∝ 1/d). Multiplying their likelihoods counts the same evidence
  twice.
- **No likelihoods are given.** There is no distribution, no σ, and no data they were fitted to.
  The model cannot be reproduced.

### B3. It is a confidence for one hypothesis, not data association (the main gap)

- With N people in view, the thesis needs to score **each** detection against the target and pick
  one, using gating plus argmax or the Hungarian method. The code instead publishes every person to
  the controller, one message after the other.
- Problem statement 3 ("may mistakenly follow the wrong person") is therefore open. *Twin*
  evidence (Arena 3 draft, current code, `fixed` bridge):

  | Scenario | Result |
  |---|---|
  | `side_by_side` | Mixing the other person's range (about 1.9 m) with the target's (0.8 m) makes the robot speed up and **drive into the standing target** (0.21 m centre to centre at t = 3 s). It then follows the other person and ends 5.2 m from the target. |
  | `stand_aside` | Turns towards a bystander and loses the target. |

  The Arena 3 reference (current code, full protocol) passes 6 of 21 identity runs and scores
  60.6/100; see `experiments/arena/2026-10-22_arena3-draft.md`.

### B4. The Kalman filter is reviewed (2.1.2) but not used

A constant-velocity Kalman filter on the target's position (from LiDAR range and bearing) gives:

- a predicted position for gating (Mahalanobis distance);
- a principled Hold mode through short occlusions;
- a motion feature that is not double-counted.

It fits a 12 Hz 2D LiDAR and costs nothing on the UP Board. The thesis should either use it or drop
it from chapter 2.

## C. Appearance (colour) features

### C1. The colour plots (4.5) cannot show discrimination

- Only the target's pixels are plotted. To show that colour separates people, the thesis needs
  the **distance between people** compared with the **distance within one person over time**:
  histograms, ROC/AUC, and the ID-switch rate with and without colour.
- **4.5.1:** a "linear" spread in RGB is the brightness axis. It shows illumination change, not
  consistency.
- **4.5.3 is circular** if the confidence already uses colour: high-confidence points cluster in
  colour because colour made them high-confidence.

### C2. Where chroma breaks down on a farm

- **Shade.** Shade lowers saturation and pulls Cb/Cr towards grey (128). Chroma is not
  illumination-invariant; only luma is separated.
- **Neutral clothing.** White, black and grey clothing all sit near (128, 128), so chroma carries
  no information.
- **Similar clothing.** Workers often wear the same uniform or the same rain jacket.

*Twin* scenarios now cover the first and third case: shade in `stand_aside`, and the same clothes
in `side_by_side_same`.

### C3. A box crop is not a person mask (from Codex's review in T8)

The new `torso_chroma()` in `ros2_yolo_live.py` takes the median Cb/Cr of a rectangle inside the
box. Background between arm and body, an overlapping person, or partial occlusion can all shift
that median. The twin does not model this contamination. E4 must measure it, not only the
within-person and between-person distances.

### C4. The box-size distance cue (scope 1.2.ii, 1.4) fails at the following distance

- The C922's vertical field of view is about 43°. With the camera at 1.1 m, it sees only a 0.40 m
  tall slice of the person at 0.5 m, and 0.79 m at 1.0 m.
- At the distances the robot follows from, the box is **clipped**, so its size says nothing about
  distance. Detection itself may also degrade when only the torso is visible. The twin assumes
  detection works down to 0.3 m, and **that assumption is untested**.
- **Fix: E3** (detection rate against distance). It also decides the set-point: the draft says
  1.2 m (3.4.1), the scope says 0.5–1.0 m, and the code uses 0.5 m.

## D. Missing results and inconsistencies

### D1. The objectives have no results

| Objective | Evidence in the draft |
|---|---|
| 3: Follow–Stop controller | No gap error, no stop latency, no success rate. |
| 4: accuracy, stability, safety | Only perception sub-metrics. |
| Expected benefit 2 ("outperforming systems that rely solely on YOLO or LiDAR") | No comparison at all. Needs the ablation E7. |
| Problem 3: multiple people | Not tested. |
| Chapter 5 | Empty. |

### D2. The text and the code disagree

| Thesis | Code |
|---|---|
| YOLOv5, "fine-tuned" (abstract, 3.1, 4.2) | Stock `yolov8n` through OpenVINO |
| Δθ = 3° LiDAR window around θ_cam (3.3.3, 3.4.2) | 9 camera sectors; nearest LiDAR sector by bearing, ±35° |
| ω = k_a·θ_cam (3.3.7) | Sector dead-band plus edge counter. Since Arena 2: gain 0.3, limit 0.8 rad/s |
| v = k_d·(d − d_safe), d_safe = 1.2 m, v_max 0.6 m/s (3.4.1) | Set-point 0.5 m, P plus speed feed-forward (Arena 2). The bridge maps 1.0 to 40 RPM, about 0.36 m/s with an unmeasured 0.085 m wheel |
| Obstacle override (3.3.7) | Not in the code |
| Initial mode with "explicit user confirmation" | Auto-lock at 0.5–1.0 m, no confirmation |
| Return-to-start, route graph (scope 5) | Not working (4.3.1). Move it to limitations or future work |

Front-matter errors:

- the year (2023);
- "Submited";
- TOC numbering (1.4/1.5 listed on page 9 before 1.2);
- two sections numbered 3.3.5;
- "Solutionฃ";
- empty sections 2.2.3, Acknowledgements and Chapter 5.

## E. Revised experiments

Each experiment answers one point above. Twin work runs any time. The robot-day work fits the two
days a month.

| ID | Question | Where | Protocol | Metric |
|---|---|---|---|---|
| E1 | Do camera and LiDAR agree on the person's direction? | Robot | Tape marks at −30…+30° every 10°, at 1, 2 and 3 m; 10 s per mark | Bearing MAE and bias (°); share of frames where the chosen LiDAR return is within ±0.2 m of the tape distance |
| E2 | What is the real latency? | Robot (bag) | Detections carry the image stamp (code change) | Capture → detection → `/cmd_vel` (ms), median and p95 |
| E3 | Does YOLO still see a person at the following distance? | Robot | Person at 0.4, 0.5, 0.75, 1.0, 1.5, 2 and 3 m, facing towards and away; 10 s each | Detection rate; box clipping; sets the set-point |
| E4 | Does clothing colour separate people, and when not? | Robot (bag) | 2 people × (different, same) clothes × (sun, shade); also with the two people overlapping in the image | Within-person vs between-person CbCr distance; AUC; how far the crop's median moves when another person or background enters the box; uses the new `cb, cr` fields |
| E5 | Does the robot keep the right person? | Twin (Arena 3), then robot | `side_by_side`, `side_by_side_same`, `stand_aside`, `head_on`, `crossing` | Pass rate, tracked share, ID switches per minute, closest approach |
| E6 | How well does it follow? | Twin (Arena 2, done), then robot | Straight, stop-and-go, curve; 10–40 m | Median and final gap, success rate, stop latency |
| E7 | Does each part help? (expected benefit 2) | Twin | Same entry with colour off, KF gating off, LiDAR off | ΔE5 and ΔE6. This is the comparison the thesis claims |

**Robot day 1.** E1, E3 and E4 recordings, plus E2 once detections carry stamps. Before that day,
check `turn_dir` with the wheels lifted (T6).

**Robot day 2.** E5 and E6 with the Arena 3 winner, and E2 from its bags.

## What changed in the repository because of this review

- **Arena 3 (draft).** The twin now gives each detection a clothing chroma `[cx, cy, sector, cb, cr]`.
  Shade lowers saturation, and the twin has a same-clothes scenario. So the thesis's own method
  (colour plus a confidence) can enter the arena and be tested against geometry-only tracking.
- **`ros2_yolo_live.py`.** Publishes the median torso Cb/Cr of each box in the same
  `[cx, cy, sector, cb, cr]` format. Downstream nodes read only the first 3 fields, so their
  behaviour is unchanged. This is what E4 records on the robot.
