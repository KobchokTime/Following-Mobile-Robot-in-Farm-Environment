# Offline twin

Run the robot's software without the robot. The twin replaces the camera/YOLO node, the
LiDAR driver and the ZLAC motor driver. The real perception → fusion → controller
nodes in `ros2_yolo_ws/scripts/` run **unmodified** around it. This is levels 1–2 of the
plan in `docs/PLAN.md`; a Gazebo world can come later on top of the same harness.

```
twin world ── /scan ─────────────────► lidar_sectorizer_node ─► /lidar_sector_dists ─┐
(sim/twin)  ── /target_centroid_sector ──────────────────────────────────────────────┤
     ▲                                                     sync_fusion_node ◄─────────┘
     │                                                            │ /synced_target
     │                                                     fusion_prob_node
     │                                                            │ /target_fused_prob
     └──── ZLAC bridge model ◄── /cmd_vel ◄──────────────── follow_stop_node (MAIN/Control)
```

## Quick start

Needs Docker (Docker Desktop on Windows works). From the repository root:

```bash
docker build -f sim/docker/Dockerfile -t following-robot-twin .
docker run --rm -v "$PWD/sim_runs:/repo/sim_runs" following-robot-twin
```

The default command runs every scenario with both bridge modes, which takes about 6 minutes. It writes
`sim_runs/summary.json` and, per run, `state.jsonl` (ground truth at 10 Hz), `score.json`, and
one log per node.

One scenario:

```bash
docker run --rm -v "$PWD/sim_runs:/repo/sim_runs" following-robot-twin \
  python3 -m sim.twin.run_scenario --scenario curve_left --bridge-mode diff_drive --out /repo/sim_runs
```

If `packages.ros.org` is unreachable, build with `--build-arg INSTALL_MCAP=0`. Everything still
works, except replaying MCAP bags.

## Scenarios (`sim/twin/scenarios.py`)

| Name | What happens |
|---|---|
| `straight` | The target walks straight ahead at 0.3 m/s, then stops. |
| `stop_and_go` | The target walks, stands for 5 s, then walks again. |
| `curve_left` | The target walks ahead, then turns about 60° left. |
| `target_loss` | Straight walk, but the detector sees nothing from t = 10 s to 14 s. |
| `crossing` | Straight walk; a second person crosses between the robot and the target. |

Bridge modes:
- `current` copies `MAIN/Control/zlac_joystick_bridge.py`: it uses `linear.x` only, at 40 RPM per
  unit (clamped to ±40), and drops to zero after 1 s without `/cmd_vel`.
- `diff_drive` also applies `angular.z`, in physical units. It shows what the follower would do
  once the bridge forwards turning.

## Replay a recorded bag

```bash
# make a bag from a twin run (sqlite3)
python3 -m sim.twin.run_scenario --scenario straight --record-bag --out /repo/sim_runs
# play its sensor topics through the real nodes and compare /cmd_vel with the recording
python3 -m sim.replay.replay_bag /repo/sim_runs/straight_current/bag --out /repo/sim_runs/replay
```

The same command replays robot-day bags from `ros2_yolo_ws/scripts/record_robot_day.sh` (MCAP).
`compare.json` reports the original and replayed `/cmd_vel` statistics and the RMS difference of
`linear.x`. Replays are close but not bit-identical, because `sync_fusion_node` pairs messages by
arrival time.

## What the twin is and is not

- It **is** good for logic: data flow between nodes, controller behavior, target loss, timeouts,
  and regressions. CI runs it on every push (`.github/workflows/twin.yml`).
- It **is not** evidence for perception accuracy or real latency. The detections come from
  geometry, not from YOLO on images.
- **Assumptions** to replace with measurements:
  - The wheel radius (0.085 m) and track width (0.40 m) in `sim/twin/world.py`.
  - The LiDAR mount yaw is 180°, matching `angle_offset_deg` in `lidar_sectorizer_node.py`.
  - The camera HFOV is 70°, matching `Image/Camera.py`.

Tests: `tests/test_sim_twin.py` (offline, part of `scripts/check.py`) and `sim/tests/smoke.py`
(regression checks over a run summary).
