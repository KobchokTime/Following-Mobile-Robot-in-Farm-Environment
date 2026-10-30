# LiDAR map: obstacle stop, avoid, and LiDAR assist (twin at 100% on the baseline set)

- **Date:** 2026-10-29.
- **Branch:** `claude/robot/avoid`. Final code `546bd57`. It merges `claude/robot/lidar-assist2` (`458d4d0`) and
  `claude/robot/obstacle-stop` (`c0be756`) and adds the avoid.
- **Data:** `2026-10-29_lidar_avoid.json`, 210 rows: the baseline (hub `5c72c4d`, 100 runs) and the final
  code (110 runs). Runner: `scripts/run_baseline.sh` (every scenario, realism, `mps`, one run at a time).
- **Pass rule (set before the runs):** target in the camera's view at the end, final gap ≤ 1.5 m, no contact
  (< 0.40 m centre to centre with anyone), target visible ≥ 90 % of the run.

## Result

| Set | Baseline `5c72c4d` | Final `546bd57` |
|---|---|---|
| The 20 baseline scenarios × s0–4 | 98/100 (`zigzag` 3/5) | **100/100** |
| `pass_by` (new) | — | 5/5 |
| `blind_corner` (new) | — | 0/5 following, **no contact** |
| Contacts, all runs | 0 | **0 in 110** |

## The three parts (all in `follow_stop_node` or `sync_fusion_node`)

1. **Obstacle stop** (`obstacle_stop`, default on). Anything the LiDAR sees in the robot's corridor,
   other than the target, caps the speed so the robot stops 0.45 m short of it.
   - The corridor is ±0.30 m (robot 47 cm wide, thesis slides) and bends with the turn. Alongside the
     body (0.26 m ahead of the LiDAR) only the body's own ±0.235 m counts, so a person level with the
     robot is beside it, not ahead.
   - Returns within 0.30 m of the target's point are the target.
   - Every scan re-checks the last moving command, so a command left running after the target messages
     stop (a single false box) still slows for whoever steps in.
   - No fresh scan: no motion.
2. **Avoid** (`obstacle_avoid`, default on). When something other than the target has blocked the straight
   path to the target for 1 s (`avoid_delay_s`), the robot aims at a point beside the target. It takes the
   smallest clear shift in 0.1 m steps, within 0.5 rad of the target, on the side already taken, steers
   there by bearing, and keeps the shift 0.5 s after the path clears. No clear shift: the stop alone.
   - Someone walking across is gone within the delay; the robot waits for them instead of going round.
3. **LiDAR assist** (`lidar_assist`, default on). Each scan moves the target track to the target's own
   cluster, which fixed `zigzag`: the robot's own turn swept the target's bearing faster than the gate's
   prediction.
   - It never takes a cluster 0.2 m nearer than the predicted range (someone covering the target) or one
     farther from the last fix than 1.5 m/s allows.
   - It pauses while the gate's ambiguity window is open (someone was just near the target).

## How the rounds went (each a twin run, then a fix)

| Round | Finding | Fix |
|---|---|---|
| Stop v1 `4f573e8` | `blind_corner`: stop on 1/5 contact, off 1/5. One false box set 0.5 m/s, then messages stopped. | Per-scan re-check; exclusion 0.45 → 0.30 m (`c0be756`): on 0/5 contact, off 2/5. |
| Assist `3cae4f3` | `zigzag` fixed, but `crossing`/`shade_crossing` 9 failures, 4 contacts: a passer-by covering the target. | Nearer-than-predicted and walking-speed rules (`9cb32f2`). |
| Avoid v1–v3 | Swerve arcs fought the sector steering; `pass_by` 4/5, then 5/10. | Aim beside the target (`dcd58e0`): 8/10. |
| Avoid v4 | Level with the worker the robot stopped for good. | Body-length flank rule (`f6373c4`): `pass_by` 10/10. |
| Full run | 94/100: avoid went round people crossing; assist still followed a crosser. | 1 s avoid delay (`b618b40`); attribution runs showed the assist (assist off 3/3, assist alone 1/3); assist waits out the ambiguity window (`458d4d0`). |

## After the T18 reviews (`claude/workspace` `a4ce8a5`)

- **Changes:** the per-scan re-check acts only within `recheck_max_s` (1.0 s) of the command it lowers, and a
  stop zeroes the turn (integration review). A command that does not move forward or back turns in place
  only with a fresh scan and nothing but the target within `spin_clear_radius_m` (0.40 m). `/scan` is
  subscribed best effort (`qos_profile_sensor_data`) (Codex review).
- **Full twin run** on `a4ce8a5` (22 scenarios × s0–4): 104/110, **0 contacts**. Baseline set 99/100: `zigzag` s1
  lost the target (visible 0.25) after an overshoot as the target crossed; no turn was held back at the time.
  A re-run of `zigzag` s0–9 on the same image: **10/10** (s1 passes, visible 1.0), so that failure is run-to-run
  variation, not the change. `blind_corner` 0/5 following, no contact (min 0.53 m).
- **Near spins** (`f57d624`, integration's probe): a creep (|v| ≤ 0.05 m/s) or an arc tighter than 2/m is checked
  against the spin circle too; refused, the turn is dropped and the corridor-checked straight creep kept. Full
  twin run: **107/110, 0 contacts**; baseline set **100/100**; `pass_by` 5/5; `blind_corner` 2/5 (s2, s4 pass;
  the rest stop without contact, min 0.59 m).
- The twin publishes `/scan` reliably, so it cannot test the QoS change; check on the robot that `follow_stop`
  receives `/scan` (`[OBST]` lines appear, or `ros2 topic info /scan --verbose`).

## Not shown

- **`blind_corner` still loses the target.** The bystander stands 0.45 m from the target's path at the
  corner, so a 47 cm robot cannot follow through. It stops safely (no contact in 15 runs across the
  rounds) and the target walks beyond the 3 m reacquire limit. Passing needs a planned path round the
  corner, not a reactive shift.
- **Twin people are circles; the bystanders here are hidden from the camera.** Real legs, crop rows and
  someone the camera does see (the give-way in `sync_fusion` then applies too) are for robot day.
- **`wheel_radius_m` 0.085 vs the slides' Ø13 cm front wheels** is unconfirmed; it scales every speed.

## Next

- [ ] Integration review and merge into `integration-hub`.
- [ ] Robot day: `[OBST]`, `[AVOID]` and `clr=` in the `follow_stop` log with a post and a crouched person.
