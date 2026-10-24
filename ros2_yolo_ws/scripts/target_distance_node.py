#!/usr/bin/env python3
import math
import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Float32


class ForwardDistanceNode(Node):
    """
    วัดระยะ 'ตรงหน้า' ด้วยข้อมูล LaserScan เพียงอย่างเดียว
    - เลือกคานตรงหน้าจาก sector รอบมุม 0° (หรือชดเชยด้วย angle_offset_deg)
    - กรองค่าใน sector แล้วคำนวณระยะด้วยโหมดที่เลือก: nearest/median/p20
    - publish ที่ /forward_distance (หน่วย: เมตร)
    """

    def __init__(self):
        super().__init__('forward_distance_node')

        # ---------- Parameters ----------
        self.declare_parameter('scan_topic', '/scan')     # ชื่อ topic ของ LaserScan
        self.declare_parameter('sector_deg', 6.0)         # กว้างรวมของ sector (องศา) เช่น 6 -> ±3°
        self.declare_parameter('angle_offset_deg', 180.0)   # ชดเชยมุมติดตั้ง (deg) + = หมุนตามเข็ม
        self.declare_parameter('min_range', 0.05)         # ระยะต่ำสุดที่ยอมรับ (m)
        self.declare_parameter('max_range', 20.0)         # ระยะสูงสุดที่ยอมรับ (m)
        self.declare_parameter('mode', 'nearest')         # 'nearest' | 'median' | 'p20'
        self.declare_parameter('print_hz', 5.0)           # ความถี่การพิมพ์ค่าออกจอ

        # ดึงค่าพารามิเตอร์
        self.scan_topic   = self.get_parameter('scan_topic').get_parameter_value().string_value
        self.sector_deg   = float(self.get_parameter('sector_deg').get_parameter_value().double_value)
        self.angle_offset = math.radians(
            float(self.get_parameter('angle_offset_deg').get_parameter_value().double_value)
        )
        self.min_range    = float(self.get_parameter('min_range').get_parameter_value().double_value)
        self.max_range    = float(self.get_parameter('max_range').get_parameter_value().double_value)
        self.mode         = self.get_parameter('mode').get_parameter_value().string_value.strip().lower()
        self.print_period = 1.0 / max(0.1, float(self.get_parameter('print_hz').get_parameter_value().double_value))

        # ---------- QoS ----------
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=50,
        )

        # ---------- I/O ----------
        self.scan_sub = self.create_subscription(LaserScan, self.scan_topic, self.on_scan, qos)
        self.pub = self.create_publisher(Float32, '/forward_distance', 10)

        self.last_print_time = self.get_clock().now()
        self.latest_dist = None

        self.get_logger().info(
            f'Started: scan_topic={self.scan_topic}, sector_deg={self.sector_deg:.2f}, '
            f'angle_offset_deg={math.degrees(self.angle_offset):.2f}, '
            f'min_range={self.min_range}m, max_range={self.max_range}m, mode={self.mode}'
        )

    def on_scan(self, scan: LaserScan):
        """เลือกคานภายใน sector รอบ 'มุมตรงหน้า + offset' แล้วคำนวณระยะตามโหมดที่กำหนด"""
        n = len(scan.ranges)
        if n == 0:
            return

        half_sector = math.radians(self.sector_deg / 2.0)

        # ใช้มุม 0 + offset เป็น 'ตรงหน้า'
        target_angle = 0.0 + self.angle_offset
        #target_angle = 180.0

        # index ใกล้มุม target_angle ที่สุด
        try:
            center_index = int(round((target_angle - scan.angle_min) / scan.angle_increment))
        except ZeroDivisionError:
            return

        # เก็บ index ทั้งหมดที่อยู่ใน sector รอบ target_angle
        indices = []
        # ซ้ายจาก center_index รวม center ด้วย
        i = max(0, min(center_index, n - 1))
        while i >= 0:
            angle_i = scan.angle_min + i * scan.angle_increment
            if abs(angle_i - target_angle) <= half_sector:
                indices.append(i)
                i -= 1
            else:
                break

        # ขวาจาก center_index+1
        j = min(center_index + 1, n - 1)
        while j < n:
            angle_j = scan.angle_min + j * scan.angle_increment
            if abs(angle_j - target_angle) <= half_sector:
                indices.append(j)
                j += 1
            else:
                break

        if not indices:
            self.latest_dist = None
            return

        # กรองค่า invalid + ช่วงระยะสมเหตุผล
        vals = []
        rng = scan.ranges
        for idx in indices:
            r = rng[idx]
            if math.isnan(r) or math.isinf(r):
                continue
            if self.min_range <= r <= self.max_range:
                vals.append(r)

        if not vals:
            self.latest_dist = None
            return

        # เลือกวิธีสรุประยะ
        mode = self.mode
        if mode == 'nearest':
            dist_m = float(min(vals))
        elif mode == 'p20':
            dist_m = float(np.percentile(vals, 20))
        else:  # 'median' และกรณีอื่นให้ fallback เป็น median
            dist_m = float(np.median(vals))

        self.latest_dist = dist_m
        self.pub.publish(Float32(data=dist_m))

        # พิมพ์ค่าตามช่วงเวลา
        now = self.get_clock().now()
        if (now - self.last_print_time).nanoseconds * 1e-9 >= self.print_period:
            deg = self.sector_deg / 2.0
            self.get_logger().info(
                f'Forward distance ≈ {dist_m*100:.1f} cm  (sector=±{deg:.1f}°, offset={math.degrees(self.angle_offset):.1f}°)'
            )
            self.last_print_time = now


def main():
    rclpy.init()
    node = ForwardDistanceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()

