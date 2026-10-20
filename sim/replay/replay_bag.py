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
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

from sim.twin.pipeline import ROOT, Processes, isolated_env

DEFAULT_INPUTS = ["/scan", "/target_centroid_sector", "/target_centroid"]
OUTPUTS = ["/lidar_sector_dists", "/synced_target", "/target_fused_prob", "/cmd_vel"]


def storage_id(bag: Path) -> str:
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


def replay(bag: Path, out: Path, inputs: List[str], rate: float) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    procs = Processes(out, isolated_env())
    try:
        procs.start_robot_nodes()
        procs.start("bag_record", ["ros2", "bag", "record", "-s", "sqlite3",
                                   "-o", str(out / "replay"), *OUTPUTS], ROOT)
        time.sleep(2.0)
        play = procs.start("bag_play", ["ros2", "bag", "play", str(bag), "--rate", str(rate),
                                        "--topics", *inputs], ROOT)
        play.wait()
        time.sleep(1.5)  # let the chain flush the last frames
    finally:
        procs.stop()

    original = read_cmd_vel(bag)
    replayed = read_cmd_vel(out / "replay")
    result = {"bag": str(bag), "inputs": inputs, "rate": rate,
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
    args = ap.parse_args()
    print(json.dumps(replay(args.bag, args.out, args.inputs, args.rate), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
