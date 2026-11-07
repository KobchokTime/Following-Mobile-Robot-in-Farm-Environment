#!/usr/bin/env python3
"""Run one or more twin scenarios through the real robot nodes and score them.

Inside the twin container (see `sim/README.md`):

    python3 -m sim.twin.run_scenario --scenario all --bridge-mode both

For every scenario this starts, on an isolated ROS domain:
  twin world (fake LiDAR + fake camera/YOLO + ZLAC bridge model)
  -> ros2_yolo_ws/scripts/Lidar/lidar_sectorizer_node.py
  -> ros2_yolo_ws/scripts/Image/sync_fusion_node.py
  -> ros2_yolo_ws/scripts/Image/fusion_prob_node.py
  -> ros2_yolo_ws/scripts/MAIN/Control/follow_stop_node.py  -> /cmd_vel -> twin world

The robot nodes run unmodified. Results go to `<out>/<scenario>_<bridge>/`:
`state.jsonl` (ground truth at 10 Hz), `score.json`, one log per node and, with
`--record-bag`, a sqlite3 rosbag2 in `bag/` that `sim.replay.replay_bag` can replay.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from .pipeline import RECORD_TOPICS, ROOT, Processes, isolated_env
from .scenarios import SCENARIO_LOOKUP, SCENARIO_SETS
from .score import load, score


def run_one(name: str, bridge_mode: str, out_root: Path, seed: int, record_bag: bool,
            ros_params: tuple = (), realism: bool = False) -> dict:
    out = out_root / f"{name}_{bridge_mode}"
    out.mkdir(parents=True, exist_ok=True)
    env = isolated_env()
    procs = Processes(out, env)
    try:
        procs.start_robot_nodes([a for p in ros_params for a in ("-p", p)])
        if record_bag:
            procs.start("bag_record", ["ros2", "bag", "record", "-s", "sqlite3",
                                       "-o", str(out / "bag"), *RECORD_TOPICS], ROOT)
        time.sleep(2.0)  # let subscribers come up before the world starts moving
        with open(out / "world.log", "w", encoding="utf-8") as log:
            world = subprocess.run(
                [sys.executable, "-m", "sim.twin.world_node", "--ros-args",
                 "-p", f"scenario:={name}", "-p", f"seed:={seed}",
                 "-p", f"bridge_mode:={bridge_mode}", "-p", f"log_path:={out / 'state.jsonl'}",
                 "-p", f"realism:={'true' if realism else 'false'}"],
                cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT,
                timeout=SCENARIO_LOOKUP[name]["duration_s"] + 60)
        if world.returncode != 0:
            raise RuntimeError(f"twin world exited with {world.returncode}; see {out / 'world.log'}")
    finally:
        procs.stop()

    result = {"scenario": name, "bridge_mode": bridge_mode, "seed": seed, "ros_params": list(ros_params),
              "realism": realism,
              "doc": SCENARIO_LOOKUP[name]["doc"], **score(load(out / "state.jsonl"))}
    (out / "score.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default="all", help=f"one of {sorted(SCENARIO_LOOKUP)}, or a set: {sorted(SCENARIO_SETS)}")
    ap.add_argument("--bridge-mode", default="current", choices=["current", "fixed", "diff_drive", "mps", "both", "turning", "all"])
    ap.add_argument("--out", default="sim_runs", type=Path)
    ap.add_argument("--seed", default=0, type=int)
    ap.add_argument("--record-bag", action="store_true", help="also record a sqlite3 rosbag2")
    ap.add_argument("--realism", action="store_true",
                    help="detection latency and dropouts, false positives, LiDAR clutter and noise, wheel slip")
    ap.add_argument("--ros-param", action="append", default=[], metavar="NAME:=VALUE",
                    help="parameter for every robot node, e.g. target_gate:=false (repeatable; for ablations)")
    args = ap.parse_args()

    names = SCENARIO_SETS.get(args.scenario, [args.scenario])
    modes = {"both": ["current", "diff_drive"], "turning": ["fixed", "diff_drive"],
             "all": ["current", "fixed", "diff_drive"]}.get(args.bridge_mode, [args.bridge_mode])
    results = [run_one(n, m, args.out, args.seed, args.record_bag, tuple(args.ros_param), args.realism) for n in names for m in modes]
    (args.out / "summary.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    cols = ["scenario", "bridge_mode", "distance_travelled_m", "median_gap_m", "final_gap_m",
            "max_abs_target_bearing_deg", "min_person_range_m", "contact", "turned", "stop_latency_s"]
    print("\t".join(cols))
    for r in results:
        print("\t".join(f"{r.get(c):.2f}" if isinstance(r.get(c), float) else str(r.get(c, "-")) for c in cols))
    return 0


if __name__ == "__main__":
    sys.exit(main())
