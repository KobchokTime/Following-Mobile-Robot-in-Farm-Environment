#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Follow_Stop_Log.py
#
# - คำนวณ front_min จากกรวย (sector_deg) รอบมุมที่กำหนด (angle_offset_deg)
# - รวม YOLO centroid (/target_centroid) กับ LiDAR (/scan)
# - State machine: NO_LIDAR, TARGET_TIMEOUT, WAIT_INIT, OK, TOO_CLOSE, RESUMING
# - พิมพ์สถานะแบบอ่านง่าย + บันทึก CSV พร้อมคอลัมน์สีสัญญาณไฟ
# - มีโหมด print-only (ไม่สั่งหุ่น) เผื่อทดสอบ/เก็บ log อย่างเดียว
#
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


def fmt(x, nd=3):
    return f"{x:.{nd}f}" if x is not None else "None"


@dataclass
class Centroid:
    cx_px: Optional[float] = None
    ts: Optional[Time] = None


class FollowStopLogger(Node):
    def __init__(self):
        super().__init__('follow_stop_logger')

        # ===== Parameters =====
        self.declare_parameter('hfov_deg', 70.0)
        self.declare_parameter('image_width', 640)
        self.declare_parameter('alpha_cx', 0.3)
        self.declare_parameter('cx_deadband', 12.0)

        self.declare_parameter('angle_offset_deg', 180.0)  # 0=หน้า, 180=หลัง
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
        self.declare_parameter('print_only', True)
        self.declare_parameter('csv_path', '~/logs/follow_stop_log.csv')

        # ===== Read params =====
        self.hfov_deg    = float(self.get_parameter('hfov_deg').value)
        self.image_width = int(self.get_parameter('image_width').value)
        self.alpha_cx    = float(self.get_parameter('alpha_cx').value)
        self.cx_deadband = float(self.get_parameter('cx_deadband').value)

        self.sector_deg  = float(self.get_parameter('sector_deg').value)
        self.lidar_min_valid = float(self.get_parameter('lidar_min_valid').value)
        self.angle_offset_deg = float(self.get_parameter('angle_offset_deg').value)

        self.init_dist   = float(self.get_parameter('init_dist').value)
        self.confirm_needed = int(self.get_parameter('confirm_needed').value)
        self.stop_dist   = float(self.get_parameter('stop_dist').value)
        self.slow_dist   = float(self.get_parameter('slow_dist').value)
        self.resume_margin = float(self.get_parameter('resume_margin').value)
        self.target_timeout = float(self.get_parameter('target_timeout').value)
        self.kx          = float(self.get_parameter('kx').value)
        self.w_max       = float(self.get_parameter('w_max').value)
        self.timer_hz    = float(self.get_parameter('timer_hz').value)
        self.print_only  = bool(self.get_parameter('print_only').value)
        self.csv_path    = os.path.expanduser(str(self.get_parameter('csv_path').value))

        # ===== State =====
        self.scan: Optional[LaserScan] = None
        self.centroid = Centroid()
        self.cx_filt: Optional[float] = None
        self.locked = False
        self.confirm_count = 0
        self.last_state = "INIT"

        # ===== ROS I/O =====
        scan_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=5,
            durability=QoSDurabilityPolicy.VOLATILE,
        )
        self.sub_scan = self.create_subscription(LaserScan, '/scan', self.cb_scan, qos_profile=scan_qos)
        self.sub_cx = self.create_subscription(Int32MultiArray, '/target_centroid', self.cb_centroid, 10)
        self.pub_cmd = self.create_publisher(Twist, '/cmd_vel', 10)

        # ===== CSV Logger =====
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        self.csv_file = open(self.csv_path, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(['stamp_sec','state','color',
                                  'front_min_m','cx_px','cx_deg','cx_filt','v','w'])
        self.get_logger().info(f"FollowStopLogger started (print_only={self.print_only})")

        self.timer = self.create_timer(1.0/self.timer_hz, self.on_timer)

    # ---------- Callbacks ----------
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
                self.cx_filt = self.alpha_cx*cx + (1.0-self.alpha_cx)*self.cx_filt

    # ---------- Helpers ----------
    def current_time_sec(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def calc_front_min(self) -> Optional[float]:
        """เลือกช่วงกรวยรอบ angle_offset_deg (องศา)"""
        if not self.scan or not self.scan.ranges:
            return None
        ang_min = self.scan.angle_min
        ang_inc = self.scan.angle_increment
        n = len(self.scan.ranges)

        center = math.radians(self.angle_offset_deg)
        half   = math.radians(self.sector_deg/2.0)

        def ang2idx(theta: float) -> int:
            while theta < ang_min:
                theta += 2*math.pi
            while theta >= ang_min + n*ang_inc:
                theta -= 2*math.pi
            return int((theta-ang_min)/ang_inc)

        i_lo = ang2idx(center-half)
        i_hi = ang2idx(center+half)

        if i_lo <= i_hi:
            idxs = range(i_lo, i_hi+1)
        else:
            idxs = list(range(i_lo,n)) + list(range(0,i_hi+1))

        vals = [self.scan.ranges[i] for i in idxs
                if math.isfinite(self.scan.ranges[i]) and self.scan.ranges[i] > self.lidar_min_valid]
        return min(vals) if vals else None

    def calc_cx_deg(self, cx_px: Optional[float]) -> Optional[float]:
        if cx_px is None or self.image_width <= 0:
            return None
        center = (self.image_width-1)/2.0
        px_per_deg = self.image_width/self.hfov_deg
        return (cx_px-center)/px_per_deg

    def pick_color(self, state: str) -> str:
        if state in ('OK','RESUMING'): return 'GREEN'
        if state in ('WAIT_INIT','TARGET_TIMEOUT'): return 'YELLOW'
        return 'RED'

    # ---------- Main loop ----------
    def on_timer(self):
        now = self.get_clock().now()
        front_min = self.calc_front_min()
        cx = self.centroid.cx_px
        cx_deg = self.calc_cx_deg(cx)
        target_age = (now-self.centroid.ts).nanoseconds*1e-9 if self.centroid.ts else None

        state,v,w = "OK",0.0,0.0

        if front_min is None:
            state="NO_LIDAR"
        elif (target_age is None) or (target_age>self.target_timeout) or (cx is None):
            state="TARGET_TIMEOUT"
            self.locked=False; self.confirm_count=0
        else:
            if not self.locked:
                if front_min>=self.init_dist:
                    self.confirm_count+=1
                    state="WAIT_INIT"
                    if self.confirm_count>=self.confirm_needed:
                        self.locked=True; self.confirm_count=0
                else:
                    state="WAIT_INIT"; self.confirm_count=0
            if self.locked:
                if front_min<=self.stop_dist:
                    state="TOO_CLOSE"; v,w=0.0,0.0
                else:
                    state="OK"
                    margin=max(0.0,min(1.0,(front_min-self.stop_dist)/(self.slow_dist-self.stop_dist+1e-6)))
                    v=0.02+0.16*margin
                    err_px=0.0 if cx is None else (cx-(self.image_width-1)/2.0)
                    if abs(err_px)<self.cx_deadband: err_px=0.0
                    w=-self.kx*err_px
                    w=max(-self.w_max,min(self.w_max,w))
                if state=="TOO_CLOSE" and front_min>=(self.stop_dist+self.resume_margin):
                    state="RESUMING"; v=0.02; w=0.0

        if not self.print_only:
            msg=Twist(); msg.linear.x=float(v); msg.angular.z=float(w)
            self.pub_cmd.publish(msg)

        color=self.pick_color(state)
        self.get_logger().info(
            f"[{state}] front_min={fmt(front_min)} cx={fmt(cx)} cx_deg={fmt(cx_deg)} "
            f"locked={self.locked} v={v:.2f} w={w:.2f} color={color}"
        )

        self.csv_writer.writerow([
            f"{self.current_time_sec():.3f}", state, color,
            f"{front_min:.3f}" if front_min else "",
            f"{cx:.1f}" if cx else "",
            f"{cx_deg:.2f}" if cx_deg else "",
            f"{self.cx_filt:.1f}" if self.cx_filt else "",
            f"{v:.3f}", f"{w:.3f}"
        ])
        self.csv_file.flush(); os.fsync(self.csv_file.fileno())
        self.last_state=state

    def destroy_node(self):
        try: self.csv_file.close()
        except: pass
        super().destroy_node()


def main():
    rclpy.init()
    node=FollowStopLogger()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node(); rclpy.shutdown()

if __name__=="__main__":
    main()

