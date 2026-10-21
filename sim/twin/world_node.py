#!/usr/bin/env python3
"""ROS 2 node that runs the twin world in real time.

Publishes what the robot's drivers would publish and consumes `/cmd_vel`:

- `/scan` (sensor_msgs/LaserScan, 10 Hz) instead of the YDLidar driver
- `/target_centroid_sector` `[cx, cy, sector, cb, cr]` and `/target_centroid` `[cx, cy]`
  (std_msgs/Int32MultiArray, 10 Hz); `cb, cr` is the clothing chroma (YCbCr)
  instead of `ros2_yolo_live.py` (camera + YOLO)
- `/sim/state` (std_msgs/String, JSON ground truth, 10 Hz)
- `/cmd_vel` is applied through the ZLAC bridge model in `world.py`

Parameters: `scenario`, `seed`, `bridge_mode`, `log_path`, `rate_hz`.
The node exits by itself when the scenario duration is over.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Int32MultiArray, String

from .scenarios import ALL_SCENARIOS, build

PHYSICS_HZ = 50.0
SENSOR_HZ = 10.0


class TwinWorldNode(Node):
    def __init__(self) -> None:
        super().__init__("twin_world")
        self.declare_parameter("scenario", "straight")
        self.declare_parameter("seed", 0)
        self.declare_parameter("bridge_mode", "current")
        self.declare_parameter("log_path", "")
        name = str(self.get_parameter("scenario").value)
        self.spec = ALL_SCENARIOS[name]
        self.world = build(name, seed=int(self.get_parameter("seed").value),
                           bridge_mode=str(self.get_parameter("bridge_mode").value))
        log_path = str(self.get_parameter("log_path").value)
        self.log = open(log_path, "w", encoding="utf-8") if log_path else None

        self.pub_scan = self.create_publisher(LaserScan, "/scan", 10)
        self.pub_sector = self.create_publisher(Int32MultiArray, "/target_centroid_sector", 10)
        self.pub_centroid = self.create_publisher(Int32MultiArray, "/target_centroid", 10)
        self.pub_state = self.create_publisher(String, "/sim/state", 10)
        self.create_subscription(Twist, "/cmd_vel", self.on_cmd, 10)

        self._ticks_per_sensor = int(round(PHYSICS_HZ / SENSOR_HZ))
        self._tick = 0
        self.done = False
        self.create_timer(1.0 / PHYSICS_HZ, self.on_tick)
        self.get_logger().info(
            f"twin world: scenario={name} bridge={self.world.robot.bridge_mode} "
            f"duration={self.spec['duration_s']}s")

    def on_cmd(self, msg: Twist) -> None:
        self.world.command(msg.linear.x, msg.angular.z)

    def on_tick(self) -> None:
        if self.done:
            return
        self.world.step(1.0 / PHYSICS_HZ)
        self._tick += 1
        if self._tick % self._ticks_per_sensor == 0:
            self.publish_sensors()
        if self.world.t >= self.spec["duration_s"]:
            self.done = True

    def publish_sensors(self) -> None:
        w, s = self.world, self.world.sensors
        stamp = self.get_clock().now().to_msg()

        scan = LaserScan()
        scan.header.stamp = stamp
        scan.header.frame_id = "laser"
        scan.angle_min = -math.pi
        scan.angle_increment = 2.0 * math.pi / s.lidar_rays
        scan.angle_max = scan.angle_min + scan.angle_increment * (s.lidar_rays - 1)
        scan.scan_time = 1.0 / SENSOR_HZ
        scan.range_min = s.lidar_range_min_m
        scan.range_max = s.lidar_range_max_m
        scan.ranges = [float(r) for r in w.scan()]
        self.pub_scan.publish(scan)

        for det in w.detections():
            self.pub_centroid.publish(Int32MultiArray(data=[det.cx, det.cy]))
            self.pub_sector.publish(Int32MultiArray(data=[det.cx, det.cy, det.sector_id, det.cb, det.cr]))

        state = w.state()
        line = json.dumps(state)
        self.pub_state.publish(String(data=line))
        if self.log:
            self.log.write(line + "\n")
            self.log.flush()

    def close(self) -> None:
        if self.log:
            self.log.close()


def main() -> None:
    rclpy.init()
    node = TwinWorldNode()
    try:
        while rclpy.ok() and not node.done:
            rclpy.spin_once(node, timeout_sec=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
