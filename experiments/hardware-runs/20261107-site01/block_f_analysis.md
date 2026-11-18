# Block F — Offline Analysis of site01 Recordings

**Analysed:** 2026-11-13, offline on the laptop copy. The robot was not connected.
**Recorded:** 2026-11-07, site01, bridge off (no drive bridge subscribed to `/cmd_vel`).

## Inputs

| Item | Value |
| --- | --- |
| Raw data | `C:\Users\Time\Documents\robot_day_data\20261107-site01\`. 29 bags, md5-identical to the robot. Manifest: [`bag_audit/robot_day_recordings.md5`](bag_audit/robot_day_recordings.md5) |
| Analysis code | `tools/robot_day/analyze.py` from `integration-hub @ d7eff1b` (git blob `29f2197d`), unmodified |
| Bag reader | [`block_f_analysis/run_analyze_offline.py`](block_f_analysis/run_analyze_offline.py) swaps only `read_bag()` for the pure-Python `rosbags` 0.11.9 reader, because the laptop has no ROS 2. Every statistic is `analyze.py`'s own code |
| Output | [`block_f_analysis/site01_report.json`](block_f_analysis/site01_report.json) |

**Reader check:** for the 10 runs in Codex's ROS-based `20261107_block_e_e2_report.json`, the
offline numbers are identical in every field (frames, bad stamps, and all medians and p95s).

**Labels:** the nine `e1_b*_d*` runs from 10:52–10:57Z were relabelled `uncontrolled_*` before
analysis, because their labels are not ground truth
([Block E correction](block_e_perception_recording.md#correction-in-bag-audit-added-2026-11-07-same-day)).
They feed E2 only. Four A/B bags have no `recording.json`, so they are labelled by folder name.
Two runs have no bag and were skipped: `093247Z_block_e_baseline_1` and `105231Z_e1_b0_d1.0`.

## What could be computed

| Experiment | Result |
| --- | --- |
| E1 bearing / range accuracy | **Not computed.** No recording has trustworthy ground truth |
| E2 latency | Computed for all 29 bags |
| E3, E4, E6 | No recordings |

## E2 — latency

`capture → detection` is the camera stamp to the recorder receiving `/yolo_frame`.
`detection → cmd_vel` is that receipt to the next `/cmd_vel`. Times are recorder receive times,
so they include the recorder's own delay.

### YOLO image queue depth (Codex A/B, same session)

| Bag | Queue | Frames | capture → detection median / p95 (ms) | capture → cmd_vel median / p95 (ms) |
| --- | --- | --- | --- | --- |
| ab_depth10 | 10 | 81 | 476.4 / 494.5 | 525.7 / 552.1 |
| ab_depth10_return | 10 | 88 | 460.0 / 477.5 | 466.2 / 603.9 |
| depth1_01 | 1 | 57 (1 bad stamp) | 154.3 / 181.3 | 170.6 / 319.0 |
| depth1_02 | 1 | 85 | 152.3 / 225.9 | 175.4 / 1569.3 |

A queue of 1 cuts the median capture → detection time by about two thirds, from 460–476 ms to
152–154 ms. This rests on two runs per arm from one session. It shows the direction of the effect but
does not bound the worst case. The one bad stamp in `depth1_01` was more than 5 s old, consistent
with the stale first frame after a restart that Codex reported, and `analyze.py` excludes it.

### All other runs (queue 10, the code before PR #18)

| Group | Runs | capture → detection median (ms) | detection → cmd_vel median (ms) |
| --- | --- | --- | --- |
| Codex `block_e_*` | 15 | 471–580 | 7.8–54.0 (10 runs with a lock) |
| `uncontrolled_e1_*` and `e1_b0_d1.0_rep` | 10 | 557–723 | 13.9–3998.8 (8 runs with a lock) |

Per-run values are in the report JSON.

### Reading these numbers

1. **Inference plus queueing dominates.** With a steady lock, detection → cmd_vel has a median of
   5.5–54 ms. With a queue of 10, capture → detection is around 470–500 ms.
2. **A long detection → cmd_vel does not mean slow control.** `follow_stop` publishes only while a
   synced target exists. When the lock comes and goes, the "next `/cmd_vel`" can be seconds away.
   This explains `block_e_person_lock_11` p95 2205 ms and the 1.0–4.0 s medians in the uncontrolled
   runs, which locked only 0–27 times
   ([audit](block_e_perception_recording.md#the-e1_-scenario-labels-are-not-ground-truth)).
   Measuring control latency needs runs with a continuous lock.
3. **The uncontrolled runs were slower before detection: 557–723 ms against 471–497 ms in the
   comparable Codex runs.** The cause is not established. Candidates:
   - YOLO was started outside the launch file (`start_yolo.sh`).
   - The disk was 98 % full while raw images were being written to the eMMC.
   - Different scene content.

## Not established

- E1 accuracy of any kind.
- Worst-case (bounded) latency. The p95 values come from runs of 29–88 frames.
- Whether queue depth 1 holds its latency under motion or with the bridge running.

## For the next robot day

- Re-record E1 with the person on measured tape marks, one label per mark, and check the bag before moving on.
- Re-measure E2 with queue depth 1 (PR #18) and with the bridge running on raised wheels.
- Clear robot disk space first. 1.2 GB was free on 2026-11-07.
