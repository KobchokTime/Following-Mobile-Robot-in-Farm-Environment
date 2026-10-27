# Clothing colour on video: lab clips, held-out clips and a public crowd video

- **Date of analysis:** 2026-10-26.
- **Folder:** renamed from `lab_videos_2025-04-08` when the held-out clips were added. The robot-side
  change is on branch `claude/robot/hs-colour`. `gate_replay.py`, `heldout.py` and
  `variants_heldout.py` load the gate from that branch through `$SYNC_FUSION`.
- **Videos:** `Videos/WIN_20250408_14_00_41_Pro.mp4` and `WIN_20250408_14_10_21_Pro.mp4` on
  `codex/robot-backup-quarantine` (Git LFS).
  - 1080p, 60 fps, 52 s and 54 s long.
  - They are not copied here. They were read from a scratch copy, and that branch is untouched.
- **Scene:** two people walk around an indoor lab, filmed by a camera that follows them.
  - One wears a blue top, the other a dark grey printed top.
  - The large windows are often behind them (backlight).
  - The person in blue crouches in shade beside a robot cart for several seconds.
- **Question:** how well does clothing colour tell the two people apart? We compare our torso Cb/Cr
  reference (`TargetGate`) with the paper's H,S Gaussian mixture (Kim, Suh and Kwon 2024, §3 and
  Algorithm 1).
- **Colour only.** The robot also gates by bearing and range, which these videos cannot give (no
  LiDAR). So this measures the colour term alone, not the whole gate.

## Method

1. `detect.py` runs the project's `yolov8n_openvino_model` on every 6th frame (10 fps).
   - Person boxes: confidence > 0.5, NMS 0.45.
   - For each box it records:
     - the torso Cb/Cr, using the same region and formula as `ros2_yolo_live.torso_chroma`;
     - 300 random H,S torso pixels.
   - Result: 436 and 478 boxes.
2. **Labels (`labels_*.json`).** Every box was labelled by eye from crop sheets:
   - `B` is the person in blue;
   - `D` is the person in dark grey;
   - `X` is anything else (the robot arm detected as a person, or a blurred mix of both).

   | Video | B | D | X |
   |---|---|---|---|
   | `14_00_41` | 244 | 177 | 15 |
   | `14_10_21` | 262 | 208 | 8 |

   Linking boxes by overlap was tried first, but the links swapped people too often to label whole
   tracks.
3. **`sep.py`** compares the Cb/Cr spread of the two people.
4. **`evalc.py`** replays each video frame by frame with one person as the target. The model locks on
   to that person's first box, then each frame picks the best-scoring box.
   - **Ours:** distance to the Cb/Cr reference.
     - The reference moves 5 % towards each accepted box (`chroma_rate`), or stays fixed.
     - It accepts within the `TargetGate` colour gate alone: cost ≤ 9 at σ = 15, which is 45 units.
   - **Paper:** a GMM on the H,S pixels of the target's last N picked boxes.
     - k from 1 to 6, chosen by BIC.
     - N = 10, or N = 0 (learned once at lock-on).
     - A box is accepted when its mean log-likelihood is at least the lowest training box's minus
       1. This threshold is ours; the paper's 0.5 probability has no direct equivalent here.
   - **Reported:**
     - the CT/CL/WT/WL states of the paper (§5.1), counted per sampled frame;
     - "ranked first": over the frames where both people are in view, how often the target scores
       best. It needs no threshold and is the fairest comparison.

## Results

### Colour spread (`sep.py`)

| Video | Blue top, median Cb/Cr | Dark top, median Cb/Cr | Blue boxes nearer the dark median |
|---|---|---|---|
| `14_00_41` | 139 / 125 | 131 / 128 | **28 %** |
| `14_10_21` | 139 / 120 | 129 / 128 | **26 %** |

- **The dark top is always grey** (Cb 128–133). No dark box is nearer the blue median than its own,
  except 1.4 % in `14_10_21`.
- **The blue top turns grey in shade and backlight.**
  - In the crouch beside the cart (boxes 80–117 of `14_00_41`, 74–109 of `14_10_21`) its Cb drops
    to 128–132, the same as the dark top.
  - At the start, walking into the window light, the blue top reads 132–135 against 128–130 for
    the dark top: 3–6 units apart.

### Picking the target by colour (`evalc.py`)

Target ranked first when both people are in view:

| Target | Video | Ours, rate 0.05 | Ours, fixed | GMM H,S, N = 10 | GMM H,S, N = 0 |
|---|---|---|---|---|---|
| Blue | `14_00_41` | **13.7 %** | 10.7 % | **78.0 %** | 58.3 % |
| Blue | `14_10_21` | **26.2 %** | 20.0 % | **92.3 %** | 67.2 % |
| Dark | `14_00_41` | 98.8 % | 98.1 % | 99.4 % | 100 % |
| Dark | `14_10_21` | 87.9 % | 96.5 % | 97.0 % | 96.5 % |

CT/CL/WT/WL with the blue top as target:

| Video | Model | CT | CL | WT | WL |
|---|---|---|---|---|---|
| `14_00_41` | Ours, rate 0.05 | 37.7 % | 0 % | 62.3 % | 0 % |
| `14_00_41` | GMM H,S, N = 10 | 76.5 % | 2.3 % | 18.1 % | 3.1 % |
| `14_10_21` | Ours, rate 0.05 | 42.3 % | 0 % | 57.7 % | 0 % |
| `14_10_21` | GMM H,S, N = 10 | 68.0 % | 4.4 % | 2.6 % | 25.0 % |

- **With the blue top as the target, our colour term picks the wrong person most of the time.**
  1. Lock-on happens in backlight, so the reference is almost grey.
  2. The dark top is then nearer to that reference than the blue top in good light.
  3. The 5 % update then follows the wrong person.
- Even with an ideal reference (the blue top's median over the whole clip), a single point
  misplaces 26–28 % of blue boxes (the table above).
- **The paper's H,S GMM with N = 10 ranks the blue top first in 78–92 % of frames.**
  - Hue keeps the blue even when it is dark.
  - Re-learning from the last 10 boxes follows the light.
  - Learning once (N = 0) gives 58–67 %. This agrees with the paper's point that online learning
    helps under changing light, though its own Table 1 also shows cases where N = 0 or N = 5 did
    better.
- **With the dark top as the target, both methods work (88–100 %).** A grey reference is easy to
  keep.
- **Ours never rejects on colour** (CL and WL are 0 %). Its 45-unit colour gate is wider than the
  whole spread of both people, so in the robot it is the bearing and range gate that rejects. The
  GMM's WL and CL depend on our threshold choice and should not be over-read.
- **Cost on this machine (4 CPU cores):**
  - re-fitting the GMM with BIC takes about **0.7 s** per update (10 boxes × 300 pixels, k = 1–6);
  - scoring takes 1 ms per box.
  - The robot cannot re-fit every frame. It could re-fit once a second in the background, or fix k.

## What this means

1. **Our single Cb/Cr reference is not enough when one person's top turns grey in shade or
   backlight.** In these videos that is a quarter of the blue top's boxes. A farm has strong sun and
   shade, so E4 on robot day will likely show the same.
2. **An H,S colour model with hue and online re-learning is clearly better here** (78–92 % against
   14–26 %). This is the strongest case so far for taking the paper's colour model.
3. **Lock-on light matters for ours.** A reference taken in backlight is poor. Locking on in good
   light, or averaging the first second, would help a little, but not with the shade problem.
4. **Limits.**
   - Indoor lab, one pair of tops, a hand-held camera.
   - Colour only, without the bearing and range gate.
   - The labels are by eye.
   - The GMM threshold is ours, not the paper's.

## Follow-up: an H,S histogram in the robot's TargetGate (branch `claude/robot/hs-colour`)

- **The paper's GMM is too slow to re-fit on the robot**, so a lighter model was built with the same
  ideas: H,S only and re-learned from the last 10 boxes.
  - The camera node sends a 12 × 4 H,S histogram of the torso (per mille) after `cb, cr`.
  - The gate compares it with the mean of the target's last 10 learned histograms (Hellinger
    distance, σ = 0.2).
  - A box is learned only if it is about as close to that mean as the boxes already learned (slack
    0.1). Without this guard the model drifted to the other person (dark target ranked first in 20 %
    of frames).
  - All settings were chosen on the two lab clips (`hist_variants.py`, `results_hist_variants.txt`).

### Held-out clips (`heldout.py`, `results_heldout.txt`)

The settings were then frozen and checked on five clips from the same branch that had not been used
yet. Each clip has one person, filmed outdoors.

| Clip | Video | Person |
|---|---|---|
| `park_black_1`, `park_black_2` | `WIN_20241126_14_23_33`, `14_24_34` | black tee, parking lot in sun |
| `park_pattern` | `WIN_20241126_14_26_37` | patterned shirt, parking lot |
| `farm_beige_1`, `farm_beige_2` | `WIN_20241210_13_47_33`, `13_51_31` | beige tee, greenhouse path in sun and shade |

- In `farm_beige_1` a second worker (hat, light blue top) walks through the frame for a few seconds.
- `WIN_20241126_14_39_25` (1.5 s, a desk, nobody in it) was not used.
- **Labels:** every box was checked by eye, and boxes showing only an arm or a blur were left out
  (`labels_*.json`).
- **Two checks:**
  - **A. Kept own:** the share of the person's frames the gate keeps accepting.
  - **B. Strangers:** each frame also shows a box of a different person from another clip. The check
    is whether the gate still scores its own person highest.

**The histogram alone failed the held-out check:**

| | Cb/Cr | Histogram alone | Histogram + Cb/Cr, half each (first adopted, then 0.25: see below) |
|---|---|---|---|
| A. Kept own, worst clip | 99.7 % | **37.4 %** (black tee) | 89.8 % (black tee) |
| A. Kept own, mean of 5 | 99.9 % | 85.0 % | 97.7 % |
| B. Strangers ranked first, all pairs | 60.1 % | 54.3 % | **65.9 %** |
| Lab clips: blue target ranked first | 14–26 % | 97–99 % | **97–99 %** |
| Lab clips: grey target ranked first | 88–99 % | 97–99 % | **97–99 %** |

- **Why the histogram alone fails:** hue is noise on black, grey, beige and sun-bleached white.
  - The black tee's histogram moved between frames, and the guard then refused to learn it.
  - Cb/Cr is steady on such tops but fails on a blue top in shade.
  - Half of each kept the strengths of both (`variants_heldout.py`, `results_variants.txt`).
- **Caveat: half-and-half was chosen after seeing the held-out results.**
  - Five variants were tried, and the half-and-half mix is the plainest of them.
  - So the held-out clips are no longer fully unseen. Robot-day E4 data is the real test.
- **"Strangers" is a harsh, artificial test.**
  - The stranger comes from another clip with other light and another camera position.
  - No colour model separates the lab's dark grey top from the black tee (21–35 %) or the patterned
    shirt (2–4 %).
  - On the robot the bearing and range gate decides in such cases.
- **The real second person in `farm_beige_1`** was never ranked above the target by any of the three gate models.

### In the robot

- **Camera:** `ros2_yolo_live.torso_hs_hist` appends 48 values to `/target_centroid_sector`. Readers
  of the first five values are unaffected.
- **Gate:** `TargetGate` with `hist_weight` 0.5. With no histogram, Cb/Cr counts in full as before.
  `use_hs_hist:=false` turns the histogram off.
- **Twin:** draws a matching histogram from the observed chroma on its own random stream. Every other
  twin value is bit-identical to before, checked open-loop over all scenarios with and without
  realism. Two new scenarios form the `colour` set, apart from the frozen identity set:
  - `shade_crossing`: a grey-top person crosses in deep shade in front of a blue-top target;
  - `shade_side_by_side`.
- **Gate replay** (`gate_replay.py`, `results_gate_replay.txt`) gives the same numbers as the offline
  model.

## Third set: a public crowd video (OpenCV `vtest.avi`, PETS 2009 S2.L1 view 1)

- **Why this video.** No other videos are on any branch. MOT Challenge and Hugging Face are blocked
  by this environment's network policy, but `raw.githubusercontent.com` is not.
  - `vtest.avi` is OpenCV's sample of PETS 2009 S2.L1: 795 frames, 10 fps, 768 × 576.
  - The camera is high and static, the day is overcast, people are small (boxes about 70–85 px tall),
    and about six are in view at once, mostly in dark clothes.
  - It is a much harder and different domain from a robot's camera at 1 m.
  - The video is not copied into the repository. Detections, labels and H,S samples are
    (`*_vtest.*`).
- **Labels.** Boxes were linked into tracklets (static camera), but the links swap people. Every
  tracklet was viewed every 6th box and split where the person changed.
  - Five people with recognisable clothes were named: RN (red/navy puffer), LB (light blue jacket),
    BL (blonde, black coat: the hard case, whose torso is as dark as most others), RD (red top) and
    BJ (blue jacket).
  - Everyone else is O. Thirty boxes where two tracklets overlapped on one named person are X (left
    out).
- **Replay** (`vtest_eval.py`, `results_vtest.txt`).
  - Each visit of a named person (a gap > 2 s ends it) is replayed on its own, colour only.
  - It locks on the visit's largest box that lies fully inside the image within its first 2 s.
    Locking on the first box, often half outside the image, gave every method a wrong reference.
  - Score: in frames with the person and someone else in view, how often the person scores best.
    Chance is 17 %.

| Person | Cb/Cr | Histogram alone | Histogram + Cb/Cr (0.25) | GMM H,S N = 10 |
|---|---|---|---|---|
| RN red/navy puffer | 1.4 % | 83.6 % | 62.9 % | 0.0 % |
| LB light blue jacket | 97.8 % | 98.9 % | 98.9 % | 0.0 % |
| BL blonde, black coat | 40.3 % | 53.2 % | 53.4 % | 19.2 % |
| RD red top | 3.5 % | 58.1 % | 6.1 % | 6.8 % |
| BJ blue jacket | 100 % | 100 % | 100 % | 100 % |
| **All** | 25.9 % | **69.8 %** | 52.8 % | 13.1 % |

- **Why Cb/Cr fails here, even on a red top.**
  - The torso region is about 10 × 24 px, so the red top's Cr swings between 151 and 196 from frame to
    frame.
  - Locked on Cr 151, the distance to a grey person (128, 134) is smaller than to the same red top at
    its full red. Grey sits between the weak and the strong reading.
  - Hue does not have this problem, so the histogram alone does best.
- **The GMM did worse than chance.** Small crops leave too few pixels, and the model drifts. This is
  the GMM as built here (our acceptance threshold), not the paper's.

## Choosing the histogram's weight (`weight_sweep.py`, `results_weight_sweep.txt`)

The same gate is used with only `hist_weight` changed.

| hist_weight | Lab, worst of 4 ranked | Held-out kept own, worst / mean | Strangers ranked | vtest ranked, all |
|---|---|---|---|---|
| 0 (Cb/Cr only) | 13.7 % | 99.7 / 99.9 % | 60.1 % | 25.9 % |
| **0.25 (adopted)** | **96.9 %** | **99.7 / 99.9 %** | **65.9 %** | 52.8 % |
| 0.5 (first choice) | 96.9 % | 89.8 / 97.7 % | 65.9 % | 53.9 % |
| 0.65 | 96.9 % | 67.3 / 91.5 % | 65.9 % | 54.1 % |
| 0.75 | 96.9 % | 55.8 / 88.8 % | 71.6 % | 75.2 % |
| 1.0 (histogram only) | 96.9 % | 37.4 / 85.0 % | 54.3 % | 69.8 % |

- **0.25 keeps every held-out person as well as Cb/Cr alone does** and keeps the full lab-clip gain.
  It gives up 1.1 points on the crowd against 0.5.
- **More histogram helps the crowd but loses the black tee.** For a follower, losing its own target is
  worse than ranking a stranger second.
- **Caveat:** 0.25 was chosen after seeing every set, so no unseen video is left. Robot-day E4 is the
  real test.
- **The re-acquisition threshold was re-derived for the smaller colour costs:** 1.0 lets 79 % of the
  target's boxes and 2.2 % of others' through. At 0.5 the matching threshold was 2.0.
- **By design, at 0.25 colour alone cannot reject someone standing exactly where the target is
  predicted:** the histogram adds at most 6.25 of the 9 budget. A small miss in bearing or range
  together with a different colour does reject.
