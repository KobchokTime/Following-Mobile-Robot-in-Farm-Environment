#!/usr/bin/env python3
"""Check the wheel radius with the robot on the ground (needed for the bridge's "mps" speed mode).

    python3 tools/robot_day/speed_check.py [--speed 0.4] [--seconds 4] [--countdown 5]

Mark the floor at the robot's centre, run this with zlac_joystick_bridge.py running, and measure how
far the robot travelled. The script prints the distance the bridge should have produced, given its
acceleration ramp. If the robot went further or less far, the wheel radius is wrong:

    true wheel_radius_m = set wheel_radius_m x measured distance / expected distance

Restart the bridge with the corrected wheel_radius_m and record it in config/motor_wheel_calibration.md.
"""

import argparse
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node

RATE_HZ = 10.0


def expected_distance(speed, seconds, accel):
    """Distance for a command of `speed` held `seconds`, with the bridge ramping at accel both ways.

    The ramp up happens inside the command and the ramp down after it, and the two triangles are the
    same size, so at full speed the distance is simply speed x seconds. If the ramp never reaches
    `speed`, the robot speeds up for `seconds` and slows down for as long.
    """
    if speed / accel <= seconds:
        return speed * seconds
    return accel * seconds * seconds


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--speed", type=float, default=0.4, help="m/s (default 0.4)")
    ap.add_argument("--seconds", type=float, default=4.0, help="how long the command lasts (default 4)")
    ap.add_argument("--countdown", type=int, default=5, help="seconds to step away first (default 5)")
    ap.add_argument("--accel", type=float, default=1.0, help="the bridge's max_accel_mps2 (default 1.0)")
    args = ap.parse_args()

    rclpy.init()
    node = Node("speed_check")
    pub = node.create_publisher(Twist, "/cmd_vel", 10)
    try:
        deadline = time.monotonic() + 5.0
        while pub.get_subscription_count() == 0 and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
        if pub.get_subscription_count() == 0:
            print("no subscriber on /cmd_vel: is zlac_joystick_bridge.py running?", flush=True)
            return
        for i in range(args.countdown, 0, -1):
            print(f"\rdriving in {i} s \a", end="", flush=True)
            time.sleep(1.0)
        print(f"\rdriving at {args.speed} m/s for {args.seconds} s", flush=True)
        msg = Twist()
        msg.linear.x = args.speed
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:
            pub.publish(msg)
            time.sleep(1.0 / RATE_HZ)
        pub.publish(Twist())
        print(f"stopped. Expected distance: {expected_distance(args.speed, args.seconds, args.accel):.2f} m "
              f"(measure from the start mark to the robot's centre)", flush=True)
    except KeyboardInterrupt:
        print("stopped", flush=True)
    finally:
        try:
            pub.publish(Twist())
        except Exception:  # noqa: BLE001  (the context may already be shut down after Ctrl-C)
            pass
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
