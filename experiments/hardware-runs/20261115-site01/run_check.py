#!/usr/bin/env python3
"""Check one robot-day recording right after it stops, before moving to the next mark.

    python3 run_check.py [RUN_DIR]      # default: newest folder in ~/robot_day_recordings

Gross-error check only: did the bag record, did YOLO see someone, did fusion lock, and for e1/e3
labels, is the person roughly where the label says. It is not the E1 accuracy result
(tools/robot_day/analyze.py computes that). Needs ROS 2 sourced (rosbag2_py).
"""

import json
import math
import re
import statistics
import sys
from pathlib import Path

import rosbag2_py
import yaml
from rclpy.serialization import deserialize_message
from std_msgs.msg import Float32MultiArray, Int32MultiArray

HFOV_DEG = 70.0
PERSON_RADIUS_M = 0.2
MIN_FRAMES = 30
MIN_LOCK_SHARE = 0.5
MAX_BEARING_ERR_DEG = 8.0
MAX_RANGE_ERR_M = 0.4


def camera_bearing_deg(cx, width):
    """Pinhole model of analyze.py / sync_fusion_node.py, left positive."""
    f = (width / 2.0) / math.tan(math.radians(HFOV_DEG) / 2.0)
    return math.degrees(math.atan2(width / 2.0 - cx, f))


def main() -> int:
    root = Path.home() / "robot_day_recordings"
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else max(
        (p for p in root.iterdir() if (p / "recording.json").exists()), key=lambda p: p.stat().st_mtime)
    label = json.loads((run / "recording.json").read_text())["scenario"]
    bag = run / "recording"
    if not (bag / "metadata.yaml").exists():
        print(f"{run.name}: NO BAG -> RETAKE")
        return 1
    storage = yaml.safe_load((bag / "metadata.yaml").read_text())["rosbag2_bagfile_information"]["storage_identifier"]
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=str(bag), storage_id=storage), rosbag2_py.ConverterOptions("", ""))
    reader.set_filter(rosbag2_py.StorageFilter(topics=["/yolo_frame", "/synced_target"]))
    frames = seen = 0
    width = 640
    bearings, ranges = [], []
    while reader.has_next():
        topic, raw, _ = reader.read_next()
        if topic == "/yolo_frame":
            d = deserialize_message(raw, Int32MultiArray).data
            frames += 1
            width = d[2]
            seen += d[4] > 0
        else:
            d = deserialize_message(raw, Float32MultiArray).data
            bearings.append(camera_bearing_deg(d[0], width))
            if math.isfinite(d[2]) and d[2] > 0:
                ranges.append(d[2])

    lock = len(bearings) / frames if frames else 0.0
    b = statistics.median(bearings) if bearings else None
    r = statistics.median(ranges) if ranges else None
    problems = []
    if frames < MIN_FRAMES:
        problems.append(f"only {frames} YOLO frames")
    if lock < MIN_LOCK_SHARE:
        problems.append(f"locked on {lock:.0%} of frames")

    m = re.fullmatch(r"e1_b(-?\d+(?:\.\d+)?)_d(\d+(?:\.\d+)?)", label)
    if m and b is not None:
        tb, td = float(m.group(1)), float(m.group(2))
        if abs(b - tb) > MAX_BEARING_ERR_DEG:
            problems.append(f"bearing {b:+.1f} deg vs mark {tb:+.0f}")
        if r is not None and abs(r - (td - PERSON_RADIUS_M)) > MAX_RANGE_ERR_M:
            problems.append(f"range {r:.2f} m vs mark {td:.1f} m (expect ~{td - PERSON_RADIUS_M:.1f})")

    fmt = lambda v, s: "-" if v is None else s.format(v)  # noqa: E731
    print(f"{run.name}  [{label}]")
    print(f"  YOLO frames {frames}, with a person {seen}, locked {len(bearings)} ({lock:.0%})")
    print(f"  median bearing {fmt(b, '{:+.1f}')} deg (left +), median LiDAR range {fmt(r, '{:.2f}')} m")
    print("  OK" if not problems else "  RETAKE: " + "; ".join(problems))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
