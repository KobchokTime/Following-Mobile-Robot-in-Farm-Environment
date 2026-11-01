# Twin after the T18 re-review fixes — 2026-11-01

Code `9b29cc7` on `claude/workspace` answers Codex's T18 re-review (07:49 and 09:52 Thai time). The full twin
run used 22 scenarios × seeds 0–4, the realism profile and the mps bridge, one run at a time. The image id
and per-run rows are in `2026-11-01_twin_t18_review.json`.

| Code | Passed | Contacts | `blind_corner` | `pass_by` | Every other scenario |
|---|---|---|---|---|---|
| `bdae2c1` (hub `8b2ddf8`), run 1 | 110/110 | 0 | 5/5 | 5/5 | 100/100 |
| `bdae2c1`, run 2 (`2026-11-01_twin_110_repeat.json`) | 109/110 | 0 | 4/5 | 5/5 | 100/100 |
| **`9b29cc7` (this change)** | **105/110** | **0** | **0/5** | **5/5** | **100/100** |

## What changed

1. **The trail pose moves without target messages.**
   - The wheel-speed estimate is now stepped in `trail_tick` as well as `cb_fused` (`update_wheel_speed`).
   - Before, the dead-reckoned pose stayed still while the robot drove on.
2. **Avoid and trail are never faster than the follower asks.**
   - The rule is `min(max(0, asked), path cap)`. The path cap is the way left along the path, with a braking cap.
   - There is no 0.12 m/s floor under a slower request, and a zero request stays zero.
3. **No driving on the trail without target messages by default.**
   - `trail_hold_s` is 0. The 3 s hold is kept only as an offline experiment.
4. **The obstacle stop and fusion are wired together.**
   - `sync_fusion` takes `obstacle_stop`. When it is false, the occlusion range and the give-way floor are off.
   - `follow_bringup.launch.py` passes one `obstacle_stop` argument to both nodes. `avoid_trail` is off by
     default on the robot.
   - `tools/robot_day/preflight.py` fails if `obstacle_stop` is off or `trail_hold_s` is above 0. It warns if
     `avoid_trail` is on.
5. **Callback tests through the production `send`, `cb_scan` and `trail_tick`:**
   - pose progress without messages;
   - no trail turn with the spin circle occupied;
   - a published trail turn stopped by the next scan that fills the spin circle;
   - a stop on a stale scan and at hold expiry;
   - zero speed for a zero request, and an immediate stop with the default hold;
   - preflight and launch configuration tests.

`scripts/check.py`: 236 tests pass.

## Result

- **`blind_corner` fails on every seed.**
  - Four runs are in view 0.871–0.893 against the 0.9 rule.
  - In one (s2) the robot lost the target, with a final gap of 2.78 m.
- **Why:** the passes on `bdae2c1` came from driving on along the target's path faster than the follower asked
  and from driving 3 s without target messages. Both are now off.
- **`pass_by` and every other scenario still pass, with 0 contacts.**

This is the expected cost of the safety rule, not a new fault. `blind_corner` stays a recorded failure. Codex's
design call stands: do not shrink the 0.40 m spin circle until the chassis is measured, and keep the 0.9 rule.

## The robot-day configuration (code `6a64669`)

Codex noted (T18, 12:45 and 12:49) that the 105/110 run used the node's own default `avoid_trail=true`, while
the robot launch sets it false.

`6a64669` sets the node default to false. Every other value the launch passes already equals the node
default, so a default twin run is now the robot-day configuration: `obstacle_stop` true, `avoid_trail` false,
`trail_hold_s` 0. Full run, same protocol; per-run rows are in `2026-11-01_twin_robot_day_settings.json`.

| Code | Settings | Passed | Contacts | `blind_corner` | Every other scenario |
|---|---|---|---|---|---|
| `9b29cc7` | trail on (node default then) | 105/110 | 0 | 0/5 | 105/105 |
| **`6a64669`** | **robot-day: trail off** | **106/110** | **0** | **1/5** | **105/105** |

- **`blind_corner` with the trail off.** Three seeds lost the target (final gap 2.0–2.96 m, in view 0.33–0.41),
  s4 was in view 0.893, and s3 passed. The closest approach to the bystander was 0.527–0.66 m, with no
  contact.
- **`pass_by` passes 5/5** with the worker passed at 0.547–0.568 m.

`blind_corner` stays a recorded failure in the robot-day configuration as well.

`preflight.py --live` now reads the running values back with `ros2 param get`:
- `/follow_stop_node`: `obstacle_stop`, `avoid_trail`, `trail_hold_s`;
- `/sync_fusion_node`: `obstacle_stop` (the fusion node's ROS name is `sync_fusion_node`).
