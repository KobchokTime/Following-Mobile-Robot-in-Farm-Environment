# Arena 3 — keep following the right person (DRAFT)

**Status: draft.** Codex can object in `DISCUSSION.md` (T8). The rules are frozen only when both
agents reply `agree`, and the commit that freezes them is named there. No entry may start before then.
**Type:** simulation only.

## Problem

Twin finding 5 (`experiments/sim/2026-10-20_twin_first_run.md`) said the `crossing` scenario does
not really test target identity. The code has no notion of identity at all:

- `ros2_yolo_live.py` publishes one `/target_centroid_sector` message **for every person** in the
  frame.
- `sync_fusion_node.py`, `fusion_prob_node.py` and `follow_stop_node.py` treat every message as
  "the target".

With two people in view, the robot gets commands for both, one message after the other. The new
scenarios below show what happens on the current code (`integration-hub`, after the Arena 2
merge), `fixed` bridge, seed 0:

| Scenario | What happens |
|---|---|
| `side_by_side` | The other person's range (about 1.9 m) is mixed in with the target's (0.8 m), so the robot speeds up and **drives into the target**, who is still standing: 0.21 m centre to centre at t = 3 s, a contact. Then it follows the other person and ends 5.16 m from the target, with the target out of view. |
| `stand_aside` | Turns towards the person standing beside the row and loses the target (final gap 3.28 m). |
| `crossing` | Passes. The other person crosses beyond the target. |
| `head_on` | Passes. |

## Task

Lock on to the person in front at the start (the existing 0.5–1.0 m initialisation), and keep
following that person while another person walks alongside, walks towards the robot, stands
beside the path or crosses. Do not lose the Arena 2 following performance.

## New scenarios (in `sim/twin/scenarios.py`, `IDENTITY_SCENARIOS`)

| Name | Second person |
|---|---|
| `side_by_side` | Walks 0.8 m ahead and 0.7 m right of the target. At the curve the target turns left and the other person turns right. |
| `head_on` | Walks towards the robot and passes 0.8 m to its left. |
| `side_by_side_same` | As `side_by_side`, but both people wear the same colour. |
| `stand_aside` | Stands still 0.7 m right of the path, like a worker in the next row. There is tree shade around the bystander (x = 3 to 5.5 m) that the target also walks through. |
| `crossing` | Existing: crosses from right to left beyond the target. |

`SCENARIOS` stays the Arena 2 set, so the frozen Arena 2 scorer still validates its runs.
`run_scenario --scenario everything` runs all 9 scenarios. `--scenario identity` runs only the 5
above. `--bridge-mode turning` runs the `fixed` and `diff_drive` bridges.

## What the entries can use

Only what the robot really has, or will have with this draft:

- **Detections `[cx, cy, sector, cb, cr]`**, one message per person, with no identity.
  - `cb, cr` is the median clothing chroma of the torso (YCbCr, 0–255, 128 is grey). This is the
    appearance feature in the thesis (4.5).
  - The real `ros2_yolo_live.py` now publishes it in the same format.
  - In the twin, the target wears red (Cb 110, Cr 165) and other people wear blue (160, 110),
    except in `side_by_side_same`. Each frame adds noise (σ = 3), and shade pulls the chroma
    towards grey.
  - The colour has its own random stream, so the geometry of every run is the same as before.
- **The LiDAR scan.**

Possible approaches:

- keep the detection nearest to the predicted bearing;
- gate by LiDAR range, or track LiDAR clusters;
- match clothing colour;
- the thesis's Bayesian confidence.

The twin and Gazebo produce the detections themselves, in place of camera plus YOLO. A change
made only in `ros2_yolo_live.py` is therefore not scored. Target selection must live in
`sync_fusion_node.py`, `fusion_prob_node.py` or `follow_stop_node.py`. Old bags carry only
`[cx, cy, sector]`, so code that reads `cb, cr` must accept 3-value messages.

`side_by_side_same` and the shade are there so that colour alone cannot win. See
`docs/thesis_review_2026-10-22.md` (B3, C2). The pipeline's node list
(`sim/twin/pipeline.py`) is protected, so the selection must live inside the existing nodes. A
new node would not be started.

## Protocol (minimum, checked by the scorer)

- **Twin:** at least 3 repeats (seeds 0, 1 and 2), each
  `--scenario everything --bridge-mode turning`, so 18 runs per seed (about 10 minutes).
  The `current` bridge is dropped: it cannot turn, so it says nothing about following.
- **Gazebo:** at least 2 runs each of `curve_left`, `side_by_side`, `side_by_side_same` and
  `stand_aside` on the `fixed` bridge.

## Scoring (`sim/arena/score_entry_v3.py`, 100 points, `fixed` bridge)

- **Identity, 50 points.** The identity scenarios, twin and Gazebo together.
  - 30 points × the share of runs that pass.
  - 20 points × the mean *visible share*.
  - A run passes when the target is in view at the end, within 1.5 m, there is no contact, and the
    visible share is at least 0.9.
  - *Visible share* (`target_visible_share`, new in `sim/twin/score.py`) is the share of the run
    after the 3 s start with the target inside the camera's ±35° and within 2 m. It is ground-truth
    visibility: it shows that the robot stayed with the target, not what a tracker believed.
- **Following, 30 points.**
  - Lag, 20 points: the Arena 2 formula scaled to 20, comparing the median gap in `straight`,
    `stop_and_go` and `curve_left` with 0.5 m.
  - Reliability, 10 points × the share of `curve_left` runs that pass.
- **Behaviour, 20 points**, on both twin bridges and in Gazebo. 5 points off for each failed check:
  - any contact;
  - `target_loss` not stopping within 1.5 s;
  - `curve_left` not turning.
- **Scope:** as Arena 2. Allowed paths are `ros2_yolo_ws/scripts/` except the drive bridge,
  `tests/`, your own `logs/<agent>.md` and `experiments/arena/entries/<agent>.md`. Any violation
  scores 0.

## Rules (as Arena 2)

- Branches: `claude/robot/arena3-identity` and `codex/robot/arena3-identity`, from the freeze commit.
- Don't read the other agent's branch until both entries are in. Post only the entry SHA in T8.
- The judge is the `integration` role. It runs both entries on the same machine in alternating
  order, with `--base-ref <freeze SHA>`, and posts the raw summaries.
- Entries stay unmerged until judged. The user decides the merge.

## Reference: current code (`integration-hub` `e504153` plus this draft), not an entry

The full minimum protocol was run: 3 twin repeats (seeds 0, 1 and 2; 9 scenarios × 2 bridges) and
2 Gazebo runs each of 4 scenarios. The colour channel is published, but the current code ignores
it.

| Part | Points | Detail |
|---|---|---|
| Identity | 16.5 / 50 | 6 of 21 runs pass. crossing 3/3, head_on 3/3; side_by_side 0/5, side_by_side_same 0/5, stand_aside 0/5. Mean visible share 0.40 |
| Following | 29.1 / 30 | mean median gap: straight 0.57 m, stop_and_go 0.55 m, curve_left 0.57 m; curve_left 0/5 failures |
| Behaviour | 15 / 20 | contact in `side_by_side` and `side_by_side_same`, with the target, as described above |
| **Total** | **60.6 / 100** | |

Raw data: `baseline_arena3_draft_2026-10-22.json`.

The failures are the same in the twin and in Gazebo:

- `side_by_side`: final gap 5.2 m in both Gazebo runs.
- `stand_aside`: final gap 3.2 m.

## Out of scope for Arena 3

- **Target occlusion.** The target walking behind a bystander is deferred to a later arena. The
  identity protocol here is a first set, not a complete one.
- **The colour model is synthetic.** The clothing colours, the noise and the shade factor are not
  calibrated to the C922. They are a repeatable test condition, not evidence that real clothing
  is separable; experiment E4 measures that on the robot.
- **`torso_chroma()` takes a rectangular crop, not a person mask.** Background, an overlapping
  person or partial occlusion can shift the median Cb/Cr on the robot. The twin does not model this
  contamination. E4 measures it.

## Open questions for Codex (T8) — answered 2026-10-22

Codex's answers:

1. The colour model is fair as a controlled first benchmark, though it is not camera-calibrated
   (see *Out of scope* above).
2. Keep the 0.9 threshold, and name the metric *visible share*. Done.
3. Drop the `current` bridge.
4. Five scenarios are a sound first set. Add an occlusion case later, or say it is deferred. It is
   deferred.

The original questions:

1. **The appearance cue.** The draft now includes `cb, cr`, both in the twin and on the robot,
   because clothing colour is the thesis's own identity feature. Are the twin's colour model (noise
   σ = 3, shade as a saturation factor) and the same-clothes scenario fair?
2. **Is the 0.9 visible-share threshold right?** In `head_on` the other person passes close by.
   A good entry may briefly lose the target from view while it ignores that person.
3. **Should the `current` bridge be dropped from the protocol?** It saves about a third of the run
   time, and the drive bridge already forwards `angular.z`.
4. **Are 5 identity scenarios enough?** Missing, for example: two people walking away in
   different directions from the start, or the target passing behind the other person (occlusion).
