# Identity belief (recursive Bayes) in the target gate: tried, not adopted

- **Date:** 2026-10-27.
- **Code:** branch `claude/robot/identity-belief`, built on `claude/robot/hs-colour` (`47553e5`).
  - It is **not merged**.
  - `identity_belief` defaults to false. When off, the gate behaves exactly as on `claude/robot/hs-colour`.
- **Why it was tried.**
  - The code had no Bayesian part, only nodes named "Bayesian" (`fusion_prob`'s weighted score, `follow_stop`'s
    sector hysteresis). Those comments are fixed on `claude/robot/naming` (`27fb26d`).
  - The user chose to try a real but light Bayesian piece (option 2 in the discussion on 2026-10-27): a belief that
    the box the gate takes is still the person it locked on.

## What was built

- `TargetGate.belief` is updated by Bayes' rule each time the gate accepts a box.
  - A small switch probability between boxes: `belief_switch` 0.01.
  - Likelihood ratio, target : nearest other person, from two parts:
    - **Geometry:** χ²(2) for the target against uniform over the gate, held to 0.3–1.5. The gate has already used
      geometry to take the box, and switches happen when people are close, where geometry says little.
    - **Colour:** a table of cost → ratio measured on the labelled videos (`COLOUR_LR`, from
      `experiments/identity/clothing_colour_videos/separability.json` at `hist_weight` 0.25): 3.8 at cost 0,
      1.0 at 1, 0.2 at 3 or more.
- With `identity_belief:=true`: below `belief_low` 0.15 the gate stops taking boxes on geometry and waits for the
  colour re-acquisition (Algorithm 1). `sync_fusion` logs `[BELIEF]` on each change.
- Unit tests: belief stays high on the target, falls on another colour, the gate waits and takes the target back.
  131 tests pass.

## Results

### Labelled videos (colour only, leave one clip out)

Scripts: `experiments/identity/clothing_colour_videos/belief_eval.py`, `belief_sweep.py` and `belief_signal.py`,
with their `results_belief_*.txt`.

| | Belief off | Belief on |
|---|---|---|
| Wrong takes, mean of 14 cases | 29.2 % | **20.0 %** |
| Target kept, mean | 100 % | **87.0 %** |
| Target kept, worst case | 100 % | **10.9 %** (red top in the crowd) |

- **No threshold avoids dropping the target** (`belief_low` 0.02–0.15, `belief_switch` 0.003–0.01). The best
  worst case is 63.5 %.
- **As a report-only signal the belief does not tell wrong takes from right ones:** AUC 0.50 over all cases.

### Twin (`mps`, realism, identity belief on)

Data: `2026-10-27_identity_belief_twin.json`. The comparison is with the same branch with the belief off
(`2026-10-27_hs_colour_twin_w025.json`).

| Set | Belief off | Belief on |
|---|---|---|
| `shade_crossing`, seeds 0–9 | 10/10 | **1/10** |
| `shade_side_by_side`, seeds 0–9 | 10/10 | 9/10, 1 contact |
| Identity, seeds 0–2 | 15/15 | 15/15 |
| Solo, seeds 0–2 | 27/30 | 28/30 |

- **What happens in `shade_crossing`** (from the `[BELIEF]` log):
  1. When the target walks into deep shade, its colour cost rises, and the belief falls below 0.15.
  2. The gate then waits for a colour match.
  3. In shade the colour never comes within the re-acquisition threshold.
  4. After 5 s the gate unlocks, and it can only lock again at 0.5–1.0 m.
- A log wording bug was found here: the unlock was logged as "target taken back". Fixed in `6102615`
  ("not taken back: gate unlocked").

## Why it does not work

- **The belief rests on the same colour evidence the gate already uses to choose the box.**
  - When the gate takes the wrong person, it is because that person's colour looks more like the target's. The
    belief then rises with it.
  - When the target's own colour changes (shade, a black tee, a tiny crop), the belief falls on the right person.
- **Bayes' rule combines evidence, but cannot add evidence that is not there.**
  - To help, the belief needs a cue independent of colour, for example the target's LiDAR track continuity, or a
    second appearance cue.
  - It also needs to know when colour is uninformative for this target (the colour-reliability idea).

## Conclusion

- **Keep `identity_belief` off.** The branch stays as a measured negative result.
- **For the thesis:** a recursive Bayes identity belief on colour evidence was tried and measured, and did not help.
  This is a useful contrast with the paper's particle filter, which also has a dedicated non-target tracker and a
  gazing camera.
