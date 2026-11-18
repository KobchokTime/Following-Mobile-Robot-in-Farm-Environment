# Robot day 2026-11-15: analyze.py report

[`robot_day_report.json`](robot_day_report.json) comes from `tools/robot_day/analyze.py`
(`integration-hub @ 804f935`, the same code as `d7eff1b`), run unmodified over all 11 bags of the day.
It ran on the laptop backup through the pure-Python reader
[`../20261107-site01/block_f_analysis/run_analyze_offline.py`](../20261107-site01/block_f_analysis/run_analyze_offline.py).

| Experiment | Result |
| --- | --- |
| **E2 latency** | camera capture → YOLO median **147–184 ms**, p95 186–276 ms, in every bag (about 15,900 frames). On 2026-11-07, with queue depth 10, it was 460–580 ms. **Queue depth 1 (PR #18) is confirmed on hardware.** YOLO → next `/cmd_vel` median is 13–23 ms when locked. |
| E6 following | **No valid run.** The three `e6_straight_1` bags had no follow: 0, 0 and 2 target messages. The series was stopped on a wrong-direction turn ([`e6_series_stop.md`](e6_series_stop.md)) |
| E1, E3, E4 | not run today |

Notes:
- The image-free session bag `20261115T060903Z_e6_session` has no `recording.json`, so the driver
  labels it with the folder name of the data root. Its E2 detection → command values (median 2.6 s)
  span long periods with no person, so they are not a latency figure.
- The idle bags (`follow_edge_td1p0*`) had nobody in view. They count for camera → YOLO only.
