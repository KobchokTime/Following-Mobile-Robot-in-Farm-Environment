# LiDAR mount change — 2026-11-15, site01

| | Before (to 2026-11-07) | Now |
| --- | --- | --- |
| Scan-plane height above ground | ~0.10 m (static TF `base_link→laser` z = 0.10) | **~0.70–0.73 m** (operator tape measure) |
| Reason | — | At leg height one person showed up as two returns (two legs). The camera bearing points at the body centre, which can fall in the gap between the legs. |

The operator reported the change before any recording on 2026-11-15. Checks on the robot, with the
bridge off (raw snapshots in [`lidar_mount_check/`](lidar_mount_check/), script
[`lidar_mount_check.py`](lidar_mount_check.py)):

- [x] **Yaw: changed by 6.2°.** The person stood on the robot's centre line in a clear scene. At
  ~1.6 m the camera said +1.5° and the LiDAR blob centre −4.7°. At ~3.8 m the camera said −0.4° and
  the LiDAR −6.6°. The 6.2° difference is the same at both distances, so it is yaw, not
  camera–LiDAR parallax. With offset 0, fusion at 3.8 m read **24.6 m**, because the camera bearing
  landed beside the person on the glass door. Applied `lidar_angle_offset_deg:=6.2`, which
  `~/start_follow.sh` passes to all three nodes. Re-check at ~3.7 m with the offset: the LiDAR blob
  centre is −0.3° and the camera −2.4°, so they agree within ~2°. Sync_fusion's `box_range` gives
  3.62 m (76/77 frames).
- [x] Level: in the clear scene, straight ahead read the far wall at ~6.4–6.6 m with no floor returns.
- [x] Self-hits: no beam closer than 0.35 m in any healthy scan.
- [x] Person standing, at ~1.6 m: **one** blob from −14.5° to +5.1° (0.54 m wide, including the
  hands at hip height), with a ~5 cm dip between the thighs and no see-through gap. Fusion distance
  was 1.533 m.
- [x] **Person walking: no leg split.** Run `20261115T041011Z_lock_walkback_3p8`: lock on at
  ~1.1 m, walk back along the centre line to ~3.4 m, then stand. Analysed with
  [`walk_shape.py`](walk_shape.py), counting returns within 0.4 m sideways and 0.45 m in range of
  the fused target:
  - **Tracking:** 76 `/synced_target` messages in 14 s. Range rose smoothly from 1.12 m to 3.37 m,
    bearing stayed within ±3°, with no dropouts.
  - **Standing at 3.2–3.4 m:** one cluster in 50/55 scans, 0.40 m wide.
  - **Walking at 1.2–3.2 m:** 47/78 scans had a second cluster. Every one was a small return
    (0.03–0.08 m) about 0.2 m in front of a 0.32–0.43 m body cluster, i.e. a swinging hand. None
    was two similar-sized clusters (legs). The fused range did not jump, because `box_range` takes
    the cluster under the box bearing.

**Lock-on window (by design, `sync_fusion_node.py:207`):** fusion first locks only on a person
0.5–1.0 m away within ±15°. It then tracks them outward, and unlocks after 5 s without a fix. To
start following, stand ~0.7 m in front for ~2 s, then walk off. Started from 3.8 m, nothing is published.
- [ ] Obstacle stop with an object tall enough to cross the scan plane

## Incident: LiDAR driver started degraded

After a pipeline restart (about 11:00 local time), `/scan` held only 66–78 of 364 beams valid per scan, about 18 %.
The healthy rate is about 85 %. The remaining beams were scattered phantom ranges (0.3–10.7 m). The
person at 3.8 m was not seen, and fusion read 0.28–0.49 m. `follow_stop` logged `dist=0.60m … → v=(0.21, 0.00)`.
Nothing moved, because the bridge was off. Restarting the pipeline restored 85–86 % valid beams.
The cause is unknown.

**Rule from now on:** run [`lidar_health.py`](lidar_health.py) after every pipeline start. It passes
at ≥ 70 % valid beams and ≥ 7 Hz. Do not enable the bridge on a FAIL.

## Consequences

- **Obstacle stop sees only objects that reach the scan plane (≈0.7 m).** Bottles, buckets, stones, pipes,
  bed edges and anything else lower are invisible to the LiDAR, so the robot will not stop for them.
  The 2026-11-07 bottle stop test (0.43 m) does not carry over to this mount.
- 0.70–0.73 m is about upper-thigh height for an adult. Thighs are closer together than shins, but
  during a stride they may still give two returns. Torso height would be about 0.95–1.1 m. The
  person-shape check above decides whether this height is enough.
- The static TF `base_link→laser` z must change from 0.10 to the measured height, so that maps and TF
  match.
- E1 from today on measures this mount. Do not pool it with leg-height data.
