#!/usr/bin/env python3
"""Lifted-wheel check of the drive bridge's turn direction (T6, `turn_dir`).

Run with the wheels off the ground and `MAIN/Control/zlac_joystick_bridge.py` running:

    python3 tools/robot_day/turn_check.py

It sends /cmd_vel in four steps, 2 s each, and prints what each wheel should do:

1. linear.x = 0.2   both wheels roll forwards
2. stop
3. angular.z = 0.3  a left turn (counter-clockwise, REP-103): right wheel forwards, left wheel backwards
4. stop

If step 1 is wrong, the forward mapping (FORWARD_DIR) is wrong. If only step 3 is wrong, restart the
bridge with `turn_dir:=-1` and run this again. Record the result in config/motor_wheel_calibration.md.
"""

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node

STEPS = [
    (0.2, 0.0, "linear.x = 0.2: BOTH wheels should roll FORWARDS"),
    (0.0, 0.0, "stop"),
    (0.0, 0.3, "angular.z = 0.3 (left turn): RIGHT wheel FORWARDS, LEFT wheel BACKWARDS"),
    (0.0, 0.0, "stop"),
]
STEP_S = 2.0
RATE_HZ = 10.0


class TurnCheck(Node):
    def __init__(self):
        super().__init__("turn_check")
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.step, self.ticks = 0, 0
        self.timer = self.create_timer(1.0 / RATE_HZ, self.tick)
        print(f"step 1/{len(STEPS)}: {STEPS[0][2]}", flush=True)

    def tick(self):
        if self.step >= len(STEPS):
            return
        lin, ang, _ = STEPS[self.step]
        msg = Twist()
        msg.linear.x, msg.angular.z = lin, ang
        self.pub.publish(msg)
        self.ticks += 1
        if self.ticks >= STEP_S * RATE_HZ:
            self.step, self.ticks = self.step + 1, 0
            if self.step < len(STEPS):
                print(f"step {self.step + 1}/{len(STEPS)}: {STEPS[self.step][2]}", flush=True)


def main():
    rclpy.init()
    node = TurnCheck()
    try:
        while rclpy.ok() and node.step < len(STEPS):
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        node.pub.publish(Twist())
        node.destroy_node()
        rclpy.shutdown()
    print("done; record what you saw in config/motor_wheel_calibration.md", flush=True)


if __name__ == "__main__":
    main()
