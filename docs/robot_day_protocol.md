# Robot-day protocol: experiments E1–E6

These are the robot-side experiments from `docs/thesis_review_2026-10-22.md` (section E). Each one
answers a gap in the thesis draft. E7 is run in the twin.

Every recording is one `record_robot_day.sh` run. Its `--scenario` label carries the ground truth,
and `tools/robot_day/analyze.py` turns a folder of recordings into numbers. Write labels exactly as
shown, because the analyser parses them.

## Working alone (current plan, 2026-10-24)

The user runs robot days alone, so the two-person experiments (E4, E5) wait. The goal for now is
**following one person reliably at walking pace**. Each recording uses `--countdown` (time to walk to
the mark; the terminal beeps each second) and `--duration` (it stops by itself):

```bash
ros2_yolo_ws/scripts/record_robot_day.sh --scenario e3_d0.5_front --countdown 10 --duration 10
```

| Order | What | Alone? | Time |
|---|---|---|---|
| 0 | `turn_check.py`, wheels lifted (T6) | yes | 10 min |
| 1 | Measure the wheel radius, track width and camera height. Then on the ground run `speed_check.py --speed 0.4`, correct `wheel_radius_m`, and write it in `config/motor_wheel_calibration.md` as `wheel_radius_m = 0.083 (measured 2026-11-02)` (`preflight.py` looks for that line) | yes | 20 min |
| 2 | First drive at `max_speed_mps:=0.5`; raise it to 1.0, then 1.4, once following looks right | yes | — |
| 3 | E3: you stand at each distance, with a countdown | yes | 30 min |
| 4 | E1: you stand on each tape mark, with a countdown | yes | 40 min |
| 5 | E6 solo: the robot follows you through the twin's solo moves, 3 runs each (`e6_<move>_<n>`, `--countdown 5 --duration 30`) | yes | 60 min |
| — | E2 is computed from every recording | — | — |

The E6 moves match the twin's `solo` set:

| Twin scenario | Move |
|---|---|
| `straight` | walk straight and stop |
| `stop_and_go` | walk, stop 5 s, walk on |
| `walk_0p6` and `walk_1p0` | your slow and normal pace |
| `turn_90` | a right-angle turn |
| `side_step` | step 1 m sideways, then walk on |
| `come_back` | walk away, turn and come back towards the robot to load it |
| `zigzag` | weave left and right |

`analyze.py` reports for each run:
- the share of time the target was tracked;
- the longest dropout;
- the median, 95th-percentile and smallest gap;
- the highest forward command.

A phone video from behind helps with the notes.

## Starting the robot (one command)

```bash
python3 tools/robot_day/preflight.py --max-speed 0.5          # files, serial port, disk, parameters
ros2 launch ros2_yolo_ws/launch/follow_bringup.launch.py max_speed_mps:=0.5 \
    camera_cmd:="<camera driver command>" lidar_cmd:="<LiDAR driver command>"
python3 tools/robot_day/preflight.py --live --max-speed 0.5   # in a second terminal: every topic's rate
```

- **What the launch starts:** YOLO, `lidar_sectorizer`, `sync_fusion`, `fusion_prob`, `follow_stop` and
  the ZLAC bridge.
- **Drivers:** the camera (`/image_raw`) and LiDAR (`/scan`) drivers are not in the repository. Pass
  their commands as above, or start them yourself before the launch.
- **Parameters:** `wheel_radius_m:=`, `turn_dir:=`, `port:=` and `model_path:=` override the defaults.
  `bridge:=false` starts everything except the motors, for a bench test.
- **Legacy bridge:** `speed_mode:=legacy` also sets `follow_stop` `max_decel` to 0.0 by itself.
- **`--live`:**
  - FAILs if a topic is missing or too slow, or if `/cmd_vel` has no bridge or no `follow_stop`;
  - warns if most LiDAR rays return nothing.
- **Exit code:** 1 on any FAIL.

## Before the day

- [ ] Check out the commit to test. Note its SHA; the recorder also stores it in `recording.json`.
- [ ] Confirm the ROS 2 MCAP storage plugin is installed (`ros2 bag record --storage mcap`). If it is
      missing, change `--storage mcap` to `--storage sqlite3` in `record_robot_day.sh`; the analyser
      reads both.
- [ ] Bring a tape measure, floor tape, and marker. Mark the robot's centre point on the floor.
- [ ] Two people for E4 and E5: one red top and one blue top, plus two tops of the same colour.

## Robot day 1

### 0. Turn direction (T6), about 10 min

With the wheels lifted and the drive bridge running:

```bash
python3 tools/robot_day/turn_check.py
```

| Step | Command | Expected |
|---|---|---|
| 1 | `linear.x = 0.2` | Both wheels roll forwards. |
| 2 | `angular.z = 0.3` | Right wheel forwards, left wheel backwards (a left turn). |

- **If step 2 is wrong:** restart the bridge with `turn_dir:=-1` and repeat.
- **Record the result** in `config/motor_wheel_calibration.md`, then close T6.
- **Also measure:**
  - the wheel radius;
  - the track width (centre to centre of the wheels);
  - the camera height.

  Write them in the same file. The twin and the bridge still use assumed values: 0.085 m and 0.40 m.

### E1. Do camera and LiDAR agree on direction? About 40 min

- **Setup:** tape marks at bearings −30, −20, −10, 0, +10, +20 and +30°, each at 1, 2 and 3 m from the
  robot's centre, measured to where the person's body centre stands. **Left of the robot is positive.**
- **Procedure:** one person stands on a mark, facing the robot. Record about 10 s per mark:

  ```bash
  ros2_yolo_ws/scripts/record_robot_day.sh --scenario e1_b-20_d2.0
  ```

  The label is `e1_b<bearing>_d<distance>`.
- **Output:**
  - camera bearing error (bias, MAE);
  - LiDAR bearing error;
  - LiDAR range error;
  - the share of frames where the LiDAR return near the camera bearing is the person (within ±0.2 m).
- **Answers:** review A1 and A2. It replaces the circular Pearson r.

### E3. Does YOLO see a person at the following distance? About 30 min

- **Procedure:** one person stands straight ahead at 0.4, 0.5, 0.75, 1.0, 1.5, 2 and 3 m. At each
  distance, record 10 s facing the robot (`e3_d0.5_front`) and 10 s facing away (`e3_d0.5_back`).
- **Output:**
  - detection rate (frames with a person ÷ all processed frames);
  - share of clipped boxes;
  - mean confidence;
  - frame rate.
- **Answers:** review C4. It decides the set-point: the draft says 1.2 m, the code uses 0.5 m. If
  detection falls off at 0.5 m, raise `target_distance` before E5/E6.

### E4. Does clothing colour separate two people? About 30 min

- **Procedure:** two people stand side by side about 1.5–2 m ahead, A on the left and B on the right.
  Record 15 s for each combination:

  | Label | Clothing | Light | Position |
  |---|---|---|---|
  | `e4_diff_sun` | different | sun | side by side |
  | `e4_diff_shade` | different | shade | side by side |
  | `e4_same_sun` | same | sun | side by side |
  | `e4_same_shade` | same | shade | side by side |
  | `e4_overlap_diff_sun` | different | sun | B steps partly behind A, as seen from the camera |
  | `e4_overlap_same_sun` | same | sun | B steps partly behind A, as seen from the camera |

- **Output:**
  - each person's mean Cb/Cr;
  - spread within a person and distance between the two people;
  - their ratio;
  - nearest-mean accuracy;
  - for overlap, how far each person's mean moves.
- **Answers:** review C1–C3, including box-crop contamination.

### E2. Latency. No extra time

The analyser computes it from every recording that has `/yolo_frame`. That topic carries the image's
capture stamp, published by `ros2_yolo_live.py`.

- **Check the camera driver's stamps first.** E2 needs the driver to fill `header.stamp` from the
  same clock. The report counts frames whose stamp is 0, in the future, or more than 5 s old as
  `bad_stamps`. If most frames are bad, E2 has no meaning for that driver.
- **Recorder delay.** Receive times come from the bag recorder, so they include its own small
  delay.

- **Output:** capture → detection, detection → next `/cmd_vel`, and the end-to-end capture → `/cmd_vel` of each frame, each as median and p95.
- **Answers:** review A3. It replaces "dt 4–6 ms".
- **Then:** set `follow_stop` `latency_s` (default 0.2) to the median capture → `/cmd_vel`. The braking
  cap uses it.

## Robot day 2

### E5. Does the robot keep the right person? Field

- **Code:** the merged Arena 3 winner. `TargetGate` is on by default.
- **Scenarios:** the twin's 5, done by two people:
  - walking side by side, then splitting;
  - the same with matching tops;
  - one person walking towards the robot;
  - a bystander beside the path;
  - a person crossing between the robot and the target.
- **Repeats:** 3 of each, about 10–20 m.
- **Labels:** `e5_side_by_side_1`, `e5_crossing_2` and so on. The analyser reports E2 for these; the
  following itself is judged from the bag and the operator's note (did it stay with the target? any
  stop or contact?).
- **Comparison:** repeat `side_by_side` with `target_gate:=false` (the old behaviour).

### E6. Following performance. Field

- **Runs:** straight, stop-and-go and curve, 10–40 m, 3 repeats each.
- **Labels:** `e6_straight_1` and so on.
- **Record:** the LiDAR gap to the target, and stop latency when the target steps out of view.

## After each day

```bash
python3 tools/robot_day/analyze.py ~/robot_day_recordings --out robot_day_report.json
```

Copy the report (not the bags) into `experiments/robot_day/<date>/` with a short write-up. The bags
stay on the robot or an external drive and are listed in `raw_data_index.md`.

## Tested on twin bags (2026-10-24)

I ran the analyser inside the twin image on bags from `run_scenario --record-bag`. The labels were
assigned by hand, and the commands were:

```bash
source /opt/ros/humble/setup.bash
python3 tools/robot_day/analyze.py <bag> --label e4_diff_sun
```

The full pipeline works: bag, `/yolo_frame`, statistics. The outputs were:

- **E4 on `side_by_side`:** mean chroma A (109.6, 164.9) and B (159.4, 110.0). These are the twin's two
  clothing colours. Separation ratio 20, nearest-mean accuracy 1.0.
- **E3 on `straight`:** 10 fps, detection rate 1.0, all boxes clipped. The twin's person is 0.5–0.8 m
  away and taller than the image.
- **E1 and E2** produced numbers. They mean nothing here, because the person walks and the twin has
  no inference delay.
