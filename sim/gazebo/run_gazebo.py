#!/usr/bin/env python3
"""Run a twin scenario in Ignition Gazebo (Fortress) with the unmodified robot nodes.

Inside the Gazebo twin container (see `sim/README.md`):

    python3 -m sim.gazebo.run_gazebo --scenario straight            # headless
    python3 -m sim.gazebo.run_gazebo --scenario straight --gui      # needs $DISPLAY

Everything runs on simulation time (`/clock`), so a slow machine gives the same
result, only more slowly. The chain is the same as in `sim.twin.run_scenario`, but
`/scan` now comes from Gazebo's gpu_lidar and the poses from Gazebo physics.
Results go to `<out>/<scenario>_<bridge>_gazebo/` in the same format as the kinematic twin.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from sim.twin.pipeline import ROOT, Processes, isolated_env
from sim.twin.scenarios import SCENARIOS
from sim.twin.score import load, score

from .world_gen import world


def bridge_args(people) -> list:
    args = ["/scan@sensor_msgs/msg/LaserScan[ignition.msgs.LaserScan",
            "/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock",
            "/world/farm/dynamic_pose/info@tf2_msgs/msg/TFMessage[ignition.msgs.Pose_V",
            "/model/robot/cmd_vel@geometry_msgs/msg/Twist]ignition.msgs.Twist"]
    args += [f"/model/{p}/cmd_vel@geometry_msgs/msg/Twist]ignition.msgs.Twist" for p in people]
    return ["ros2", "run", "ros_gz_bridge", "parameter_bridge", *args,
            "--ros-args", "-r", "/world/farm/dynamic_pose/info:=/gz/poses"]


def run_one(name: str, bridge_mode: str, out_root: Path, gui: bool, seed: int, camera_pose: str) -> dict:
    out = out_root / f"{name}_{bridge_mode}_gazebo"
    out.mkdir(parents=True, exist_ok=True)
    (out / "world.sdf").write_text(world(name, camera_pose), encoding="utf-8")
    env = dict(isolated_env(), IGN_PARTITION=f"twin{os.getpid()}")
    sim_time = ["-p", "use_sim_time:=true"]
    people = [p[0] for p in SCENARIOS[name]["people"]]
    procs = Processes(out, env)
    try:
        gz = ["ign", "gazebo", "-r", str(out / "world.sdf")]
        if not gui:
            gz[2:2] = ["-s", "--headless-rendering"]
        procs.start("gazebo", gz, ROOT)
        procs.start("ros_gz_bridge", bridge_args(people), ROOT)
        procs.start_robot_nodes(sim_time)
        time.sleep(8.0 if gui else 5.0)
        with open(out / "gz_twin.log", "w", encoding="utf-8") as log:
            twin = subprocess.run(
                [sys.executable, "-m", "sim.gazebo.gz_twin_node", "--ros-args", *sim_time,
                 "-p", f"scenario:={name}", "-p", f"bridge_mode:={bridge_mode}", "-p", f"seed:={seed}",
                 "-p", f"log_path:={out / 'state.jsonl'}"],
                cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT,
                timeout=SCENARIOS[name]["duration_s"] * 8 + 120)
        if twin.returncode != 0:
            raise RuntimeError(f"gz_twin_node exited with {twin.returncode}; see {out / 'gz_twin.log'}")
    finally:
        procs.stop()
    result = {"scenario": name, "bridge_mode": bridge_mode, "simulator": "gazebo", "seed": seed,
              "doc": SCENARIOS[name]["doc"], **score(load(out / "state.jsonl"))}
    (out / "score.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default="straight", help=f"comma-separated names from {sorted(SCENARIOS)}, or 'all'")
    ap.add_argument("--bridge-mode", default="current", choices=["current", "fixed", "diff_drive"])
    ap.add_argument("--out", default="sim_runs", type=Path)
    ap.add_argument("--gui", action="store_true", help="open the Gazebo window (needs $DISPLAY)")
    ap.add_argument("--seed", default=0, type=int)
    ap.add_argument("--camera-pose", default="-3.5 -5.5 4.5 0 0.5 0.75",
                    help="GUI camera 'x y z roll pitch yaw'")
    args = ap.parse_args()
    names = sorted(SCENARIOS) if args.scenario == "all" else args.scenario.split(",")
    results = [run_one(n, args.bridge_mode, args.out, args.gui, args.seed, args.camera_pose) for n in names]
    (args.out / "summary_gazebo.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    for r in results:
        print(json.dumps({k: r.get(k) for k in ("scenario", "bridge_mode", "distance_travelled_m",
                                                  "median_gap_m", "final_gap_m", "max_abs_target_bearing_deg",
                                                  "min_person_range_m", "contact", "turned", "stop_latency_s")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
