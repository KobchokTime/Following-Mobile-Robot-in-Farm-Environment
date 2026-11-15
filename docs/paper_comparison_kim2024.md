# Comparison with Kim, Suh and Kwon (2024)

**Paper:** J. Kim, I. H. Suh and T. Kwon, *Multi-modal Bayesian Learning, Re-identification and
Tracking of a Target Person for Mobile Robots*. Preprint submitted to Elsevier, SSRN 4927941 (2024).
It has **not been peer reviewed**; cite it as a preprint.

The user's copy is stored on `codex/robot-backup-quarantine` under `Paper/` (Git LFS). The PDF is not
copied anywhere else in the repository.

## What the paper does

The pipeline has four steps: detection, learning and identification, tracking, and following.

| Part | Method |
|---|---|
| **Target appearance (§3)** | Temporal interval sampling: the target's hue and saturation pixels over the last N frames, without V because V reacts most to light. A Gaussian mixture is fitted by EM, and k is chosen by BIC. The model is re-learned online (N = 10 proposed). |
| **Re-identification (Algorithm 1)** | When the target is lost, each detection is scored by the colour model. A detection above 0.5 that lies near the target's last predicted position becomes a candidate. |
| **Dynamic non-target detector (§4.1, Fig. 5)** | The scan at t−N is ICP-matched with the current scan, **using wheel odometry as the initial guess**. Points that do not match are segmented into objects and added to a candidate vector. Static objects are filtered out. What is left goes to the tracker. |
| **Data association (§4.2)** | Global nearest neighbour on cluster centroids, with an average-velocity time-interval model. |
| **Fusion and tracking (§4.3–4.4, "STnT")** | A particle filter over the target's position. The camera colour likelihood is a positive factor. Tracked non-targets from the LiDAR are a negative factor, `1 − p(z_laser | x)`, which pushes the target estimate away from them. A rotating "target gazer" camera keeps the target in view. |
| **Evaluation (§5)** | Identification states CT, CL, WT and WL (correctly or wrongly tracked or lost) over four sequences. An external rig of four LRFs measures E_dist, the distance between the predicted and the true target position. The robot was used at ROBOTWORLD Korea. |

## Our system against it

| Paper | Ours (`claude/workspace`) | Status |
|---|---|---|
| Colour model, GMM on H,S, re-learned online | Median torso Cb/Cr of the box. The target's reference adapts slowly (rate 0.05). It is a soft cost in the gate. | Simpler. Same idea of an illumination-robust chroma, but not a learned mixture. |
| Re-identification after loss | After 5 s unseen the gate unlocks and locks on in the start window (0.5–1.0 m, ±15°), whoever stands there. `src/following_robot/target_identity.py` is offline only. | **Not implemented** in the running pipeline. |
| ICP scan matching with an odometry guess | Branch `claude/robot/static-filter`: keyframe ICP, refreshed every second. The guess comes from `/cmd_vel` because the robot has no odometry yet. | **Implemented, off by default.** Twin results in `experiments/sim/2026-10-26_static_filter.md`. |
| Unmatched points → segments → dynamic objects | `StaticMap` flags clusters that stay put for 2 s. LiDAR tracking past the image edge skips them. | Same purpose, different test: per cluster over time, not per point between two scans. |
| Tracking non-targets (GNN) as a negative factor | The gate rejects non-targets. A rejected person in the corridor triggers give-way. Non-targets are not tracked. | Partial. |
| Particle filter (Bayes) | An alpha-beta track and gate, with a weighted confidence. Not Bayesian. | Different. Our thesis draft now says so. |
| Camera gazer | Fixed camera. The robot turns towards the target, and LiDAR tracking covers edge exits. | Different hardware. |
| Evaluation: CT/CL/WT/WL and E_dist with an external LRF rig | Twin and Gazebo pass/fail, gap and contact. On robot day, `analyze.py` reports E1–E6. | Their CT/CL/WT/WL states are worth borrowing (below). |

## What is worth taking from it

1. **Wheel odometry as the ICP guess.**
   - The paper uses it.
   - Our ZLAC8015D reports wheel speed. Reading it in the bridge would replace the `/cmd_vel` guess,
     which is wrong while the wheels ramp or slip.
   - It also matters where the field has few static features, which is where ICP falls back to the
     guess.
2. **The CT/CL/WT/WL states for E5 and E6.**
   - The twin knows the ground truth (target visible or not, and which person was followed), so these
     four states can be computed for every run.
   - On robot day they need a label of which person was followed, which the recorder note or video
     gives.
3. **The negative factor.** Pushing the target estimate away from tracked non-targets is the
   principled version of our give-way rule. It needs non-target tracks first.
4. **Online colour learning.**
   - Our E4 measures whether chroma separates two people.
   - If it separates them poorly in sun against shade, the paper's sliding-window re-learning (N ≈ 10)
     is the next step.

## Paragraph for thesis chapter 2 (draft)

> Kim, Suh and Kwon [preprint, 2024] combine a colour model with a 2D LiDAR to follow one person among
> others. The target's hue–saturation distribution is re-learned online as a Gaussian mixture, whose
> number of components is chosen by BIC, so identification adapts to changes in illumination. A
> dynamic-object detector ICP-matches consecutive laser scans, with wheel odometry as the initial
> guess. Points that fail to match are segmented into moving objects, which are tracked by
> global-nearest-neighbour association. A particle filter then weights the target position by the
> colour likelihood (positive) and by the tracked non-targets (negative). Our system follows the same
> division of labour on cheaper hardware: a monocular camera for identity, a 2D LiDAR for range and for
> people outside the camera's view. It replaces the learned mixture with a torso chroma reference and
> the particle filter with a gated alpha-beta track. We evaluated their scan-matching idea in
> simulation without odometry (Section 4.x).

Section numbers and citation style follow the thesis template. Add the paper to the reference list as
a preprint.
