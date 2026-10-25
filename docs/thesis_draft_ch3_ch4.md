# Thesis draft: Chapters 3 and 4 (rewrite)

> **Status: draft for the author.**
> - Written 2026-10-25 from the code on `claude/workspace` and the review in
>   `docs/thesis_review_2026-10-22.md`.
> - It describes **what the robot actually runs**, and it reports only results that exist.
> - Every robot measurement that has not been made yet is a placeholder:
>   **⟦ROBOT DAY: what to put here, and which experiment gives it⟧**.
> - The thesis `.docx` stays with the author. Copy text across by hand, and renumber figures and
>   tables to fit.
>
> **Main changes against the current draft (see the review for why):**
> - **YOLOv8n, not YOLOv5.** It runs on OpenVINO, and the code loads `yolov8n_openvino_model`.
> - **The "Bayesian Tracking Module" (old 3.3.5) is replaced** by what runs. That is two parts:
>   - target selection: a gated alpha-beta track with a clothing-colour cost;
>   - a fused confidence: a weighted camera/LiDAR score with time smoothing.
>
>   The Bayes-rule equations are removed. They described a model that was never implemented.
> - **The following distance is 0.5 m** (code), not 1.2 m.
> - **The control law is sector-based steering plus a P + feed-forward speed law with a braking cap**,
>   not ω = k_a·θ.
> - **Results that cannot support their claims are removed.** That is "dt ≈ 4–6 ms" and the two
>   correlations. They are replaced by experiments E1–E7.
> - **Simulation results are reported as simulation**, separately from the robot results.

---

## CHAPTER 3 — METHODOLOGY

### 3.1 System overview

The robot follows one person on foot through farm paths. It uses a monocular RGB camera, a 2D LiDAR
and an embedded computer. There is no depth camera, no 3D LiDAR, no GPS and no map.

The software is a chain of ROS 2 Humble nodes (Figure 3.1):

1. **Detection** (`ros2_yolo_live.py`):
   - YOLOv8n finds people in each camera frame.
   - For each person it publishes the box centre, the image sector, and the median clothing chroma
     (Cb, Cr) of the torso.
2. **LiDAR sectoring** (`lidar_sectorizer_node.py`):
   - The front ±35° of each scan, matching the camera's field of view, is split into the same nine
     sectors.
   - It publishes the nearest return in each sector.
3. **Fusion and target selection** (`sync_fusion_node.py`):
   - Each detection is paired with the LiDAR sector that matches its *bearing* and the nearest scan in
     time.
   - It then decides whether the detection is the person being followed (Section 3.3.4).
   - It also handles three special cases: a person stepping into the path, the target leaving the
     image at its edge, and false or duplicate boxes.
4. **Confidence** (`fusion_prob_node.py`): a fused confidence score for the target, smoothed over time.
5. **Control** (`follow_stop_node.py`): the forward speed and turn rate, or a stop when confidence is
   low.
6. **Drive bridge** (`zlac_joystick_bridge.py`): turns `/cmd_vel` into the wheel speeds of the ZLAC8015D
   driver, with a speed cap and an acceleration ramp.

The whole chain starts with one command, `ros2 launch ros2_yolo_ws/launch/follow_bringup.launch.py`.
A preflight script checks that every topic is alive before the robot moves.

⟦FIGURE 3.1: node graph. Redraw the old "System Architecture Diagram" with the six nodes and topics
above: `/image_raw`, `/scan`, `/target_centroid_sector`, `/lidar_sector_dists`, `/synced_target`,
`/target_fused_prob`, `/cmd_vel`.⟧

### 3.2 Equipment

| No. | Item | Use | Qty |
|---|---|---|---|
| 1 | Logitech C922 camera, 640×480 | person detection | 1 |
| 2 | YDLIDAR Tmini Pro (2D, 360°) | range to the target and to anything in the path | 1 |
| 3 | UP Board | runs all ROS 2 nodes, with YOLO on OpenVINO | 1 |
| 4 | ZLAC8015D dual-channel driver and two hub motors | differential drive over RS-485 (Modbus) | 1 |
| 5 | 3-colour LED tower | shows the robot's state | 1 |
| 6 | HDMI touch screen | status and commands | 1 |
| 7 | 12 V battery | power | 1 |

⟦ROBOT DAY: measured wheel radius, track width, and camera and LiDAR heights
(`config/motor_wheel_calibration.md`). The code currently assumes a 0.085 m wheel radius and a
0.40 m track width.⟧

### 3.3 System design

#### 3.3.1 Person detection

- **Model.** YOLOv8n, exported to OpenVINO, runs on each frame from `/image_raw`. Only the class
  *person* is kept.
- **What is published.** For each person the node publishes:
  - the box centre (c_x, c_y) and the image sector, where the 640-pixel width is split into
    N = 9 equal sectors;
  - the median Cb and Cr of the torso (the middle half of the box width, 20–55% of its height),
    used as a clothing-colour feature (Section 3.3.4);
  - once per processed frame, on `/yolo_frame`, the capture time stamp and every box, for the latency
    and detection experiments.
- **No distance from the camera.** Box size is not used as a distance cue: at the 0.5 m following
  distance the person's box is clipped by the image edges. All ranges come from the LiDAR.

#### 3.3.2 Bearing of a detection

The camera bearing of a box centre uses the pinhole model, with the horizontal field of view
FOV_h = 70° and the image width W = 640 px:

  f = (W/2) / tan(FOV_h/2),  θ_cam = atan((W/2 − c_x) / f)

Left of the robot is positive. The old linear formula θ = (c_x − W/2)·FOV_h/W has the opposite sign,
and it is about 2° off at the image edge.

⟦ROBOT DAY E1: the measured camera bearing error (bias and MAE, in degrees) at tape marks of −30° to
+30°, at 1–3 m.⟧

#### 3.3.3 LiDAR sectors and association

- **Sectors.** `lidar_sectorizer` keeps the returns between −35° and +35° of the robot's heading (the
  LiDAR is mounted facing backwards, so it applies a 180° offset). It splits them into nine sectors and
  publishes each sector's nearest valid return and centre angle.
- **Association.** `sync_fusion` pairs a detection with the LiDAR sector **whose centre angle is
  nearest θ_cam**.
  - It does not use the sector with the same index: camera sectors run left to right in the image,
    while LiDAR sectors run in angle order. The old index match was mirrored.
  - The pair is used only if the nearest LiDAR message arrived within 0.10 s of the detection.
- **What this does not give.** The range is the nearest return in that sector, so a nearer object
  in the same sector is reported instead of the person. The give-way rule (3.3.4) depends on this.

⟦ROBOT DAY E1: LiDAR bearing and range error, and the share of frames where the LiDAR return near
θ_cam is the person (within ±0.2 m of the tape-measured range).⟧

#### 3.3.4 Target selection (data association)

The camera node publishes one message per person and gives them no identity. Choosing which detection
is the target is therefore the central problem when more than one person is visible (problem
statement 3).

The `TargetGate` keeps one target track:

- **Lock-on.** The first detection in the start window (range 0.5–1.0 m, bearing within ±15°)
  becomes the target. The person starts the robot by standing in front of it.
- **Track.** An alpha-beta filter (α = 0.6, β = 0.2) on bearing and range predicts where the target
  will be at the next detection.
- **Gate.** Each detection gets a normalised cost against the prediction:

  c = ((θ − θ̂)/σ_θ·w)² + ((r − r̂)/σ_r·w)² + ‖(Cb, Cr) − (Cb̂, Cr̂)‖² / σ_c²

  - σ_θ = 5°, σ_r = 0.15 m and σ_c = 15.
  - w widens by 1 per second after the target was last seen (w = 1 + (t − t_last − 0.2), when
    positive), so the target can be found again after a short occlusion.
  - Only a detection with c ≤ 9 is the target.
  - The colour reference adapts slowly (rate 0.05), so it follows shade but not a different person.
- **Guards**, each found in testing (Section 4.6):
  1. Two boxes on one person arrive about 1 ms apart. Steps under 0.015 s, which is under one frame
     even at 60 fps, update the position only. A rate taken over 1 ms would make every later
     prediction wrong.
  2. After 5 s with no fix the track is dropped, and lock-on starts again in the start window.
     Gates widened that far would accept a false box anywhere.
     - The first detection in the start window then becomes the target, **whoever it is**.
     - For one person this is how following resumes. With two people, the operator must make sure
       the right person walks back to the robot.
- **Give-way.**
  - When a detection is *not* the target, sits in the robot's corridor (±0.7 m), and is at least
    0.2 m nearer than the target, the distance sent to the controller is that person's range minus
    0.4 m. The robot then slows or stops for them.
  - The 0.2 m minimum stops a false box drawn over the target itself, which carries the target's own
    LiDAR range, from triggering it.
  - The cost of that minimum: someone less than 0.2 m nearer than the target is not treated as in
    the way. This threshold needs review before two-person trials.
- **LiDAR tracking past the image edge.** When the target leaves the image at its edge, the LiDAR
  keeps the target for up to 5 s, and the robot turns towards it:
  - "At the edge" means within 8° of the ±35° limit, or predicted to be past it by now.
  - The LiDAR fix is the person-sized cluster (end-to-end length 0.15–0.8 m) nearest the predicted
    bearing and range, in a scan at most 0.3 s old.
  - A target that vanishes in mid-image while not moving sideways means the detector failed. The
    robot does not guess; it stops.
  - One that was moving sideways fast enough to be predicted past the edge also gets LiDAR tracking.
    The prediction looks at most 1 s ahead, so the rule fires when |θ + θ̇·1 s| ≥ 27°.

#### 3.3.5 Fused confidence

`fusion_prob` turns each fused target message into a confidence P_fused, which the controller uses
to decide whether to follow.

  P_C = exp(−k·d_x²), where d_x = |c_x − W/2|/(W/2) and k = 0 (camera term; currently always 1)
  P_L = max(0, 1 − r/r_max), r_max = 2.0 m, averaged over the last 1 s
  P_obs = (0.7·P_C + 0.3·P_L) / (0.7 + 0.3)
  P_fused,t = a·P_obs + (1 − a)·P_fused,t−1, where a = 0.7·exp(−Δt / (2·0.33 s))

- **What P_fused is.** A smoothed score of how well the camera and the LiDAR agree that a target is
  present and near. It is **not** a posterior probability, and it does not choose between people.
  That is the gate's job (3.3.4).
- **Bayes' rule.** The old 3.3.5 equations described a model that is not implemented. Use them only
  if a later version implements them.

#### 3.3.6 Follow–Stop control

`follow_stop` runs on each fused message.

1. **Start.** The robot moves only after the target has been seen in the start window (0.5–1.0 m).
2. **Confidence.**
   - The mean of the last five P_fused values must be at least 0.6.
   - Below that, the last command is held for up to 1 s, then the robot stops.
   - When no message arrives at all, the drive bridge stops the wheels after 1 s.
3. **Speed.** With the gap error e = r − r*, where r* = 0.5 m:
   - **Feed-forward.** u_ff grows by 1.0·e·Δt while e > 0, up to 1.0 m/s, and decays with a 0.3 s time
     constant when e < 0. It learns the target's walking speed, so the gap does not settle where
     P-only control would leave it.
   - **Command.**
     - v = 1.5·e + u_ff when e > 0.1 m;
     - v = u_ff in the ±0.1 m band;
     - v = 1.5·e (reversing) when e < −0.1 m.
   - **Braking cap.** v ≤ √(2·a·max(0, e − v̂·τ)), where a = 0.8 m/s² and τ = 0.2 s.
     - It limits the speed to what can still stop within the gap that is left, allowing for the gap
       closed during the perception latency τ.
     - v̂ is the *estimated* forward wheel speed, not the last command. It is modelled as the drive
       bridge's 1.0 m/s² ramp towards the last command, because while the robot slows down the wheels
       still turn faster than the command.
     - It is an estimate, not a measured wheel speed, and τ is a guess until E2. So this is a design
       intent, not a guarantee.
     - Reversing is limited by the gain 1.5 and the ramp: a person walking quickly up to the robot can
       come closer than the set-point (Section 4.5).
4. **Steering, by image sector** (centre sector 4):
   - The robot does not turn while the target stays in sectors 3–5.
   - Outside them it turns at ω = −0.3·(s − 4), limited to ±0.8 rad/s.
   - LiDAR edge tracking (3.3.4) reports sector 0 or 8, which gives a full-rate turn towards the side
     where the target left.

#### 3.3.7 Drive bridge

- **Wheel speeds.** The bridge maps /cmd_vel (m/s, rad/s) to the two wheel speeds of a differential
  drive, v ± ω·b/2, where b is the track width. They are converted to RPM with the wheel radius.
- **Limits.** Each wheel is capped at 1.4 m/s. Both wheels ramp together at 1.0 m/s², so the robot
  keeps its turning radius while it accelerates.
- **Parameter check.** Parameters are checked before the motor driver is opened.

⟦ROBOT DAY: turn direction check (T6) and the measured wheel radius from `speed_check.py`.⟧

### 3.4 Experiments

#### 3.4.1 Simulation

The real nodes run unmodified against two simulators:
- a fast 2D **twin**, `sim/twin`, with a modelled camera, LiDAR and drive bridge;
- a **Gazebo** (Ignition Fortress) world, `sim/gazebo`, with a GPU LiDAR and walking people.

There are three scenario sets:
- **Arena 2:** following, curves and target loss.
- **Identity, 5 scenarios:** two people crossing, walking side by side (with different or the same
  clothes), a person walking head-on, and a bystander beside the path.
- **Solo, 10 scenarios:** one person walking at 0.3, 0.6 and 1.0 m/s, stopping, turning 90°, stepping
  sideways out of view, coming back, and zigzagging.

A **realism profile** adds:
- 0.15 s detection latency, 10% missed and 3% false detections;
- LiDAR noise and dropout;
- 5% wheel slip;
- posts and bushes beside the path.

**Pass rule.** A run passes when:
- the target is in the camera's view at the end;
- the final gap is at most 1.5 m;
- there is no contact (centre to centre under 0.4 m);
- the target was visible for at least 90% of the run.

Each set is run with seeds 0–2.

#### 3.4.2 Robot experiments

These follow `docs/robot_day_protocol.md`. Every run is recorded with `record_robot_day.sh`, whose
label carries the ground truth, and is analysed with `tools/robot_day/analyze.py`.

| Exp. | Question | Setup |
|---|---|---|
| E1 | Do camera and LiDAR agree on direction and range? | Tape marks at −30° to +30°, 1–3 m |
| E2 | What is the real latency from capture to command? | Every recording (`/yolo_frame` stamps) |
| E3 | Does YOLO see a person at the following distance? | 0.4–3 m, facing towards and away |
| E4 | Does clothing chroma separate two people? | Different or same clothes, sun or shade, overlap |
| E5 | Does the robot keep the right person? | The 5 identity scenarios with two people, 3 repeats |
| E6 | How well does it follow? | The solo moves, 3 repeats, 10–40 m |
| E7 | Which part of target selection helps? | Ablation in simulation |

⟦ROBOT DAY: test site, date, weather and lighting, path length and surface. Add a photo of the site
and of the robot.⟧

---

## CHAPTER 4 — RESULTS AND ANALYSIS

> Sections 4.1–4.4 are robot results and are placeholders until robot day. Sections 4.5–4.7 are
> simulation results that exist now. The thesis should always label them as simulation.

### 4.1 Sensor alignment (E1)

⟦ROBOT DAY E1:
- table of camera bearing error, LiDAR bearing error and LiDAR range error, each as bias and MAE, per
  distance;
- a plot of θ_cam against the tape-measured bearing, with the y = x line;
- the share of frames where the associated LiDAR return is the person.⟧

**Replaces:** the old Pearson r between c_x and sector index. That correlation is set by
construction, because the sector is computed from c_x, so it cannot show alignment.

### 4.2 Latency (E2)

⟦ROBOT DAY E2:
- median and 95th percentile of capture → detection, detection → /cmd_vel, and capture → /cmd_vel;
- the YOLO frame rate.⟧

**Replaces:** "dt ≈ 4–6 ms". That figure was the gap between two message arrival times, not sensor
synchronisation or latency.

**Then:** set `latency_s` in `follow_stop` to the measured median and repeat the realism runs
(Section 4.6) with it.

### 4.3 Detection at the following distance (E3)

⟦ROBOT DAY E3:
- detection rate, share of clipped boxes and mean confidence, per distance (0.4–3 m) and facing
  direction;
- whether 0.5 m is a workable set-point. If detection drops at 0.5 m, raise `target_distance` and
  say so here.⟧

### 4.4 Clothing colour (E4)

⟦ROBOT DAY E4:
- each person's mean (Cb, Cr);
- the spread within each person and the distance between the two people, and their ratio;
- nearest-mean accuracy, for different and same clothes, in sun and shade;
- how far each person's mean moves when the boxes overlap.⟧

**Replaces:** the old Section 4.5 (RGB/YCbCr scatter plots of a single person). One person's colour
cloud cannot show that colour separates *two* people.

### 4.5 Following one person (simulation; robot E6 to follow)

**Twin, `mps` bridge, seeds 0–2, without the realism profile:**
- The solo set passes 29 of 30 runs.
  - The one failure, `side_step` seed 1, happened while six runs shared the machine.
  - It passed on two reruns, and repeats of `side_step` and `zigzag` pass 6 of 6.
- Median gaps are 0.42–0.58 m against the 0.5 m set-point.
- There is no contact.
- When the target disappears mid-image (`target_loss`), the robot stops within 1.2–1.3 s.

**Before the speed changes in Section 3.3.7:** with the original bridge, capped at about 0.36 m/s,
5 of 10 solo scenarios passed. A person walking at 1.0 m/s pulled away to 5.8 m.

**Gazebo, `mps` bridge, seeds 0–2:**
- 27 of 30 runs pass.
- All three failures are `come_back`: the person walks back to the robot and comes within 0.39 m,
  centre to centre, against the 0.40 m contact limit. Reversing is slower than the person walking up.
- Every other scenario passes 3/3, with median gaps of 0.43–0.57 m.
- See `experiments/sim/2026-10-25_gazebo_solo.md`.

⟦ROBOT DAY E6:
- for each move: share of time tracked, longest dropout, median, p95 and smallest gap, and highest
  speed;
- a comparison with the twin numbers above;
- a phone video still per move.⟧

### 4.6 Robustness to imperfect sensors (simulation)

The same code was run with the realism profile (3.4.1). The profile exposed five defects, which were
then fixed:

| Defect | Effect | Fix |
|---|---|---|
| Two boxes on one person, about 1 ms apart | the track's rate exploded and the target was never accepted again | position-only update for steps under 0.015 s |
| A false box over the target | read as a person in the path, so the robot backed off | give-way needs ≥ 0.2 m nearer than the target |
| Gates widening without limit | after 7 s a false box at a post was accepted, and the robot drove at it | unlock after 5 s, then lock-on again |
| Latency in braking | ended 1–2 cm inside the contact limit | braking cap allows for τ = 0.2 s, using the estimated wheel speed (after Codex's T11 review) |
| Late edge exit | LiDAR tracking did not start | also use the predicted bearing |

| Code | Solo (30 runs) | Identity (15 runs) | Contact |
|---|---|---|---|
| Before the fixes | 19 | 13 | 0 |
| After the fixes, first run (6 jobs in parallel) | 27 | 15 | 0 |
| After the fixes, integration re-run (one job at a time) | 29 | 15 | **1** (`come_back` seed 2, 0.355 m) |

- **The two runs differ.** Runs are not bit-identical: ROS timing changes with machine load. Report
  both.
- **The contact.** The `come_back` contact matches Gazebo, where the closest approach is 0.39 m in
  every seed. A person walking back to the robot comes closer than the controller can reverse.
- ⟦RE-RUN after the wheel-speed estimate in the braking cap; update this table.⟧

In the first run the three failures were `zigzag` ×2 and `side_step` ×1:
- The person weaves within 1 m of the robot, so the bearing changes at about 100°/s.
- The sector steering turns at a fixed rate, and with 0.2 s latency it sometimes turns the wrong way.
- This is the main limit of the current controller (Section 5).

### 4.7 Which part of target selection helps (E7, simulation)

Identity set, `fixed` and `diff_drive` bridges, seeds 0–2, 30 runs per condition. Each part is
switched off by a parameter only.

| Condition | Passed | Contacts |
|---|---|---|
| Full | 30 / 30 | 0 |
| No colour | 27 / 30 | 0 |
| No give-way | 28 / 30 | 2 |
| No gate (the original pipeline) | 12 / 30 | 8 |

- **Data association is the main gain.** Without it the robot follows whichever person is nearest in
  the sector.
- **Colour breaks the near-ties.** These are cases where geometry alone puts a bystander inside the
  gate.
- **The give-way rule prevents contact** with a person crossing between the robot and the target.

These runs were made before the fixes in 4.6. ⟦RE-RUN E7 on the current code and update the table.⟧

⟦ROBOT DAY E5: the identity scenarios with two people, 3 repeats each, including `side_by_side` with
`target_gate:=false` for comparison.⟧

### 4.8 Mapping

Unchanged from the current draft (old 4.3.1): SLAM was not stable outdoors, so return-to-start is
out of scope. Keep it as a stated limitation.

### 4.9 Summary against the objectives

| Objective | Evidence | Status |
|---|---|---|
| 1. Monocular person detection and position | E1, E3 | ⟦robot day⟧ |
| 2. Camera–LiDAR fusion for target confidence | 3.3.3–3.3.5; E1, E7 | E7 (sim) done; E1 ⟦robot day⟧ |
| 3. Follow–Stop controller | 4.5, 4.6; E6 | sim done; E6 ⟦robot day⟧ |
| 4. Outdoor farm evaluation | E1–E6 | ⟦robot day⟧ |

---

### Notes for the author

- **Figures to remove:**
  - the correlation plots (old Figure 17 and the dt histogram);
  - the confidence-coloured YCbCr scatter, which plots a quantity that does not exist in the code.
- **Figures to add:**
  - the node graph (3.1);
  - a twin trajectory for one solo scenario (the dashboard can export one);
  - the E1 bearing plot;
  - the E2 latency histogram.
- **Simulation and robot results.** Keep them in separate sections. Examiners will ask which numbers
  came from the robot.
