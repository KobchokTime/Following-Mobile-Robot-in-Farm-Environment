# Bag replay: does scan-only SLAM track real motion? (2026-11-15 17:23–17:42)

The user OK'd this in chat ("Replay the bag"). The input was `/scan` (plus `/odom` kept only as a
reference topic) from the joystick bag `20261115T043413Z_slam_map_1115`, recording_0.db3 md5
`47a28d2eef6b0b991e480e22c098c6aa`. In the first 15.6 s the robot drives and spins; after that it
is stationary. The replay used `replay_scan_only.sh` on the robot in ROS domain 87, which is
isolated from the live graph. There was no LiDAR, no motors and no bag `/tf`: `odom→base_link`
was the mapping-only static identity, so the pose comes only from scan matching.

The pose reference comes from scan geometry only (`scan_pose_reference.py`, `reference_comparison.txt`):
- the last scans aligned directly onto the first: (0.47, −0.47) m, −185.5° (41% overlap; the next
  distinct peak is 21%);
- chained 0.5 s scan-to-scan alignments: (0.50, −0.53) m, −186.0°;
- reference = mean (0.48, −0.50) m, −185.8°.

| Source | Final pose | Position error | Heading error |
|---|---|---|---|
| wheel `/odom` (dead reckoning from commanded speeds) | (0.72, −0.31), −248.0° | 0.30 m | −62.2° |
| SLAM r1, params at the time (`minimum_time_interval` 0.3, `coarse_search_angle_offset` 0.349) | (0.47, −0.59), −158.4° | 0.09 m | +27.4° |
| SLAM r2, tuned (`minimum_time_interval` 0.1, `coarse_search_angle_offset` 0.524) | (0.48, −0.39), −181.8° | 0.11 m | +4.0° |

Result: mapping-only SLAM with no wheel odometry tracks the real motion. The tuned params (r2) are
now the defaults in `slam_params_mapping_only.yaml`. With the old params, heading was lost during
fast in-place spins.

Limits:
- This is one short bag: about 1.7 m and one ~186° spin.
- The reference is itself a scan alignment, not motion capture.
- slam_toolbox dropped 423 scans (r1) and 857 scans (r2) because the beam count alternates between
  384 and 386.

Files: `r1.csv`/`r2.csv` (SLAM pose next to bag `/odom`, about 10 Hz), `r*_map.json`, `r*_slam.log`,
`slam_params_v2.yaml`, `reference_comparison.txt`, `SHA256SUMS`.
