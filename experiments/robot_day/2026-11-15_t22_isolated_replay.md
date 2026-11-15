# T22 recorded-data replay, 2026-11-15

This is an **offline ROS replay**, not a field trial or clearance for motion. The 2026-11-15
recordings are identified below by their bag names. The wrong-turn rule is the field
`e6_check.py` from `claude/test-ssh-humsai-67e424 @ 1713dac`: a turn above 0.05 rad/s opposite
the largest YOLO box's side (beyond 7.8 degrees), with fused range at least 0.9 m. It uses a
camera box rather than the fused track as the direction reference.

## Isolation and source

- The clean pre-fix control used robot nodes from `026fe17` (draft PR #19). The patched run used
  T22 robot code from `795514a` (draft PR #20). Both ran through the same bounded replay harness.
- Source and output were staged on RAM storage; the original SQLite bags were opened read-only.
  The replay started only `lidar_sectorizer`, `sync_fusion`, `fusion_prob`, and `follow_stop` on
  localhost-only ROS domain 187. The domain was checked empty before each field replay. No ZLAC
  bridge or live hardware driver was started, and no physical motor command was delivered.
- All three LiDAR consumers used the measured 6.2 degree offset and sign -1. The sectorizer's
  parameter names are `angle_offset_deg` / `angle_sign`; fusion and controller use
  `lidar_angle_offset_deg` / `lidar_angle_sign`. E6 additionally used target distance 1.0 m,
  sector steering, and front/wide band radii 2. The first-follow bag used target distance 0.5 m
  and default band radii 1.
- The E6 matched pair began 540 s into the session and ran for 95 wall-clock seconds, with no
  playback delay in the tested harness. The first-follow matched pair played the entire 23.7 s
  bag with a 3 s ROS subscriber delay. Replay output included `/yolo_frame`, `/synced_target`,
  and `/cmd_vel` for the checker. The later replay tool omits linear RMSE for truncated windows;
  the RMSE in the captured E6 `compare.json` files is **not time-aligned and must be ignored**.

## Results

| Recording and source | YOLO frames/person | Fused messages | Wrong-direction turns ≥0.9 m | Finding |
|---|---:|---:|---:|---|
| E6 original `20261115T060903Z_e6_session` | 4721/363 | 185 | 5 | Recorded failure; checker control |
| E6 pre-fix replay, 540–635 s | 632/304 | 128 | **5** | Reproduces the failure |
| E6 T22 replay, same window | 634/304 | 103 | **0** | Conflict stop at replay t=72.83 s |
| First original `20261115T041627Z_follow_first_short` | 152/128 | 145 | 5 | Recorded failure at t=1.7–1.9 s |
| First pre-fix replay, full bag | 152/128 | 105 | 0 | Does not recreate the early held track |
| First T22 replay, full bag | 152/128 | 106 | 0 | Non-discriminating result |

In the matched E6 replay, the pre-fix control still commanded +0.8 rad/s left while the camera
box was on the right at t≈73 s. The patched fusion log emitted `camera/LiDAR edge disagreement:
stop and relock manually`; `/synced_target` contained the explicit -1/-1 conflict marker at
t=72.83 s and `/cmd_vel` was zero at that timestamp. The controller did not continue the held
left turn. This is direct evidence for the E6 failure path, within replay timing limits.

The first bag is **not a convincing replay regression**: the pre-fix control also scores zero
wrong turns and reaches only 0.98 m fused range, whereas the original reaches 1.57 m at the
early wrong turn. The recording began with the live tracker already established, and a fresh
replay node cannot reconstruct that prior state from the bag alone. Its T22 result therefore
does not establish the two-bag criterion. The synthetic edge-conflict unit test covers this
state transition separately.

The new `fast_step_static_cluster` twin scenario ran once with realism and the mps bridge model
on the patched code (seed 0): no contact, 0.73 m travelled, final gap 4.09 m. The pre-fix control
on the same low-power host travelled 0 m, showing startup timing made this single-seed twin
comparison unreliable. The required robot-day 110 runs and five-seed T22 scenario have **not**
been validated. `python scripts/check.py` passed 254/254 offline tests on the updated branch.

## Evidence retention and next gates

Small derived replay bags, metadata, `compare.json`, and fusion logs were copied into a local
evidence bundle outside Git. The E6 control bag SHA-256 is
`9fed671c9f50a8581df062ac023f43ed4722eeae7cabc9e6ab7473dc7dba3d21`; the patched E6 bag is
`350dfc9c43997dbe9a4b14a223c9a13ada69d8d120b584c301b8a8a28757069e`. No original bag
or large recording was committed. The RAM test source and outputs may be removed after this
evidence is checked.

PR #20 remains draft. Before integration: run the 110-case robot-day twin and the T22 scenario
on a stable Linux ROS environment; obtain an independent safety review of identity/fusion/
controller behavior; and resolve the first-bag limitation or explicitly accept the synthetic
regression as its coverage. No physical following test is implied by this replay.
