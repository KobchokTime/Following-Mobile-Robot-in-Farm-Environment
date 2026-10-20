#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import csv
import math
import os
from dataclasses import dataclass
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy, QoSDurabilityPolicy
from rclpy.time import Time

from std_msgs.msg import Int32MultiArray
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist

# ======== Motor drive (ZLAC8015D via Modbus RTU) ========
import minimalmodbus
import serial
from contextlib import suppress

def fmt(x, nd=3):
    return f"{x:.{nd}f}" if x is not None else "None"

@dataclass
class Centroid:
    cx_px: Optional[float] = None
    ts: Optional[Time] = None

class ZLAC8015D:
    """Thin wrapper for ZLAC8015D dual-wheel drive over Modbus RTU."""
    def __init__(self, port: str, slave_id: int = 1, baudrate: int = 115200, timeout: float = 0.6, use_rs485_rts: bool = False):
        self.port = port
        self.slave_id = slave_id
        self.baudrate = baudrate
        self.timeout = timeout
        self.use_rs485_rts = use_rs485_rts
        self.inst = self._open()

    def _open(self):
        inst = minimalmodbus.Instrument(self.port, self.slave_id)
        inst.serial.baudrate = self.baudrate
        inst.serial.bytesize = 8
        inst.serial.parity   = minimalmodbus.serial.PARITY_NONE
        inst.serial.stopbits = 1
        inst.serial.timeout  = self.timeout
        inst.mode = minimalmodbus.MODE_RTU
        inst.close_port_after_each_call = True
        if self.use_rs485_rts:
            inst.serial.rs485_mode = serial.rs485.RS485Settings(
                rts_level_for_tx=True, rts_level_for_rx=False, loopback=False
            )
        return inst

    def enable_velocity(self):
        """Set velocity mode + enable servo (CMD=8)."""
        # MODE=3 (velocity)
        self.inst.write_register(0x200D, 3, 0, functioncode=6)
        # clear/stop then enable
        with suppress(Exception):
            self.inst.write_register(0x200E, 7, 0, functioncode=6)
        self.inst.write_register(0x200E, 8, 0, functioncode=6)

    def set_velocity_rpm(self, left_rpm: int, right_rpm: int):
        """Send target RPM for left/right (signed)."""
        self.inst.write_register(0x2088, int(left_rpm), 0, functioncode=6, signed=True)
        self.inst.write_register(0x2089, int(right_rpm), 0, functioncode=6, signed=True)

    def stop(self):
        with suppress(Exception):
            self.inst.write_register(0x200E, 7, 0, functioncode=6)

class FollowStopMotorNode(Node):
    def __init__(self):
        super().__init__('follow_stop_motor_node')

        # ========= Parameters (vision/LiDAR) =========
        self.declare_parameter('hfov_deg', 70.0)
        self.declare_parameter('image_width', 640)
        self.declare_parameter('alpha_cx', 0.3)
        self.declare_parameter('cx_deadband', 12.0)

        self.declare_parameter('angle_offset_deg', 180.0)
        self.declare_parameter('sector_deg', 30.0)
        self.declare_parameter('lidar_min_valid', 0.05)

        self.declare_parameter('init_dist', 1.0)
        self.declare_parameter('confirm_needed', 5)
        self.declare_parameter('stop_dist', 0.5)
        self.declare_parameter('slow_dist', 1.2)
        self.declare_parameter('resume_margin', 0.05)
        self.declare_parameter('target_timeout', 1.8)
        self.declare_parameter('kx', 0.0015)     # rad/s per pixel error
        self.declare_parameter('w_max', 1.0)
        self.declare_parameter('timer_hz', 10.0)
        self.declare_parameter('print_only', True)
        self.declare_parameter('csv_path', '~/logs/follow_stop_log.csv')

        # ========= Parameters (drive & kinematics) =========
        self.declare_parameter('drive_enable', True)        # <-- สวิตช์หลัก: ส่งมอเตอร์จริงไหม
        self.declare_parameter('drive_port', '/dev/ttyUSB0')
        self.declare_parameter('drive_baud', 115200)
        self.declare_parameter('drive_id', 1)
        self.declare_parameter('use_rs485_rts', False)

        self.declare_parameter('wheel_radius_m', 0.08)      # รัศมีล้อ (m)
        self.declare_parameter('track_width_m', 0.40)       # ระยะศูนย์กลางล้อซ้าย-ขวา (m)
        self.declare_parameter('rpm_max', 400)              # limit เป้าหมาย
        self.declare_parameter('rpm_min', 0)                # ถ้าต้องการคาบขั้นต่ำ
        self.declare_parameter('left_dir', 1)               # เฟสซ้าย (1 หรือ -1)
        self.declare_parameter('right_dir', -1)             # เฟสขวา (1 หรือ -1)
        self.declare_parameter('stop_on_timeout', True)     # TARGET_TIMEOUT/NO_LIDAR ให้หยุดไหม

        # Read params
        self.hfov_deg = float(self.get_parameter('hfov_deg').value)
        self.image_width = int(self.get_parameter('image_width').value)
        self.alpha_cx = float(self.get_parameter('alpha_cx').value)
        self.cx_deadband = float(self.get_parameter('cx_deadband').value)

        self.sector_deg = float(self.get_parameter('sector_deg').value)
        self.lidar_min_valid = float(self.get_parameter('lidar_min_valid').value)
        self.angle_offset_rad = math.radians(float(self.get_parameter('angle_offset_deg').value))

        self.init_dist = float(self.get_parameter('init_dist').value)
        self.confirm_needed = int(self.get_parameter('confirm_needed').value)
        self.stop_dist = float(self.get_parameter('stop_dist').value)
        self.slow_dist = float(self.get_parameter('slow_dist').value)
        self.resume_margin = float(self.get_parameter('resume_margin').value)
        self.target_timeout = float(self.get_parameter('target_timeout').value)
        self.kx = float(self.get_parameter('kx').value)
        self.w_max = float(self.get_parameter('w_max').value)
        self.timer_hz = float(self.get_parameter('timer_hz').value)
        self.print_only = bool(self.get_parameter('print_only').value)
        self.csv_path = os.path.expanduser(str(self.get_parameter('csv_path').value))

        self.drive_enable = bool(self.get_parameter('drive_enable').value)
        self.drive_port = str(self.get_parameter('drive_port').value)
        self.drive_baud = int(self.get_parameter('drive_baud').value)
        self.drive_id = int(self.get_parameter('drive_id').value)
        self.use_rs485_rts = bool(self.get_parameter('use_rs485_rts').value)

        self.wheel_radius_m = float(self.get_parameter('wheel_radius_m').value)
        self.track_width_m = float(self.get_parameter('track_width_m').value)
        self.rpm_max = int(self.get_parameter('rpm_max').value)
        self.rpm_min = int(self.get_parameter('rpm_min').value)
        self.left_dir = int(self.get_parameter('left_dir').value)
        self.right_dir = int(self.get_parameter('right_dir').value)
        self.stop_on_timeout = bool(self.get_parameter('stop_on_timeout').value)

        # State
        self.scan: Optional[LaserScan] = None
        self.centroid = Centroid()
        self.cx_filt: Optional[float] = None
        self.locked = False
        self.confirm_count = 0
        self.last_state = "INIT"
        self.last_left_rpm = 0
        self.last_right_rpm = 0

        # ROS I/O
        scan_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=5,
            durability=QoSDurabilityPolicy.VOLATILE,
        )
        self.sub_scan = self.create_subscription(LaserScan, '/scan', self.cb_scan, qos_profile=scan_qos)
        self.sub_cx = self.create_subscription(Int32MultiArray, '/target_centroid', self.cb_centroid, 10)
        self.pub_cmd = self.create_publisher(Twist, '/cmd_vel', 10)

        # CSV
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        self.csv_file = open(self.csv_path, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow([
            'stamp_sec', 'state', 'color',
            'front_min_m', 'cx_px', 'cx_deg', 'cx_filt',
            'v', 'w', 'left_rpm', 'right_rpm'
        ])

        # Motor init
        self.drive: Optional[ZLAC8015D] = None
        if self.drive_enable:
            try:
                self.drive = ZLAC8015D(self.drive_port, self.drive_id, self.drive_baud, timeout=0.6, use_rs485_rts=self.use_rs485_rts)
                self.drive.enable_velocity()
                self.get_logger().info(f"[Drive] Enabled at {self.drive_port} baud={self.drive_baud} id={self.drive_id}")
            except Exception as e:
                self.get_logger().error(f"[Drive] init failed: {e}")
                self.drive = None  # fall back to print-only

        self.get_logger().info(f"FollowStopMotorNode started (print_only={self.print_only}, drive_enable={self.drive_enable})")
        self.timer = self.create_timer(1.0 / self.timer_hz, self.on_timer)

    # ------------- callbacks -------------
    def cb_scan(self, msg: LaserScan):
        self.scan = msg

    def cb_centroid(self, msg: Int32MultiArray):
        cx = float(msg.data[0]) if len(msg.data) > 0 else None
        self.centroid.cx_px = cx
        self.centroid.ts = self.get_clock().now()
        if cx is not None:
            if self.cx_filt is None:
                self.cx_filt = cx
            else:
                self.cx_filt = self.alpha_cx * cx + (1.0 - self.alpha_cx) * self.cx_filt

    # ------------- helpers -------------
    def current_time_sec(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def calc_front_min(self) -> Optional[float]:
        if not self.scan or not self.scan.ranges:
            return None
        ang_min = self.scan.angle_min
        ang_inc = self.scan.angle_increment
        n = len(self.scan.ranges)
        sector_rad_half = math.radians(self.sector_deg / 2.0)
        target_angle = 0.0 + self.angle_offset_rad
        i_lo = max(0, int((target_angle - sector_rad_half - ang_min) / ang_inc))
        i_hi = min(n - 1, int((target_angle + sector_rad_half - ang_min) / ang_inc))
        vals = [self.scan.ranges[i] for i in range(i_lo, i_hi + 1)
                if math.isfinite(self.scan.ranges[i]) and self.scan.ranges[i] > self.lidar_min_valid]
        return min(vals) if vals else None

    def calc_cx_deg(self, cx_px: Optional[float]) -> Optional[float]:
        if cx_px is None or self.image_width <= 0:
            return None
        center = (self.image_width - 1) / 2.0
        px_per_deg = self.image_width / self.hfov_deg
        return (cx_px - center) / px_per_deg

    def pick_color(self, state: str) -> str:
        if state in ('OK', 'RESUMING'):
            return 'GREEN'
        if state in ('WAIT_INIT', 'TARGET_TIMEOUT', 'NO_LIDAR'):
            return 'YELLOW'
        return 'RED'

    def vw_to_rpm(self, v: float, w: float) -> (int, int):
        # differential drive kinematics → wheel linear speeds
        v_l = v - w * (self.track_width_m / 2.0)
        v_r = v + w * (self.track_width_m / 2.0)
        # linear speed (m/s) -> wheel rpm
        rpm_l = (v_l / (2.0 * math.pi * self.wheel_radius_m)) * 60.0
        rpm_r = (v_r / (2.0 * math.pi * self.wheel_radius_m)) * 60.0
        # apply direction and clamp
        rpm_l *= self.left_dir
        rpm_r *= self.right_dir

        def clamp_rpm(x):
            if self.rpm_min > 0:
                if x > 0:
                    x = max(self.rpm_min, x)
                elif x < 0:
                    x = min(-self.rpm_min, x)
            return max(-self.rpm_max, min(self.rpm_max, x))

        rpm_l = int(clamp_rpm(rpm_l))
        rpm_r = int(clamp_rpm(rpm_r))
        return rpm_l, rpm_r

    # ------------- main timer -------------
    def on_timer(self):
        now = self.get_clock().now()
        front_min = self.calc_front_min()
        cx = self.centroid.cx_px
        cx_deg = self.calc_cx_deg(cx)
        target_age = (now - self.centroid.ts).nanoseconds * 1e-9 if self.centroid.ts else None

        state = "OK"
        v = 0.0
        w = 0.0

        if front_min is None:
            state = "NO_LIDAR"
        elif (target_age is None) or (target_age > self.target_timeout) or (cx is None):
            state = "TARGET_TIMEOUT"
            self.locked = False
            self.confirm_count = 0
        else:
            if not self.locked:
                if front_min >= self.init_dist:
                    self.confirm_count += 1
                    state = "WAIT_INIT"
                    if self.confirm_count >= self.confirm_needed:
                        self.locked = True
                        self.confirm_count = 0
                else:
                    state = "WAIT_INIT"
                    self.confirm_count = 0
            if self.locked:
                if front_min <= self.stop_dist:
                    state = "TOO_CLOSE"
                    v = 0.0
                    w = 0.0
                else:
                    state = "OK"
                    # linear speed schedule by distance margin
                    margin = max(0.0, min(1.0, (front_min - self.stop_dist) / (self.slow_dist - self.stop_dist + 1e-6)))
                    v = 0.02 + 0.16 * margin  # m/s (เหมือนเดิม)
                    # heading control (pixel error -> w)
                    err_px = 0.0 if cx is None else (cx - (self.image_width - 1) / 2.0)
                    if abs(err_px) < self.cx_deadband:
                        err_px = 0.0
                    w = - self.kx * err_px
                    w = max(-self.w_max, min(self.w_max, w))
                if state == "TOO_CLOSE" and front_min >= (self.stop_dist + self.resume_margin):
                    state = "RESUMING"
                    v = 0.02
                    w = 0.0

        if self.stop_on_timeout and state in ("TARGET_TIMEOUT", "NO_LIDAR"):
            v, w = 0.0, 0.0

        # publish cmd_vel (เผื่อใช้กับ stack อื่น)
        if not self.print_only:
            msg = Twist()
            msg.linear.x = float(v)
            msg.angular.z = float(w)
            self.pub_cmd.publish(msg)

        # convert to rpm & send to drive
        left_rpm, right_rpm = self.vw_to_rpm(v, w)
        sent = False
        if self.drive_enable and self.drive is not None:
            try:
                self.drive.set_velocity_rpm(left_rpm, right_rpm)
                sent = True
                self.last_left_rpm, self.last_right_rpm = left_rpm, right_rpm
            except Exception as e:
                self.get_logger().warn(f"[Drive] send failed: {e}")

        color = self.pick_color(state)
        self.get_logger().info(
            f"[{state}] front_min={fmt(front_min)} "
            f"cx={fmt(cx)} cx_deg={fmt(cx_deg)} cx_filt={fmt(self.cx_filt)} "
            f"v={v:.3f} w={w:.3f} rpm=({left_rpm},{right_rpm}) sent={sent} color={color}"
        )

        # log CSV
        self.csv_writer.writerow([
            f"{self.current_time_sec():.3f}",
            state,
            color,
            f"{front_min:.3f}" if front_min is not None else "",
            f"{cx:.1f}" if cx is not None else "",
            f"{cx_deg:.2f}" if cx_deg is not None else "",
            f"{self.cx_filt:.1f}" if self.cx_filt is not None else "",
            f"{v:.3f}",
            f"{w:.3f}",
            f"{left_rpm:d}",
            f"{right_rpm:d}",
        ])
        self.csv_file.flush()
        os.fsync(self.csv_file.fileno())

    # ------------- shutdown -------------
    def destroy_node(self):
        try:
            if self.drive is not None:
                self.drive.stop()
            self.csv_file.close()
        except Exception:
            pass
        super().destroy_node()

# ======== main ========
def main():
    rclpy.init()
    node = FollowStopMotorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

