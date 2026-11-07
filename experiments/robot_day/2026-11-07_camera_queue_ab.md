# Camera queue depth A/B, 2026-11-07

The robot was stationary. The follow controller could publish `/cmd_vel`, but the motor
bridge was absent: `/cmd_vel` had zero subscribers before the trial and after restoration.
No motor command was delivered. The robot checkout was `integration-hub` at `043b877`
with four tracked modifications and two untracked files from the field session; this
trial did not edit that checkout.

The running YOLO source was SHA-256
`80ace185da082682433989471c69f52efe1d1e46242c5637f4839ce19a347e8c`.
The temporary depth-1 copy outside the checkout was SHA-256
`54b6472aff75f840b7ce382ee5ebdbd047f91202fd6c9c633715851425f1dab5`.
Its only source change was the `/image_raw` subscription depth, 10 to 1.
Each bag used SQLite and recorded `/camera_info`, `/yolo_frame`,
`/target_centroid_sector`, `/synced_target`, and `/cmd_vel` for approximately
15 seconds. Camera capture-to-YOLO age is bag receive time of `/yolo_frame`
minus its embedded image capture stamp. The recorder adds a small receive delay;
`/camera_info` capture-to-recorder median was 3.4–3.8 ms.

| Run, UTC | Queue | YOLO frames | Measured span | Frames/s | Person frames | Capture-to-YOLO median / p95 |
|---|---:|---:|---:|---:|---:|---:|
| 10:08:33 baseline | 10 | 81 | 12.40 s | 6.45 | 81 | 476.4 / 494.5 ms |
| 10:10:18 trial 1 | 1 | 57 | 8.72 s | 6.42 | 57 | 154.4 / 183.3 ms |
| 10:10:37 trial 2 | 1 | 85 | 13.30 s | 6.31 | 85 | 152.3 / 226.4 ms |
| 10:13:53 restored baseline | 10 | 88 | 12.10 s | 7.19 | 88 | 460.0 / 478.3 ms |

The difference is reproducible across the two depth-1 and two depth-10 windows:
depth 1 saved roughly 0.31 seconds at the median. The output rate stayed in the
6.3–7.2 frames/s range, but these short windows do not establish equivalent
throughput or performance in other scenes. The first frame of depth-1 trial 1 was
6.347 s old; all later frames in that run were under 0.5 s old, and none in trial 2
exceeded 0.5 s. That startup outlier remains a caution against quoting a maximum
latency from this A/B. No command-to-motion latency was measured.

The original YOLO process was restored after both trials. The final check at
10:19:14 UTC found two `/cmd_vel` publishers and zero subscribers. The bags
remain only on the robot under:

- `/home/yakgreen001/robot_day_recordings/20261107T100833Z_ab_depth10/recording`
- `/home/yakgreen001/robot_day_recordings/ab_depth1_trial/20261107T101018Z_depth1_01/recording`
- `/home/yakgreen001/robot_day_recordings/ab_depth1_trial/20261107T101037Z_depth1_02/recording`
- `/home/yakgreen001/robot_day_recordings/20261107T101353Z_ab_depth10_return/recording`

The result supports reviewing a depth-1 default for YOLO. It is a perception
latency observation, not a field motion test.
