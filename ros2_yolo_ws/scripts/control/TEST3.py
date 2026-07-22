#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import csv
import math
import os
import time
from dataclasses import dataclass
from typing import Optional
from contextlib import suppress

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy, QoSDurabilityPolicy
from rclpy.time import Time

from std_msgs.msg import Int32MultiArray
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist

import minimalmodbus, serial


# ================= CONFIG =================
PORT = "/dev/ttyUSB1"
BAUD = 115200
SLAVE_ID = 1
RPM_LIMIT = 300  # safety clamp rpm

# ================= ZLAC DRIVER =================
class ZLAC8015D:
    def __init__(self, port, sid, baud, use_rs485_rts=False):
        self.port, self.sid, self.baud = port, sid, baud
        self.inst = self._open_safe(use_rs485_rts)

    def _open_safe(self, use_rs485_rts: bool):
        # เปิดพอร์ต serial แบบไม่แตะ DTR/RTS
        ser = serial.serial_for_url(self.port, do_not_open=True)
        ser.baudrate = self.baud
        ser.bytesize = serial.EIGHTBITS
        ser.parity   = serial.PARITY_NONE
        ser.stopbits = serial.STOPBITS_ONE
        ser.timeout  = 0.6
        ser.rtscts   = False
        ser.dsrdtr   = False
        if hasattr(ser, "exclusive"):
            ser.exclusive = False
        with suppress(Exception): ser.dtr = False
        with suppress(Exception): ser.rts = False
        if use_rs485_rts:
            ser.rs485_mode = serial.rs485.RS485Settings(
                rts_level_for_tx=True, rts_level_for_rx=False, loopback=False
            )
        ser.open()

        # manual bind to minimalmodbus.Instrument
        inst = minimalmodbus.Instrument.__new__(minimalmodbus.Instrument)
        inst.serial  = ser
        inst.address = self.sid
        inst.mode    = minimalmodbus.MODE_RTU

        # >>> สำคัญ ต้องเติม field พื้นฐาน <<<
        inst.port = self.port
        inst.debug = False
        inst.precalculate_read_size = False
        inst.handle_local_echo = False
        inst.clear_buffers_before_each_transaction = True
        inst.close_port_after_each_call = True

        return inst

    def enable_velocity(self):
        self.inst.write_register(0x200D, 3, 0, functioncode=6)
        time.sleep(0.05)
        with suppress(Exception):
            self.inst.write_register(0x200E, 7, 0, functioncode=6)
        time.sleep(0.05)
        self.inst.write_register(0x200E, 8, 0, functioncode=6)
        print("[Drive] Velocity mode enabled")

    def set_velocity(self, left, right):
        left  = max(-RPM_LIMIT, min(RPM_LIMIT, int(left)))
        right = max(-RPM_LIMIT, min(RPM_LIMIT, int(right)))
        self.inst.write_register(0x2088, left,  0, functioncode=6, signed=True)
        self.inst.write_register(0x2089, right, 0, functioncode=6, signed=True)
        print(f"[Drive] L={left} R={right}")

    def stop(self):
        with suppress(Exception):
            self.inst.write_register(0x200E, 7, 0, functioncode=6)
        print("[Drive] Stopped")


# ================= FOLLOW + STOP =================
def fmt(x, nd=3):
    return f"{x:.{nd}f}" if x is not None else "None"

@dataclass
class Centroid:
    cx_px: Optional[float] = None
    ts: Optional[Time] = None

class FollowStopWithMotor(Node):
    def __init__(self):
        super().__init__('follow_stop_with_motor')

        # ROS Params
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
        self.declare_parameter('kx', 0.0015)
        self.declare_parameter('w_max', 1.0)
        self.declare_parameter('timer_hz', 10.0)
        self.declare_parameter('csv_path', '~/logs/follow_stop_motor.csv')

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
        self.csv_path = os.path.expanduser(str(self.get_parameter('csv_path').value))

        # State
        self.scan: Optional[LaserScan] = None
        self.centroid = Centroid()
        self.cx_filt: Optional[float] = None
        self.locked = False
        self.confirm_count = 0

        # ROS I/O
        scan_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=5,
            durability=QoSDurabilityPolicy.VOLATILE,
        )
        self.sub_scan = self.create_subscription(LaserScan, '/scan', self.cb_scan, qos_profile=scan_qos)
        self.sub_cx = self.create_subscription(Int32MultiArray, '/target_centroid', self.cb_centroid, 10)

        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        self.csv_file = open(self.csv_path, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(['stamp_sec','state','front_min','cx_px','v','w','L','R'])

        # Motor driver
        self.drive = ZLAC8015D(PORT, SLAVE_ID, BAUD)
        self.drive.enable_velocity()

        # Timer
        self.timer = self.create_timer(1.0/self.timer_hz, self.on_timer)
        self.get_logger().info("FollowStopWithMotor started")

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
                self.cx_filt = self.alpha_cx * cx + (1.0-self.alpha_cx) * self.cx_filt

    def calc_front_min(self) -> Optional[float]:
        if not self.scan or not self.scan.ranges:
            return None
        ang_min = self.scan.angle_min
        ang_inc = self.scan.angle_increment
        n = len(self.scan.ranges)
        sector_rad_half = math.radians(self.sector_deg/2.0)
        target_angle = 0.0 + self.angle_offset_rad
        i_lo = max(0, int((target_angle - sector_rad_half - ang_min)/ang_inc))
        i_hi = min(n-1, int((target_angle + sector_rad_half - ang_min)/ang_inc))
        vals = [self.scan.ranges[i] for i in range(i_lo,i_hi+1)
                if math.isfinite(self.scan.ranges[i]) and self.scan.ranges[i] > self.lidar_min_valid]
        return min(vals) if vals else None

    def on_timer(self):
        now = self.get_clock().now()
        front_min = self.calc_front_min()
        cx = self.centroid.cx_px
        target_age = (now - self.centroid.ts).nanoseconds*1e-9 if self.centroid.ts else None

        state, v, w = "OK", 0.0, 0.0
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
                    v, w = 0.0, 0.0
                else:
                    state = "OK"
                    margin = max(0.0, min(1.0,(front_min-self.stop_dist)/(self.slow_dist-self.stop_dist+1e-6)))
                    v = 0.02 + 0.16*margin
                    err_px = 0.0 if cx is None else (cx-(self.image_width-1)/2.0)
                    if abs(err_px) < self.cx_deadband:
                        err_px = 0.0
                    w = - self.kx*err_px
                    w = max(-self.w_max,min(self.w_max,w))
                if state=="TOO_CLOSE" and front_min >= (self.stop_dist+self.resume_margin):
                    state="RESUMING"
                    v,w = 0.02,0.0

        # convert v,w → rpm
        wheel_base = 0.4
        wheel_radius = 0.1
        v_l = (v - w*wheel_base/2.0)/wheel_radius
        v_r = (v + w*wheel_base/2.0)/wheel_radius
        rpm_l = v_l*60/(2*math.pi)
        rpm_r = v_r*60/(2*math.pi)

        self.drive.set_velocity(rpm_l, rpm_r)
        self.get_logger().info(f"[{state}] v={v:.2f} w={w:.2f} L={rpm_l:.1f} R={rpm_r:.1f}")

        self.csv_writer.writerow([
            f"{self.get_clock().now().nanoseconds*1e-9:.3f}",
            state,
            f"{front_min:.3f}" if front_min else "",
            f"{cx:.1f}" if cx else "",
            f"{v:.3f}", f"{w:.3f}", f"{rpm_l:.1f}", f"{rpm_r:.1f}"
        ])
        self.csv_file.flush()
        os.fsync(self.csv_file.fileno())

    def destroy_node(self):
        try:
            self.drive.stop()
            self.csv_file.close()
        except Exception:
            pass
        super().destroy_node()


# ================= MAIN =================
def main():
    rclpy.init()
    node = FollowStopWithMotor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

