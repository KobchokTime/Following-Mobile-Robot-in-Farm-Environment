#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import math, time
from collections import deque
from typing import Optional, List

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy, QoSDurabilityPolicy

from sensor_msgs.msg import LaserScan
from std_msgs.msg import Int32MultiArray  # สมมติ YOLO ส่ง cx ใน data[0]

def stamp_to_sec(stamp) -> float:
    return float(stamp.sec) + float(stamp.nanosec) * 1e-9

class LidarAggregator(Node):
    def __init__(self):
        super().__init__('lidar_aggregator')

        # ---------- Params ----------
        # การรวม LiDAR
        self.declare_parameter('window_mode', 'count')     # 'count' หรือ 'time'
        self.declare_parameter('scans_per_group', 3)       # ใช้เมื่อ window_mode='count'
        self.declare_parameter('max_age_s', 0.5)           # ใช้เมื่อ window_mode='time'
        self.declare_parameter('reduce_method', 'median')  # 'mean' | 'median' | 'min'

        # sector สำหรับคำนวณ front_min ตัวอย่าง
        self.declare_parameter('sector_deg', 30.0)
        self.declare_parameter('angle_offset_deg', 0.0)   # 0 คือด้านหน้าเซนเซอร์
        self.declare_parameter('lidar_min_valid', 0.05)

        # อ่านค่า
        self.window_mode     = self.get_parameter('window_mode').value
        self.scans_per_group = int(self.get_parameter('scans_per_group').value)
        self.max_age_s       = float(self.get_parameter('max_age_s').value)
        self.reduce_method   = self.get_parameter('reduce_method').value

        self.sector_deg      = float(self.get_parameter('sector_deg').value)
        self.angle_offset    = math.radians(float(self.get_parameter('angle_offset_deg').value))
        self.lidar_min_valid = float(self.get_parameter('lidar_min_valid').value)

        # ---------- Buffers ----------
        # เก็บ (t, LaserScan) ล่าสุด ๆ
        self.scan_buf: deque = deque(maxlen=100)
        self.last_yolo_time: Optional[float] = None

        # ---------- I/O ----------
        scan_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST, depth=10,
            durability=QoSDurabilityPolicy.VOLATILE,
        )
        self.sub_scan = self.create_subscription(LaserScan, '/scan', self.cb_scan, qos_profile=scan_qos)
        self.sub_yolo = self.create_subscription(Int32MultiArray, '/target_centroid', self.cb_yolo, 10)

        self.get_logger().info(
            f"Aggregator started | mode={self.window_mode} "
            f"N={self.scans_per_group} max_age={self.max_age_s}s reduce={self.reduce_method}"
        )

    # ---------- Callbacks ----------
    def cb_scan(self, msg: LaserScan):
        self.scan_buf.append((stamp_to_sec(msg.header.stamp), msg))

    def cb_yolo(self, msg: Int32MultiArray):
        t_now = self.get_clock().now().nanoseconds * 1e-9
        t_prev = self.last_yolo_time or (t_now - self.max_age_s)

        # เลือกสแกนที่อยู่ระหว่าง YOLO ก่อนหน้า → ตอนนี้
        scans = self._select_scans(t_prev, t_now)
        agg = self._reduce_scans(scans)

        if agg is None:
            self.get_logger().warn("No LiDAR scans available to aggregate.")
            self.last_yolo_time = t_now
            return

        front_min = self._front_min_from_scan(agg)
        cx = float(msg.data[0]) if len(msg.data) else None

        self.get_logger().info(
            f"YOLO@{t_now:.2f} | scans_used={len(scans)} | front_min={front_min:.3f} | cx={cx}"
        )
        # TODO: ส่งต่อให้ฟิวชัน/คอนโทรลเลอร์

        self.last_yolo_time = t_now

    # ---------- Helpers ----------
    def _select_scans(self, t_prev: float, t_now: float) -> List[LaserScan]:
        vals = [m for (t, m) in self.scan_buf if t_prev <= t <= t_now]
        if self.window_mode == 'count' and len(vals) > self.scans_per_group:
            vals = vals[-self.scans_per_group:]  # เอา N อันล่าสุด
        else:
            # time window: ตัดทิ้งที่อายุมากกว่า max_age_s (กันกรณี YOLO มาช้ากว่าที่คิด)
            vals = [(m) for (t, m) in [(stamp_to_sec(v.header.stamp), v) for v in vals]
                    if t_now - t <= self.max_age_s]
        return vals

    def _reduce_scans(self, scans: List[LaserScan]) -> Optional[LaserScan]:
        if not scans:
            return None
        # ต้องแน่ใจว่าพารามิเตอร์สแกนเท่ากัน (ส่วนใหญ่คงที่)
        n = len(scans[0].ranges)
        # ทำเป็น array shape = (num_scans, num_beams)
        arr = []
        for s in scans:
            r = np.array(s.ranges, dtype=float)
            # ฟิลเตอร์ค่าไม่ valid
            r[~np.isfinite(r)] = np.nan
            r[r < self.lidar_min_valid] = np.nan
            arr.append(r)
        A = np.vstack(arr)  # (k, n)

        if self.reduce_method == 'mean':
            red = np.nanmean(A, axis=0)
        elif self.reduce_method == 'min':
            red = np.nanmin(A, axis=0)
        else:  # median เป็นค่าเริ่มต้น
            red = np.nanmedian(A, axis=0)

        # สร้าง LaserScan ใหม่ (คง metadata ของอันล่าสุด)
        out = LaserScan()
        ref = scans[-1]
        out.header = ref.header
        out.angle_min = ref.angle_min
        out.angle_max = ref.angle_max
        out.angle_increment = ref.angle_increment
        out.time_increment = ref.time_increment
        out.scan_time = ref.scan_time
        out.range_min = ref.range_min
        out.range_max = ref.range_max
        # แทนค่า nan ด้วย inf (ตามคอนเวนชัน LaserScan)
        red[np.isnan(red)] = float('inf')
        out.ranges = red.tolist()
        out.intensities = []  # ไม่รวม
        return out

    def _front_min_from_scan(self, scan: LaserScan) -> float:
        ang_min = scan.angle_min
        ang_inc = scan.angle_increment
        n = len(scan.ranges)
        half = math.radians(self.sector_deg/2.0)
        # สมมติ 0 rad = ด้านหน้าเซนเซอร์ → ชดเชยมุม offset ได้
        target = 0.0 + self.angle_offset
        i0 = max(0, int((target - half - ang_min)/ang_inc))
        i1 = min(n-1, int((target + half - ang_min)/ang_inc))
        vals = [scan.ranges[i] for i in range(i0, i1+1)
                if math.isfinite(scan.ranges[i]) and scan.ranges[i] > self.lidar_min_valid]
        return min(vals) if vals else float('inf')

def main():
    rclpy.init()
    node = LidarAggregator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

