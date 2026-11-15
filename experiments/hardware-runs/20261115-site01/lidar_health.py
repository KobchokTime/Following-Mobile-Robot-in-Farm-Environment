#!/usr/bin/env python3
"""Fail if /scan is degraded. Run after every pipeline start, before the bridge is enabled.

On 2026-11-15 the YDLidar driver once started in a state where only ~18 % of beams were valid,
and the rest were scattered phantom ranges; a restart fixed it. Healthy scans had ~85 % valid.
Exit 0 = PASS, 1 = FAIL (restart the pipeline and run again).
"""

import math
import statistics
import sys
import time

import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan

MIN_VALID_SHARE = 0.70
SECONDS = 3.0


def main() -> int:
    rclpy.init()
    node = rclpy.create_node("lidar_health")
    scans = []
    node.create_subscription(LaserScan, "/scan", scans.append, qos_profile_sensor_data)
    deadline = time.monotonic() + 10.0
    while not scans and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
    scans.clear()
    end = time.monotonic() + SECONDS
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.05)
    node.destroy_node()
    rclpy.shutdown()
    if not scans:
        print("FAIL: no /scan")
        return 1
    shares = [sum(1 for r in m.ranges if math.isfinite(r) and r > 0) / len(m.ranges) for m in scans]
    med = statistics.median(shares)
    rate = len(scans) / SECONDS
    ok = med >= MIN_VALID_SHARE and rate >= 7.0
    print(f"{'PASS' if ok else 'FAIL'}: {len(scans)} scans ({rate:.1f} Hz), valid beams median {med:.0%} "
          f"(min {min(shares):.0%}, need >= {MIN_VALID_SHARE:.0%})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
