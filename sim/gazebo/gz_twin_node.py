#!/usr/bin/env python3
"""Glue between Ignition Gazebo and the robot nodes. Runs on simulation time.

- Reads every model pose from Gazebo (`/gz/poses`, bridged from
  `/world/farm/dynamic_pose/info`).
- Drives each person along the scenario waypoints: feed-forward velocity plus a
  position correction, sent to `/model/<name>/cmd_vel`.
- Applies the robot's `/cmd_vel` through the same ZLAC bridge model as the kinematic
  twin (`sim.twin.world.bridge_rpm`) and sends the resulting body twist to
  `/model/robot/cmd_vel`.
- Stands in for camera + YOLO: projects the people Gazebo has, as seen from the robot's
  Gazebo pose, with the same code as the kinematic twin, and publishes
  `/target_centroid_sector` and `/target_centroid` at 10 Hz. The LiDAR is Gazebo's own
  `gpu_lidar`.
- Writes ground truth in the kinematic twin's JSONL schema, so `sim.twin.score` works as is.
"""

from __future__ import annotations

import json
import math
import random

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Int32MultiArray, String
from tf2_msgs.msg import TFMessage

from sim.twin.scenarios import SCENARIOS
from sim.twin.world import Person, RobotParams, SensorParams, bridge_rpm, project_detections, wheel_twist

CONTROL_HZ = 50.0
SENSOR_HZ = 10.0
POSITION_GAIN = 2.0


class GzTwinNode(Node):
    def __init__(self) -> None:
        super().__init__("gz_twin")
        self.declare_parameter("scenario", "straight")
        self.declare_parameter("bridge_mode", "current")
        self.declare_parameter("log_path", "")
        self.declare_parameter("seed", 0)
        name = str(self.get_parameter("scenario").value)
        self.spec = SCENARIOS[name]
        self.people = [Person(n, list(wp), is_target=t) for n, t, wp in self.spec["people"]]
        self.blackouts = self.spec.get("blackouts", ())
        self.robot = RobotParams(bridge_mode=str(self.get_parameter("bridge_mode").value))
        self.sensors = SensorParams()
        self.rng = random.Random(int(self.get_parameter("seed").value))
        log_path = str(self.get_parameter("log_path").value)
        self.log = open(log_path, "w", encoding="utf-8") if log_path else None

        self.poses = {}
        self.cmd = (0.0, 0.0)
        self.cmd_t = None
        self.v = self.w = self.rpm_left = self.rpm_right = 0.0
        self.t0 = None
        self.done = False

        self.create_subscription(TFMessage, "/gz/poses", self.on_poses, 10)
        self.create_subscription(Twist, "/cmd_vel", self.on_cmd, 10)
        self.pub_robot = self.create_publisher(Twist, "/model/robot/cmd_vel", 10)
        self.pub_people = {p.name: self.create_publisher(Twist, f"/model/{p.name}/cmd_vel", 10)
                           for p in self.people}
        self.pub_sector = self.create_publisher(Int32MultiArray, "/target_centroid_sector", 10)
        self.pub_centroid = self.create_publisher(Int32MultiArray, "/target_centroid", 10)
        self.pub_state = self.create_publisher(String, "/sim/state", 10)
        self.create_timer(1.0 / CONTROL_HZ, self.on_control)
        self.create_timer(1.0 / SENSOR_HZ, self.on_sensors)
        self.get_logger().info(f"gz twin: scenario={name} bridge={self.robot.bridge_mode}")

    # ------------------------------------------------------------------ time
    def now(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def t(self) -> float:
        return 0.0 if self.t0 is None else self.now() - self.t0

    # ---------------------------------------------------------------- inputs
    def on_poses(self, msg: TFMessage) -> None:
        for tf in msg.transforms:
            name = tf.child_frame_id
            q = tf.transform.rotation
            yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
            self.poses[name] = (tf.transform.translation.x, tf.transform.translation.y, yaw)

    def on_cmd(self, msg: Twist) -> None:
        self.cmd = (msg.linear.x, msg.angular.z)
        self.cmd_t = self.now()

    # --------------------------------------------------------------- control
    def ready(self) -> bool:
        return "robot" in self.poses and all(p.name in self.poses for p in self.people)

    def on_control(self) -> None:
        if self.done or not self.ready():
            return
        if self.t0 is None:
            self.t0 = self.now()
        t = self.t()
        for p in self.people:
            x, y, _ = self.poses[p.name]
            gx, gy = p.position(t)
            nx, ny = p.position(t + 0.1)
            msg = Twist()
            msg.linear.x = (nx - gx) / 0.1 + POSITION_GAIN * (gx - x)
            msg.linear.y = (ny - gy) / 0.1 + POSITION_GAIN * (gy - y)
            self.pub_people[p.name].publish(msg)

        age = None if self.cmd_t is None else self.now() - self.cmd_t
        self.rpm_left, self.rpm_right = bridge_rpm(self.robot, self.cmd, age)
        self.v, self.w = wheel_twist(self.robot, self.rpm_left, self.rpm_right)
        out = Twist()
        out.linear.x, out.angular.z = self.v, self.w
        self.pub_robot.publish(out)
        if t >= self.spec["duration_s"]:
            self.done = True
            self.pub_robot.publish(Twist())
            for pub in self.pub_people.values():
                pub.publish(Twist())

    # ---------------------------------------------------------------- sensors
    def robot_frame(self):
        rx, ry, ryaw = self.poses["robot"]
        c, s = math.cos(ryaw), math.sin(ryaw)
        out = {}
        for p in self.people:
            x, y, _ = self.poses[p.name]
            dx, dy = x - rx, y - ry
            out[p.name] = (c * dx + s * dy, -s * dx + c * dy)
        return out

    def on_sensors(self) -> None:
        if self.done or self.t0 is None:
            return
        t = self.t()
        blackout = any(a <= t < b for a, b in self.blackouts)
        rel = self.robot_frame()
        if not blackout:
            for det in project_detections(rel, self.sensors, self.rng):
                self.pub_centroid.publish(Int32MultiArray(data=[det.cx, det.cy]))
                self.pub_sector.publish(Int32MultiArray(data=[det.cx, det.cy, det.sector_id]))

        rx, ry, ryaw = self.poses["robot"]
        state = {
            "t": round(t, 3),
            "robot": {"x": rx, "y": ry, "yaw_deg": math.degrees(ryaw), "v": self.v, "w": self.w,
                      "rpm_left": self.rpm_left, "rpm_right": self.rpm_right},
            "cmd": {"linear_x": self.cmd[0], "angular_z": self.cmd[1],
                    "age_s": None if self.cmd_t is None else self.now() - self.cmd_t},
            "people": {p.name: {"range_m": math.hypot(*rel[p.name]),
                                "bearing_deg": math.degrees(math.atan2(rel[p.name][1], rel[p.name][0])),
                                "is_target": p.is_target} for p in self.people},
            "blackout": blackout,
        }
        line = json.dumps(state)
        self.pub_state.publish(String(data=line))
        if self.log:
            self.log.write(line + "\n")
            self.log.flush()


def main() -> None:
    rclpy.init()
    node = GzTwinNode()
    try:
        while rclpy.ok() and not node.done:
            rclpy.spin_once(node, timeout_sec=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        if node.log:
            node.log.close()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
