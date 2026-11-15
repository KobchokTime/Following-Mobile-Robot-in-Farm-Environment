#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Follow_Stop_Log.py
#
# - คำนวณ front_min จากกรวยด้านหน้า (sector_deg)
# - รวม YOLO centroid (/target_centroid) กับ LiDAR (/scan)
# - State machine: NO_LIDAR, TARGET_TIMEOUT, WAIT_INIT, OK, TOO_CLOSE, RESUMING
# - พิมพ์สถานะแบบอ่านง่าย + บันทึก CSV พร้อมคอลัมน์สีสัญญาณไฟ
# - มีโหมด print-only (ไม่สั่งหุ่น) เผื่อทดสอบ/เก็บ log อย่างเดียว
#
# ใช้งาน:
# python3 ~/ros2_yolo_ws/scripts/Follow_Stop_Log.py --ros-args \
#   -p sector_deg:=30.0 -p hfov_deg:=70.0 -p image_width:=640 \
#   -p init_dist:=1.0 -p confirm_needed:=5 \
#   -p stop_dist:=0.5 -p slow_dist:=1.2 -p resume_margin:=0.05 \
#   -p kx:=0.0015 -p w_max:=1.0 \
#   -p target_timeout:=1.8 -p alpha_cx:=0.3 -p cx_deadband:=12.0 \
#   -p lidar_min_valid:=0.05 -p timer_hz:=10.0 \
#   -p csv_path:="~/logs/follow_stop_log.csv" -p print_only:=true
#
import csv
import math
import os
from dataclasses import dataclass
from typing import Optional, Tuple

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
        # camera / yolo
        self.declare_parameter('hfov_deg', 70.0)
        self.declare_parameter('image_width', 640)
        self.declare_parameter('alpha_cx', 0.3)        # EMA ของ cx
        self.declare_parameter('cx_deadband', 12.0)    # พิกเซล

        # lidar / fusion
        self.declare_parameter('angle_offset_deg', 180.0)
        self.declare_parameter('sector_deg', 30.0)     # ขนาดกรวยด้านหน้า
        self.declare_parameter('lidar_min_valid', 0.05)

        # follow/stop logic
        self.declare_parameter('init_dist', 1.0)       # ระยะขั้นต่ำก่อน lock ชุดแรก
        self.declare_parameter('confirm_needed', 5)    # เฟรมที่ต้องยืนยันก่อน lock
        self.declare_parameter('stop_dist', 0.5)
        self.declare_parameter('slow_dist', 1.2)
        self.declare_parameter('resume_margin', 0.05)
        self.declare_parameter('target_timeout', 1.8)  # วินาที
        self.declare_parameter('kx', 0.0015)           # เกนหมุนตาม cx
        self.declare_parameter('w_max', 1.0)           # จำกัดอัตราหมุน
        self.declare_parameter('timer_hz', 10.0)
        self.declare_parameter('print_only', True)
        self.declare_parameter('csv_path', '~/logs/follow_stop_log.csv')

        # read params
        self.hfov_deg    = float(self.get_parameter('hfov_deg').value)
        self.image_width = int(self.get_parameter('image_width').value)
        self.alpha_cx    = float(self.get_parameter('alpha_cx').value)
        self.cx_deadband = float(self.get_parameter('cx_deadband').value)

        self.sector_deg  = float(self.get_parameter('sector_deg').value)
        self.lidar_min_valid = float(self.get_parameter('lidar_min_valid').value)
        self.angle_offset_rad = math.radians(float(self.get_parameter('angle_offset_deg').value))

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

        # ===== Publishers/Subscribers =====
        # LaserScan → ใช้ QoS แบบ SensorData (best-effort) เพื่อลด incompatible QoS
        scan_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=5,
            durability=QoSDurabilityPolicy.VOLATILE,
        )
        self.sub_scan = self.create_subscription(LaserScan, '/scan', self.cb_scan, qos_profile=scan_qos)

        # YOLO centroid → ปกติพอใช้ RELIABLE ค่า default
        self.sub_cx = self.create_subscription(Int32MultiArray, '/target_centroid', self.cb_centroid, 10)

        # cmd_vel (ทางเลือก)
        self.pub_cmd = self.create_publisher(Twist, '/cmd_vel', 10)

        # ===== Logging (CSV) =====
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        self.csv_file = open(self.csv_path, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow([
            'stamp_sec', 'state', 'color',
            'front_min_m', 'cx_px', 'cx_deg', 'cx_filt',
            'v', 'w'
        ])
        self.get_logger().info(f"FollowStopLogger started (print_only={self.print_only})")

        # ===== Timer =====
        self.timer = self.create_timer(1.0 / self.timer_hz, self.on_timer)

    # --------------- Callbacks ---------------
    def cb_scan(self, msg: LaserScan):
        self.scan = msg

    def cb_centroid(self, msg: Int32MultiArray):
        # data: [cx_px, <optional cy>]
        cx = float(msg.data[0]) if len(msg.data) > 0 else None
        self.centroid.cx_px = cx
        self.centroid.ts = self.get_clock().now()

        # EMA filter
        if cx is not None:
            if self.cx_filt is None:
                self.cx_filt = cx
            else:
                self.cx_filt = self.alpha_cx * cx + (1.0 - self.alpha_cx) * self.cx_filt

    # --------------- Helpers ---------------
    def current_time_sec(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def calc_front_min(self) -> Optional[float]:
        """
        เลือกเฉพาะรังสีในกรวยด้านหน้า ±sector_deg/2 รอบมุม 0 rad
        """
        if not self.scan or not self.scan.ranges:
            return None

        ang_min = self.scan.angle_min
        ang_inc = self.scan.angle_increment
        n = len(self.scan.ranges)

        target_angle = 0.0 + self.angle_offset_rad # default = 0.0 rad
        sector_rad_half = math.radians(self.sector_deg / 2.0)
        i_lo = max(0, int(( -sector_rad_half - ang_min) / ang_inc))
        i_hi = min(n - 1, int(( +sector_rad_half - ang_min) / ang_inc))

        cand = []
        for i in range(i_lo, i_hi + 1):
            r = self.scan.ranges[i]
            if math.isfinite(r) and r > self.lidar_min_valid:
                cand.append(r)

        return min(cand) if cand else None

    def calc_cx_deg(self, cx_px: Optional[float]) -> Optional[float]:
        if cx_px is None or self.image_width <= 0:
            return None
        # กึ่งกลางพิกัด (0..W-1) → center = (W-1)/2
        center = (self.image_width - 1) / 2.0
        px_per_deg = self.image_width / self.hfov_deg
        return (cx_px - center) / px_per_deg  # +ขวา/-ซ้าย (ตามแกนอิมเมจ)

    def pick_color(self, state: str) -> str:
        # ไฟสถานะ 3 สี:
        # - เขียว: OK, RESUMING
        # - เหลือง: WAIT_INIT, TARGET_TIMEOUT
        # - แดง: NO_LIDAR, TOO_CLOSE
        if state in ('OK', 'RESUMING'):
            return 'GREEN'
        if state in ('WAIT_INIT', 'TARGET_TIMEOUT'):
            return 'YELLOW'
        return 'RED'

    # --------------- Timer (main loop) ---------------
    def on_timer(self):
        now = self.get_clock().now()

        # LiDAR (front min)
        front_min = self.calc_front_min()

        # YOLO centroid
        cx = self.centroid.cx_px
        cx_deg = self.calc_cx_deg(cx)

        # ตรวจ timeout ของ YOLO target
        target_age = None
        if self.centroid.ts is not None:
            target_age = (now - self.centroid.ts).nanoseconds * 1e-9

        # ===== State machine =====
        state = "OK"
        v = 0.0
        w = 0.0

        # 1) ไม่มี LiDAR
        if front_min is None:
            state = "NO_LIDAR"

        # 2) YOLO หายไปนาน
        elif (target_age is None) or (target_age > self.target_timeout) or (cx is None):
            state = "TARGET_TIMEOUT"
            self.locked = False
            self.confirm_count = 0

        else:
            # มีทั้ง LiDAR และ YOLO สด
            # เงื่อนไข lock เริ่มแรก: ต้องเห็น target >= init_dist และยืนยันครบ confirm_needed
            if not self.locked:
                if front_min >= self.init_dist:
                    self.confirm_count += 1
                    state = "WAIT_INIT"
                    if self.confirm_count >= self.confirm_needed:
                        self.locked = True
                        self.confirm_count = 0
                        # ตรงนี้ถือว่าเริ่มติดตามได้
                else:
                    # ยังไม่ถึงระยะ init → ถือว่ายังไม่พร้อมล็อก
                    state = "WAIT_INIT"
                    self.confirm_count = 0
            # ถ้า lock แล้ว → ควบคุมและสลับ state ตามระยะ
            if self.locked:
                # zone: too close → หยุดนิ่ง
                if front_min <= self.stop_dist:
                    state = "TOO_CLOSE"
                    v = 0.0
                    w = 0.0
                else:
                    # zone: slow/ok → ให้ v ต่ำๆ ปลอดภัย และหันตาม cx_deg
                    state = "OK"
                    # v แบบง่าย ๆ (ตามระยะ) แต่จำกัดไม่ให้เร็วเกินไป
                    # จะกำหนดเป็นสัดส่วนกับส่วนต่าง slow_dist เพื่อคุมให้ค่อยๆ เคลื่อน
                    # คุณสามารถปรับสมการนี้ได้ตามต้องการ
                    margin = max(0.0, min(1.0, (front_min - self.stop_dist) / (self.slow_dist - self.stop_dist + 1e-6)))
                    v = 0.02 + 0.16 * margin  # 0.02..0.18 m/s (ตามลอจิกงานเก็บ log)
                    # deadband เพื่อลดการส่าย
                    err_px = 0.0 if cx is None else (cx - (self.image_width - 1) / 2.0)
                    if abs(err_px) < self.cx_deadband:
                        err_px = 0.0
                    w = - self.kx * err_px
                    w = max(-self.w_max, min(self.w_max, w))

                # hysteresis สำหรับออกจาก stop zone
                if state == "TOO_CLOSE" and front_min >= (self.stop_dist + self.resume_margin):
                    state = "RESUMING"
                    v = 0.02
                    # ปล่อยให้ w ตามเดิม (คง 0) เพื่อปลอดภัย
                    w = 0.0

        # ===== Publish command (optional) =====
        if not self.print_only:
            msg = Twist()
            msg.linear.x = float(v)
            msg.angular.z = float(w)
            self.pub_cmd.publish(msg)

        # ===== Log print =====
        color = self.pick_color(state)
        self.get_logger().info(
            f"[{state}] front_min={fmt(front_min)} "
            f"cx={fmt(cx)} cx_deg={fmt(cx_deg)} cx_filt={fmt(self.cx_filt)} "
            f"locked={self.locked} v={v:.2f} w={w:.2f} color={color}"
        )

        # ===== CSV =====
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
        ])
        # flush เป็นระยะเพื่อกันข้อมูลหาย
        self.csv_file.flush()
        os.fsync(self.csv_file.fileno())

        self.last_state = state

    # --------------- Shutdown ---------------
    def destroy_node(self):
        try:
            self.csv_file.close()
        except Exception:
            pass
        super().destroy_node()


def main():
    rclpy.init()
    node = FollowStopLogger()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

