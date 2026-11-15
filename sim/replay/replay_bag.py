#!/usr/bin/env python3
"""Replay a recorded rosbag2 through the unmodified robot nodes and compare the output.

    python3 -m sim.replay.replay_bag BAG_DIR --out replay_out

Plays only the sensor inputs (`--inputs`, default `/scan /target_centroid_sector
/target_centroid`) into the perception -> fusion -> controller chain, records what
the chain publishes, and compares the new `/cmd_vel` with the `/cmd_vel` stored in
the original bag (when there is one). Works with sqlite3 bags out of the box and
with MCAP bags (from `record_robot_day.sh`) when the MCAP storage plugin is installed.

Output: `<out>/replay/` (the new bag), `<out>/compare.json`, and one log per node.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import signal
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

from sim.twin.pipeline import ROOT, ROBOT_NODES, Processes, isolated_env

DEFAULT_INPUTS = ["/scan", "/target_centroid_sector", "/target_centroid", "/yolo_frame"]
OUTPUTS = ["/yolo_frame", "/lidar_sector_dists", "/synced_target", "/target_fused_prob", "/cmd_vel"]


def storage_id(bag: Path) -> str:
    import yaml

    meta = yaml.safe_load((bag / "metadata.yaml").read_text(encoding="utf-8"))
    return meta["rosbag2_bagfile_information"]["storage_identifier"]


def read_cmd_vel(bag: Path) -> List[Tuple[float, float, float]]:
    """(t_s from first message, linear.x, angular.z) for every /cmd_vel in the bag."""
    import rosbag2_py
    from geometry_msgs.msg import Twist
    from rclpy.serialization import deserialize_message

    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=str(bag), storage_id=storage_id(bag)),
                rosbag2_py.ConverterOptions("cdr", "cdr"))
    reader.set_filter(rosbag2_py.StorageFilter(topics=["/cmd_vel"]))
    rows = []
    while reader.has_next():
        _, data, t_ns = reader.read_next()
        msg = deserialize_message(data, Twist)
        rows.append((t_ns * 1e-9, msg.linear.x, msg.angular.z))
    if rows:
        t0 = rows[0][0]
        rows = [(t - t0, v, w) for t, v, w in rows]
    return rows


def summarize(rows: List[Tuple[float, float, float]]) -> Dict[str, float]:
    if not rows:
        return {"count": 0}
    lin = [v for _, v, _ in rows]
    return {
        "count": len(rows),
        "duration_s": rows[-1][0],
        "mean_linear_x": statistics.fmean(lin),
        "max_linear_x": max(lin),
        "mean_abs_angular_z": statistics.fmean(abs(w) for _, _, w in rows),
        "zero_fraction": sum(1 for _, v, w in rows if v == 0.0 and w == 0.0) / len(rows),
    }


def aligned_linear_rmse(a, b, step: float = 0.1) -> float:
    """RMS difference of linear.x, sampling both series (sample-and-hold) every `step` s."""
    def hold(rows, t):
        val = 0.0
        for tt, v, _ in rows:
            if tt > t:
                break
            val = v
        return val
    end = min(a[-1][0], b[-1][0])
    ts = [i * step for i in range(int(end / step) + 1)]
    return math.sqrt(statistics.fmean((hold(a, t) - hold(b, t)) ** 2 for t in ts))


def parse_node_params(items: List[str]) -> Dict[str, Dict[str, str]]:
    """Parse NODE.PARAM=VALUE without leaking a node's overrides into other nodes."""
    params: Dict[str, Dict[str, str]] = {}
    for item in items:
        lhs, sep, value = item.partition("=")
        node, dot, key = lhs.partition(".")
        if not sep or not dot or node not in ROBOT_NODES or not key.isidentifier() or not value:
            raise ValueError(f"Invalid --node-param {item!r}; expected NODE.PARAM=VALUE")
        params.setdefault(node, {})[key] = value
    return params


def replay(bag: Path, out: Path, inputs: List[str], rate: float,
           node_params: Dict[str, Dict[str, str]] | None = None,
           start_offset: float = 0.0, max_wall_s: float | None = None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    procs = Processes(out, isolated_env())
    try:
        procs.start_robot_nodes(node_params=node_params)
        procs.start("bag_record", ["ros2", "bag", "record", "-s", "sqlite3",
                                   "-o", str(out / "replay"), *OUTPUTS], ROOT)
        time.sleep(2.0)
        play_cmd = ["ros2", "bag", "play", str(bag), "--rate", str(rate),
                    "--disable-keyboard-controls", "--topics", *inputs]
        if start_offset:
            play_cmd.extend(("--start-offset", str(start_offset)))
        play = procs.start("bag_play", play_cmd, ROOT)
        try:
            play.wait(timeout=max_wall_s)
        except subprocess.TimeoutExpired:
            os.killpg(play.pid, signal.SIGINT)
            play.wait(timeout=10)
        time.sleep(1.5)  # let the chain flush the last frames
    finally:
        procs.stop()

    original = read_cmd_vel(bag)
    replayed = read_cmd_vel(out / "replay")
    result = {"bag": str(bag), "inputs": inputs, "rate": rate,
              "start_offset": start_offset, "max_wall_s": max_wall_s, "node_params": node_params or {},
              "original_cmd_vel": summarize(original), "replayed_cmd_vel": summarize(replayed)}
    if original and replayed:
        result["linear_x_rmse"] = aligned_linear_rmse(original, replayed)
    (out / "compare.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bag", type=Path)
    ap.add_argument("--out", default=Path("replay_out"), type=Path)
    ap.add_argument("--inputs", nargs="+", default=DEFAULT_INPUTS)
    ap.add_argument("--rate", default=1.0, type=float)
    ap.add_argument("--start-offset", default=0.0, type=float,
                    help="Skip this many seconds from the beginning of a long bag")
    ap.add_argument("--max-wall-s", type=float,
                    help="Stop playback after this many wall-clock seconds, then flush the output bag")
    ap.add_argument("--node-param", action="append", default=[], metavar="NODE.PARAM=VALUE",
                    help="Pass a ROS parameter only to the named replay node (repeatable)")
    args = ap.parse_args()
    if args.rate <= 0 or args.start_offset < 0 or (args.max_wall_s is not None and args.max_wall_s <= 0):
        ap.error("--rate must be positive, --start-offset non-negative, and --max-wall-s positive")
    try:
        node_params = parse_node_params(args.node_param)
    except ValueError as error:
        ap.error(str(error))
    print(json.dumps(replay(args.bag, args.out, args.inputs, args.rate, node_params,
                            args.start_offset, args.max_wall_s), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
