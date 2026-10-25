#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from contextlib import suppress
import minimalmodbus
import math
import time

# ================= CONFIG =================
PORT = "/dev/ttyUSB1"
BAUD = 115200
SLAVE_ID = 1

# mapping จาก /cmd_vel.linear.x → speed command
SPEED_GAIN = 40.0      # lin=0.5 → ~20
MAX_CMD    = 40.0      # กันไม่ให้ส่งแรงเกินไป

# ถ้าเดินหน้ากลายเป็นถอยหลัง สลับเป็น -1.0 ได้
FORWARD_DIR = 1.0

TIMEOUT = 1.0  # วินาที: ถ้าไม่ได้ cmd_vel ใหม่เกินนี้ → set vel = 0

# Turning (angular.z). Defaults below; each is also a ROS parameter of the node.
USE_ANGULAR = True     # False = old behaviour (linear.x only)
TRACK_WIDTH_M = 0.40   # distance between the wheels; not measured on this chassis yet
TURN_DIR = 1.0         # set -1.0 if a positive angular.z spins the robot clockwise

# Speed mode. "mps": /cmd_vel is in m/s and rad/s, turned into wheel RPM with the wheel radius,
# capped at MAX_SPEED_MPS per wheel and ramped at MAX_ACCEL_MPS2. "legacy": the old mapping
# (40 RPM per unit of linear.x, capped at 40 RPM, about 0.36 m/s with a 0.085 m wheel).
SPEED_MODE = "mps"
WHEEL_RADIUS_M = 0.085   # not measured on this chassis yet; measure on robot day
MAX_SPEED_MPS = 1.4      # brisk walking pace
MAX_ACCEL_MPS2 = 1.0     # per wheel; the ramp also applies when slowing down
UPDATE_HZ = 10.0


def wheel_commands(linear, angular, speed_gain=SPEED_GAIN, max_cmd=MAX_CMD, track_width=TRACK_WIDTH_M,
                   forward_dir=FORWARD_DIR, turn_dir=TURN_DIR, use_angular=USE_ANGULAR):
    """Return the (0x2088, 0x2089) register values for a /cmd_vel.

    Differential drive, angular.z positive = counter-clockwise (REP-103). Both wheels are
    scaled down together when one would pass max_cmd, so a turn keeps its shape.
    Channels and signs follow the forward mapping the joystick-tested bridge already used
    (forward: 0x2088 negative, 0x2089 positive) and config/motor_wheel_calibration.md
    (0x2088 drives the physical right wheel). With angular = 0 the result is the same as
    before this change.
    """
    if not (math.isfinite(linear) and math.isfinite(angular)):
        return 0.0, 0.0  # a NaN/inf command stops the wheels instead of crashing the write loop
    turn_dir = 1.0 if turn_dir >= 0 else -1.0
    turn = turn_dir * angular * track_width / 2.0 if use_angular else 0.0
    left = forward_dir * (linear - turn) * speed_gain
    right = forward_dir * (linear + turn) * speed_gain
    scale = max(1.0, abs(left) / max_cmd, abs(right) / max_cmd)
    left, right = left / scale, right / scale
    return -right, left

def mps_to_rpm(mps, wheel_radius=WHEEL_RADIUS_M):
    return mps * 60.0 / (2.0 * math.pi * wheel_radius)


def wheel_commands_mps(linear, angular, wheel_radius=WHEEL_RADIUS_M, max_speed=MAX_SPEED_MPS,
                       track_width=TRACK_WIDTH_M, forward_dir=FORWARD_DIR, turn_dir=TURN_DIR,
                       use_angular=USE_ANGULAR):
    """(0x2088, 0x2089) RPM targets for a /cmd_vel in m/s and rad/s ("mps" mode).

    Same channels, signs and turn shape as wheel_commands(); each wheel's speed is capped at
    max_speed (m/s), scaling both together so a turn keeps its shape.
    """
    if not (math.isfinite(linear) and math.isfinite(angular)):
        return 0.0, 0.0
    turn_dir = 1.0 if turn_dir >= 0 else -1.0
    turn = turn_dir * angular * track_width / 2.0 if use_angular else 0.0
    left = forward_dir * (linear - turn)
    right = forward_dir * (linear + turn)
    scale = max(1.0, abs(left) / max_speed, abs(right) / max_speed)
    left, right = mps_to_rpm(left / scale, wheel_radius), mps_to_rpm(right / scale, wheel_radius)
    return -right, left


def ramp(current, target, max_step):
    """Move current towards target by at most max_step."""
    return current + max(-max_step, min(max_step, target - current))


def ramp_pair(current, target, max_step):
    """Ramp both wheels together: the wheel with the larger change moves at most max_step and the
    other moves in proportion, so they arrive at the same time and a turn keeps its shape."""
    dl, dr = target[0] - current[0], target[1] - current[1]
    k = min(1.0, max_step / max(abs(dl), abs(dr))) if (dl or dr) else 1.0
    return current[0] + k * dl, current[1] + k * dr


def check_params(speed_mode, wheel_radius, max_speed, max_accel):
    """Reject parameter values that would divide by zero or silently pick the wrong mode."""
    if speed_mode not in ("mps", "legacy"):
        raise ValueError(f"speed_mode must be 'mps' or 'legacy', got {speed_mode!r}")
    for name, value in (("wheel_radius_m", wheel_radius), ("max_speed_mps", max_speed),
                        ("max_accel_mps2", max_accel)):
        if not (math.isfinite(value) and value > 0.0):
            raise ValueError(f"{name} must be a positive number, got {value!r}")

# ============== ZLAC DRIVER ===============
class ZLAC8015D:
    def __init__(self, port, sid, baud):
        self.inst = minimalmodbus.Instrument(port, sid)
        self.inst.serial.baudrate = baud
        self.inst.serial.bytesize = 8
        self.inst.serial.parity   = minimalmodbus.serial.PARITY_NONE
        self.inst.serial.stopbits = 1
        self.inst.serial.timeout  = 0.5
        self.inst.mode = minimalmodbus.MODE_RTU
        self.inst.close_port_after_each_call = True

    def enable_velocity(self):
        # เหมือนสคริปต์จอยที่วิ่งได้
        self.inst.write_register(0x200D, 3, 0, functioncode=6)
        time.sleep(0.05)
        with suppress(Exception):
            self.inst.write_register(0x200E, 7, 0, functioncode=6)
        time.sleep(0.05)
        self.inst.write_register(0x200E, 8, 0, functioncode=6)
        print("[Drive] Velocity mode enabled")

    def set_velocity(self, left, right):
        # ✅ สำคัญ: ต้องใส่ signed=True เหมือนโค้ดจอย
        self.inst.write_register(0x2088, int(left), 0, functioncode=6, signed=True)
        self.inst.write_register(0x2089, int(right), 0, functioncode=6, signed=True)
        print(f"[Drive] set_velocity L={left} R={right}")

    def stop_soft(self):
        """หยุดแบบนิ่ม: แค่ตั้ง velocity = 0"""
        with suppress(Exception):
            self.inst.write_register(0x2088, 0, 0, functioncode=6, signed=True)
            self.inst.write_register(0x2089, 0, 0, functioncode=6, signed=True)
        print("[Drive] Soft stop (vel=0)")

    def stop_hard(self):
        """หยุดจริงจัง: ปิด enable (ใช้ตอนปิดโปรแกรม)"""
        with suppress(Exception):
            self.inst.write_register(0x200E, 7, 0, functioncode=6)
        print("[Drive] Hard stop (0x200E=7)")

# ============== MAIN NODE =================
class DriveBridge(Node):
    def __init__(self):
        super().__init__('zlac_drive_bridge')
        self.declare_parameter('use_angular', USE_ANGULAR)
        self.declare_parameter('track_width_m', TRACK_WIDTH_M)
        self.declare_parameter('turn_dir', TURN_DIR)
        self.declare_parameter('speed_mode', SPEED_MODE)
        self.declare_parameter('wheel_radius_m', WHEEL_RADIUS_M)
        self.declare_parameter('max_speed_mps', MAX_SPEED_MPS)
        self.declare_parameter('max_accel_mps2', MAX_ACCEL_MPS2)
        self.use_angular = bool(self.get_parameter('use_angular').value)
        self.track_width = float(self.get_parameter('track_width_m').value)
        self.turn_dir = float(self.get_parameter('turn_dir').value)
        self.speed_mode = str(self.get_parameter('speed_mode').value)
        self.wheel_radius = float(self.get_parameter('wheel_radius_m').value)
        self.max_speed = float(self.get_parameter('max_speed_mps').value)
        check_params(self.speed_mode, self.wheel_radius, self.max_speed,
                     float(self.get_parameter('max_accel_mps2').value))
        # largest RPM change per update in "mps" mode
        self.max_step = mps_to_rpm(float(self.get_parameter('max_accel_mps2').value) / UPDATE_HZ, self.wheel_radius)
        self.zlac = ZLAC8015D(PORT, SLAVE_ID, BAUD)
        self.zlac.enable_velocity()

        self.last_cmd_time = time.time()
        self.left = 0.0
        self.right = 0.0
        self.out_left = 0.0   # what was last written, after the ramp ("mps" mode)
        self.out_right = 0.0

        self.sub = self.create_subscription(Twist, '/cmd_vel', self.cmd_callback, 10)
        self.timer = self.create_timer(1.0 / UPDATE_HZ, self.update_loop)

        self.get_logger().info("✅ ZLAC Drive Bridge started (listening to /cmd_vel)")

    def cmd_callback(self, msg: Twist):
        linear = msg.linear.x
        angular = msg.angular.z
        # self.left / self.right are the values for registers 0x2088 / 0x2089 (see wheel_commands)
        if self.speed_mode == "legacy":
            self.left, self.right = wheel_commands(
                linear, angular, track_width=self.track_width,
                turn_dir=self.turn_dir, use_angular=self.use_angular)
        else:
            self.left, self.right = wheel_commands_mps(
                linear, angular, wheel_radius=self.wheel_radius, max_speed=self.max_speed,
                track_width=self.track_width, turn_dir=self.turn_dir, use_angular=self.use_angular)

        self.last_cmd_time = time.time()

        self.get_logger().info(
            f"[CMD] lin={linear:.2f} ang={angular:.2f} → 0x2088={self.left:.2f} 0x2089={self.right:.2f}"
        )

    def update_loop(self):
        # ถ้าเกิน TIMEOUT ไม่มี cmd_vel ใหม่ → set velocity = 0
        if time.time() - self.last_cmd_time > TIMEOUT:
            if self.left != 0.0 or self.right != 0.0:
                self.get_logger().info("[STATE] Timeout → zero velocity")
            self.left = 0.0
            self.right = 0.0

        # ส่งค่าปัจจุบันเข้าไดรฟ์ทุก 0.1 วินาที
        if self.speed_mode == "legacy":
            self.zlac.set_velocity(self.left, self.right)
        else:
            self.out_left, self.out_right = ramp_pair((self.out_left, self.out_right),
                                                      (self.left, self.right), self.max_step)
            self.zlac.set_velocity(self.out_left, self.out_right)

    def destroy_node(self):
        # ตอนปิดโปรแกรม ค่อย soft stop + hard stop
        self.zlac.stop_soft()
        self.zlac.stop_hard()
        super().destroy_node()

def main():
    rclpy.init()
    node = DriveBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
