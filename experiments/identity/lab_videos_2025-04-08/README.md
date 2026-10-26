# Clothing colour on two lab videos (2025-04-08)

- **Date of analysis:** 2026-10-26.
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
