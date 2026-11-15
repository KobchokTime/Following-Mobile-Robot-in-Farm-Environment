#!/usr/bin/env python3
"""Log the SLAM pose (TF map->base_link) next to a recorded /odom, for bag replays.

Read-only: subscribes to /odom, /map and TF; publishes nothing. Run with use_sim_time so
the TF lookups use the bag clock:
    python3 slam_pose_logger.py OUT_PREFIX --ros-args -p use_sim_time:=true
Writes OUT_PREFIX.csv (one row per /odom message once TF is available) and
OUT_PREFIX_map.json (last /map size and cell counts). Stops after `idle_s` seconds
without /odom (default 20).
"""

import csv
import json
import math
import sys
import time

import rclpy
from nav_msgs.msg import OccupancyGrid, Odometry
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from tf2_ros import Buffer, TransformListener


def yaw_of(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


def main():
    prefix = sys.argv[1]
    rclpy.init(args=sys.argv)
    node = rclpy.create_node("slam_pose_logger_ro")
    idle_s = 20.0
    buf = Buffer()
    TransformListener(buf, node)
    out = open(prefix + ".csv", "w", newline="", encoding="utf-8")
    writer = csv.writer(out)
    writer.writerow(["t", "odom_x", "odom_y", "odom_yaw", "slam_x", "slam_y", "slam_yaw"])
    last = {"odom_wall": time.monotonic(), "map": None, "rows": 0}

    def on_odom(msg):
        last["odom_wall"] = time.monotonic()
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        try:
            tr = buf.lookup_transform("map", "base_link", rclpy.time.Time()).transform
            slam = [tr.translation.x, tr.translation.y, yaw_of(tr.rotation)]
        except Exception:
            return
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        writer.writerow([round(t, 3), round(p.x, 4), round(p.y, 4), round(yaw_of(q), 4),
                         *[round(v, 4) for v in slam]])
        last["rows"] += 1

    def on_map(msg):
        data = msg.data
        last["map"] = {"width": msg.info.width, "height": msg.info.height,
                       "resolution": msg.info.resolution,
                       "known_cells": sum(1 for v in data if v >= 0),
                       "occupied_cells": sum(1 for v in data if v >= 65),
                       "cells": len(data)}

    node.create_subscription(Odometry, "/odom", on_odom, 50)
    node.create_subscription(OccupancyGrid, "/map", on_map, QoSProfile(
        depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL))
    try:
        while rclpy.ok() and time.monotonic() - last["odom_wall"] < idle_s:
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        out.close()
        with open(prefix + "_map.json", "w", encoding="utf-8") as f:
            json.dump(last["map"], f, indent=2)
        print(f"logged {last['rows']} rows; map {last['map']}", flush=True)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
