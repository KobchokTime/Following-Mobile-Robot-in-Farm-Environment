# E6 series: stopped after the first run (wrong-direction turn at ≥ 0.9 m)

Setup: cloud coordinator's E6 plan, approved by the operator, in **edge** steering
(`steer_mode=sector`, `front_band_radius=2`, `wide_front_radius=2`, so turns happen only in S0–S1/S7–S8)
with `target_distance` 1.0 m. Before the bridge came up:
- the image-free session bag `20261115T060903Z_e6_session` was started;
- `lidar_health` passed at 81 %;
- `preflight --live` reported ready with 0 FAIL.

The operator confirmed in writing: nobody else within 3 m, the rear clear, and a spotter on the e-stop.
Per-run check: [`e6_check.py`](e6_check.py). It compares the turn sign with the side of the largest
YOLO box, not with the fused target.

## Runs

| Bag | Result |
| --- | --- |
| `20261115T061413Z_e6_straight_1` | no person in view (0/203 frames); the 5 s countdown was too short. Retake |
| `20261115T061538Z_e6_straight_1` | no person in view (0/185, 15 s countdown); the operator was not at the robot. Retake |
| `20261115T061932Z_e6_straight_1` | 2/189 frames with a person, fused 0.50 m, cmd vx −0.61 to −0.66, wz +0.8. The robot had already turned away before recording started (below) |

## What happened (session bag, t from 06:18:55 UTC)

| t | Camera person bearing | Fused target | Command |
| --- | --- | --- | --- |
| 7–22 s | +2 to +15° | 0.83–1.30 m, same bearing | holds range, no turn: correct |
| 23 s | +23° (S1) | +24° | turn left 0.8: correct |
| 24 s | **−1.9° (centre)** | **+35° (left edge, LiDAR track)** | turn left 0.8: **wrong** |
| 25 s | **−30.5° (right, S8)** | **+35°, 1.10 m** | turn left 0.8: **wrong direction at ≥ 0.9 m** |
| 26–28 s | lost | LiDAR track at +17 to +25° | still turning left |
| 29–73 s | no person | none | stopped |
| 74–85 s | person at +30° then −28° to −18° | 0.50 m, +24° then −14.5° | reverse −0.66 to −0.75, wz +0.8. Front clearance 0.12–0.26 m, probably the operator turning the robot by hand |
| 86–92 s | −12 to −18° | 1.15–1.20 m | forward 0.4, no turn: correct |

The fused range never dropped below 0.50 m. The largest commanded reverse was −0.75 m/s, which the bridge caps at 0.5 m/s.

## Failure mode (same as `follow_first_short` at t = 1.6 s)

When the person moved quickly to the left, the target track was carried by LiDAR. It moved onto
another cluster on the left. Sync_fusion then kept publishing that track at the image edge (cx = 0,
+35°). It did not accept the camera box of the real person at the centre (t = 24 s) or on the right
(t = 25 s). Those boxes failed the target gate against the track's prediction. The controller turned
left at the full rate, away from the person. Edge steering does not prevent this, because the
wrong target sits in S0, which is a turn zone.

No code or parameters were changed after the stop. Next steps are for the coordinator and the
operator: review the LiDAR-assist / track-at-edge path in `sync_fusion_node.py`
(`assist_with_lidar`, `track_with_lidar`) and the gate's rejection of a centred camera box while the
track is LiDAR-only. Run it in the twin before the next robot day.
