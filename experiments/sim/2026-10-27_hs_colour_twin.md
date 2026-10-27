# H,S colour histogram and colour re-acquisition in the twin

- **Date:** 2026-10-26 to 27.
- **Code:** branch `claude/robot/hs-colour`, at `2547f8b`. It is **not merged**.
- **What it adds**, as in `experiments/identity/clothing_colour_videos/README.md`:
  1. The camera sends a torso H,S histogram.
  2. `TargetGate` weighs histogram and Cb/Cr half each.
  3. A lost target is taken back by colour near its predicted bearing (Kim, Suh and Kwon 2024,
     Algorithm 1).
- **Twin:** the histogram is drawn from the clothing colour, with saturation scaled by
  `0.6 + 0.4 × shade`.
  - It was calibrated on the lab video, where a blue top in shade stayed about 0.57 (Hellinger) from
    itself in light. Here deep shade gives about 0.5.
  - Every other twin value is bit-identical to before. This was checked open-loop over all scenarios,
    with and without realism.
- **Scenario set `colour`** (separate from the frozen identity set). In both, the target wears blue
  and the other person dark grey:
  - `shade_crossing`: the other person crosses in front of the target in deep shade (0.3);
  - `shade_side_by_side`: the two start side by side in shade.
- **Runs:** `mps`, one job at a time. Pass means: target in view at the end, gap ≤ 1.5 m, no contact,
  and target in view for ≥ 90 % of the run. Data: `2026-10-27_hs_colour_twin.json`.

## Results (`2547f8b`)

| Set | Histogram off (Cb/Cr only) | Histogram on |
|---|---|---|
| `shade_crossing`, clean, seeds 0–9 | 10/10 | 10/10 |
| `shade_crossing`, realism, seeds 0–9 | **5/10** | **10/10** |
| `shade_side_by_side`, clean, seeds 0–9 | 10/10 | 10/10 |
| `shade_side_by_side`, realism, seeds 0–9 | 10/10 | 10/10 |
| Identity (5 scenarios), realism, seeds 0–2 | 15/15 | 15/15 |
| Solo (14 scenarios), realism, seeds 0–2 | 26/30, 1 contact | **29/30, no contact** |
| Solo, realism, `steer_mode:=bearing` | — | 29/30, 1 contact (`come_back` s2, the known question) |
| Identity, realism, `steer_mode:=bearing` | — | 15/15 |

- **Solo failures:**
  - histogram off: `side_step` s0 and s1, `zigzag` s0, and `come_back` s1 (contact);
  - histogram on: `zigzag` s2.
- These are the known out-of-view moves and vary from run to run.

## How the `shade_crossing` failure was found and fixed

1. **The first twin histogram was too pessimistic.**
   - It was drawn from the shaded Cb/Cr, so deep shade moved it 0.84 from the same top in light.
   - The gate then dropped the target in shade: 1 of 3 runs passed (`f28b011`/`a936d3f`).
   - Cb/Cr shrink with brightness, and HSV saturation does not. Fixed in the twin (`34fdcdf`).
2. **The remaining failure belonged to the old gate, with or without the histogram.**
   - Seen in 2 of 14 runs with Cb/Cr only and 1 of 23 with the histogram (`34fdcdf`). Gate decisions
     were logged with a debug copy of `sync_fusion` (not committed).
   - What happened:
     1. The LiDAR range behind the target's box read the crosser in front (0.38 m).
     2. The crosser was then accepted: cost 8.0 < 9, because Cb/Cr saw only 1.5 between a blue top
        in shade and a grey one.
     3. The track's rates ran to −30° and a range of −0.27 m, and the real target was rejected from
        then on.
     4. After the 5 s unlock, it could only be locked again at 0.5–1.0 m, so the robot stood still.
3. **Fix (`2547f8b`):** take the target back by colour once it has been unseen for 1 s.
   - The match must have colour cost ≤ 2.0, lie within 35° of the predicted bearing, and may be at
     any range. Only with a histogram.
   - The 2.0 is from the seven videos: 81 % of the target's boxes pass, against 2.7 % of other
     people's.
   - With the histogram the crosser's colour cost is about 12, so it is not accepted in the first
     place.

## Limits

- **The twin's histogram is synthetic.** These runs show the code works end to end and does no
  harm. They are not evidence of how well colour separates people. That evidence is the video work,
  and E4 on robot day is the real test.
- **Same-colour tops:** colour cannot help; geometry alone decides, as before.
- **Not run:** Gazebo.

## Update: histogram at a quarter weight (`47553e5`)

- **Change:** after the weight sweep over all video sets
  (`experiments/identity/clothing_colour_videos/README.md`), the gate uses `hist_weight` 0.25 and
  `reacquire_colour_max` 1.0.
- **Rerun:** the same 215 runs. Data: `2026-10-27_hs_colour_twin_w025.json`.

| Set | Histogram off (Cb/Cr only) | Histogram on, 0.25 |
|---|---|---|
| `shade_crossing`, clean, seeds 0–9 | 10/10 | 10/10 |
| `shade_crossing`, realism, seeds 0–9 | 9/10 | **10/10** |
| `shade_side_by_side`, clean and realism | 10/10, 10/10 | 10/10, 10/10 |
| Identity, realism, seeds 0–2 | 15/15 | 15/15 |
| Solo, realism, seeds 0–2 | 24/30, 1 contact (`come_back` s1) | **27/30**, 1 contact (`come_back` s2) |
| Solo, realism, `bearing` | — | 28/30, no contact |
| Identity, realism, `bearing` | — | 15/15 |

- **Same picture as at 0.5:** colour does no harm in the twin, and helps when a crossing person is in
  shade.
- **Run-to-run variation is large:** with the histogram off, `shade_crossing` with realism went 5/10
  in the previous run and 9/10 now, on the same code for that setting.
