#!/usr/bin/env python3
"""Snapshot check of the LiDAR mount: self-hits, front clusters, and camera vs LiDAR bearing.

    python3 lidar_mount_check.py LABEL [--seconds 2] [--offset 0] [--sign -1] [--out DIR]

Robot-frame bearing = wrap(sign * raw + offset), left positive, as in lidar_sectorizer / analyze.py.
Saves the per-beam median ranges and the summary to DIR/<LABEL>.json. Needs ROS 2 sourced.
"""

import argparse
import json
import math
import statistics
import time
from pathlib import Path

import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Int32MultiArray

HFOV_DEG = 70.0
SELF_HIT_M = 0.35
FRONT_DEG = 45.0
MAX_RANGE_M = 4.0
JUMP_M = 0.15
GAP_DEG = 2.0


def wrap_deg(a):
    return (a + 180.0) % 360.0 - 180.0


def camera_bearing_deg(cx, width):
    f = (width / 2.0) / math.tan(math.radians(HFOV_DEG) / 2.0)
    return math.degrees(math.atan2(width / 2.0 - cx, f))


def clusters(points):
    """Split (bearing_deg, range_m) points, sorted by bearing, at range jumps or angular gaps."""
    out, cur = [], []
    for b, r in points:
        if cur and (abs(r - cur[-1][1]) > JUMP_M or b - cur[-1][0] > GAP_DEG):
            out.append(cur)
            cur = []
        cur.append((b, r))
    if cur:
        out.append(cur)
    res = []
    for c in out:
        b0, b1 = c[0][0], c[-1][0]
        rm = statistics.median(r for _, r in c)
        res.append({"bearing_from": round(b0, 1), "bearing_to": round(b1, 1),
                    "bearing_mid": round((b0 + b1) / 2, 1), "range_median_m": round(rm, 3),
                    "width_m": round(2 * rm * math.sin(math.radians(max(b1 - b0, 0.0)) / 2), 3),
                    "points": len(c)})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("--seconds", type=float, default=2.0)
    ap.add_argument("--offset", type=float, default=0.0)
    ap.add_argument("--sign", type=float, default=-1.0)
    ap.add_argument("--out", default=str(Path.home() / "lidar_mount_check"))
    a = ap.parse_args()

    rclpy.init()
    node = rclpy.create_node("lidar_mount_check")
    scans, frames = [], []
    node.create_subscription(LaserScan, "/scan", scans.append, qos_profile_sensor_data)
    node.create_subscription(Int32MultiArray, "/yolo_frame", lambda m: frames.append(list(m.data)), 10)
    deadline = time.monotonic() + 10.0
    while not scans and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
    scans.clear()
    frames.clear()
    end = time.monotonic() + a.seconds
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.05)
    node.destroy_node()
    rclpy.shutdown()
    if not scans:
        print("NO /scan received")
        return 1

    s0 = scans[0]
    n = min(len(s.ranges) for s in scans)
    med = []
    for i in range(n):
        vals = [s.ranges[i] for s in scans if math.isfinite(s.ranges[i]) and s.ranges[i] > 0.0]
        med.append(statistics.median(vals) if vals else None)
    beams = []
    for i, r in enumerate(med):
        raw = math.degrees(s0.angle_min + i * s0.angle_increment)
        beams.append((round(wrap_deg(a.sign * raw + a.offset), 2), r))

    self_hits = sorted((b, round(r, 3)) for b, r in beams if r is not None and r < SELF_HIT_M)
    front = sorted((b, r) for b, r in beams if r is not None and abs(b) <= FRONT_DEG and r <= MAX_RANGE_M)
    cl = clusters(front)
    cam = []
    for d in frames:
        w, nbox = d[2], d[4]
        for k in range(nbox):
            x1, _, x2 = d[5 + 7 * k], d[6 + 7 * k], d[7 + 7 * k]
            cam.append(camera_bearing_deg((x1 + x2) / 2.0, w))
    cam_b = round(statistics.median(cam), 1) if cam else None

    summary = {"label": a.label, "scans": len(scans), "yolo_frames": len(frames),
               "lidar_offset_deg": a.offset, "lidar_sign": a.sign,
               "self_hits_lt_0.35m": self_hits, "front_clusters_pm45deg_lt4m": cl,
               "camera_person_bearing_median_deg": cam_b,
               "camera_person_boxes": len(cam)}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    path = Path(a.out) / f"{a.label}.json"
    path.write_text(json.dumps({**summary, "beams_median": beams}, indent=1))

    print(f"[{a.label}] scans={len(scans)} yolo_frames={len(frames)} -> {path}")
    print(f"  self-hits <{SELF_HIT_M} m: {len(self_hits)} beams"
          + (f", bearings {self_hits[0][0]}..{self_hits[-1][0]} deg" if self_hits else ""))
    print(f"  camera person bearing (median, left +): {cam_b} deg from {len(cam)} boxes")
    print(f"  front clusters (|bearing| <= {FRONT_DEG} deg, range <= {MAX_RANGE_M} m):")
    for c in cl:
        mark = "  <- near camera bearing" if cam_b is not None and abs(c["bearing_mid"] - cam_b) <= 8 else ""
        print(f"    {c['bearing_from']:+6.1f}..{c['bearing_to']:+6.1f} deg  r={c['range_median_m']:.2f} m"
              f"  width={c['width_m']:.2f} m  pts={c['points']}{mark}")
    print("  profile, min range per 5 deg bin (left +):")
    row = []
    for lo in range(-60, 60, 5):
        rs = [r for b, r in beams if r is not None and lo <= b < lo + 5]
        row.append(f"{lo:+d}:{min(rs):.2f}" if rs else f"{lo:+d}:--")
    for k in range(0, len(row), 8):
        print("    " + "  ".join(row[k:k + 8]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
