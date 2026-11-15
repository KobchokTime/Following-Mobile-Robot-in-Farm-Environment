#!/usr/bin/env python3
"""Per-run check for E6 follow runs. Run on the robot right after each recording (ROS 2 sourced).

    python3 e6_check.py [RUN_DIR]        # default: newest folder in ~/robot_day_recordings

Reports lock share, fused range min/max, max |cmd_vel|, and flags wrong-direction turns: a /cmd_vel
turn whose sign is opposite to the side of the image where the camera sees the person (largest YOLO
box in the nearest /yolo_frame; left + / right -), while the fused range is >= 0.9 m. The camera box,
not the fused target, is the reference, because a fused target on the wrong side is the failure mode.
A turn counts only above 0.05 rad/s, and the box centre must be off the image centre by more than one
sector (|bearing| > 7.8 deg). Exit 1 if any wrong-direction turn is found.
"""

import json
import math
import sys
from pathlib import Path

import rosbag2_py
import yaml
from geometry_msgs.msg import Twist
from rclpy.serialization import deserialize_message
from std_msgs.msg import Float32MultiArray, Int32MultiArray

W, HFOV = 640, 70.0
MIN_RANGE_FOR_WRONG = 0.9
TURN_EPS = 0.05
SIDE_DEG = 7.8


def bearing_deg(cx):
    f = (W / 2) / math.tan(math.radians(HFOV / 2))
    return math.degrees(math.atan2(W / 2 - cx, f))


def main() -> int:
    root = Path.home() / "robot_day_recordings"
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else max(
        (p for p in root.iterdir() if (p / "recording.json").exists()), key=lambda p: p.stat().st_mtime)
    label = json.loads((run / "recording.json").read_text())["scenario"]
    bag = run / "recording"
    storage = yaml.safe_load((bag / "metadata.yaml").read_text())["rosbag2_bagfile_information"]["storage_identifier"]
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=str(bag), storage_id=storage), rosbag2_py.ConverterOptions("", ""))
    r.set_filter(rosbag2_py.StorageFilter(topics=["/yolo_frame", "/synced_target", "/cmd_vel"]))
    t0, frames, people, synced, cmds, boxes = None, 0, 0, [], [], []
    while r.has_next():
        topic, raw, t = r.read_next()
        t0 = t0 or t
        s = (t - t0) * 1e-9
        if topic == "/yolo_frame":
            d = list(deserialize_message(raw, Int32MultiArray).data)
            frames += 1
            people += d[4] > 0
            if d[4] > 0:
                bx = max((d[5 + 7 * i: 12 + 7 * i] for i in range(d[4])), key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
                boxes.append((s, (bx[0] + bx[2]) / 2.0))
        elif topic == "/synced_target":
            d = deserialize_message(raw, Float32MultiArray).data
            synced.append((s, float(d[0]), float(d[2])))
        else:
            m = deserialize_message(raw, Twist)
            cmds.append((s, m.linear.x, m.angular.z))

    wrong = []
    for s, vx, wz in cmds:
        if abs(wz) <= TURN_EPS:
            continue
        near = [x for x in synced if abs(x[0] - s) <= 0.3]
        seen = [x for x in boxes if abs(x[0] - s) <= 0.3]
        if not near or not seen:
            continue
        rng = min(near, key=lambda x: abs(x[0] - s))[2]
        cx = min(seen, key=lambda x: abs(x[0] - s))[1]
        b = bearing_deg(cx)
        if rng >= MIN_RANGE_FOR_WRONG and abs(b) > SIDE_DEG and (b > 0) != (wz > 0):
            wrong.append((round(s, 1), min(8, int(cx * 9 / W)), round(b, 1), round(rng, 2), round(vx, 2), round(wz, 2)))

    rng = [x[2] for x in synced if math.isfinite(x[2])]
    print(f"{run.name}  [{label}]")
    print(f"  YOLO frames {frames}, with person {people}, locked msgs {len(synced)} "
          f"({len(synced) / frames:.0%} of frames)" if frames else "  no YOLO frames")
    print(f"  fused range min {min(rng):.2f} m, max {max(rng):.2f} m" if rng else "  no fused range")
    if cmds:
        print(f"  cmd_vel msgs {len(cmds)}, max vx {max(c[1] for c in cmds):+.2f}, min vx {min(c[1] for c in cmds):+.2f}, "
              f"max |wz| {max(abs(c[2]) for c in cmds):.2f}")
    else:
        print("  no cmd_vel")
    if wrong:
        print(f"  WRONG-DIRECTION TURNS at >= {MIN_RANGE_FOR_WRONG} m: {len(wrong)}")
        for w in wrong[:10]:
            print(f"    t={w[0]}s sector S{w[1]} bearing {w[2]:+} deg range {w[3]} m cmd vx {w[4]:+} wz {w[5]:+}")
        print("  -> STOP the series and report")
        return 1
    print("  no wrong-direction turns at >= 0.9 m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
