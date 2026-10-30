#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lidar sectorizer + (optional) aggregation
- แบ่งสแกนเป็นหลาย sector รอบตัว แล้วให้ค่า min/median ต่อ sector
- เผยแพร่ /scan_sectors เป็น Float32MultiArray (len = num_sectors)
- มี helper สำหรับ map YOLO cx_px -> sector index

รัน:
  python3 sectorizer.py --ros-args \
    -p window_mode:=count -p scans_per_group:=3 -p reduce_method:=median \
    -p num_sectors:=8 -p sector_span_deg:=45.0 -p start_angle_deg:=-180.0 \
    -p lidar_min_valid:=0.05 \
    -p pub_front_min:=true -p front_sector_center_deg:=0.0 -p front_sector_width_deg:=30.0 \
    -p camera_hfov_deg:=70.0 -p image_width:=640
"""

import math
from collections import deque
from typing import Optional, List

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy, QoSDurabilityPolicy
from std_msgs.msg import Float32MultiArray, Int32MultiArray
from sensor_msgs.msg import LaserScan

def stamp_to_sec(stamp) -> float:
    return float(stamp.sec) + float(stamp.nanosec) * 1e-9

class LidarSectorizer(Node):
    def __init__(self):
        super().__init__('lidar_sectorizer')

        # ===== Aggregation params =====
        self.declare_parameter('window_mode', 'count')     # 'count' | 'time'
        self.declare_parameter('scans_per_group', 3)
        self.declare_parameter('max_age_s', 0.5)
        self.declare_parameter('reduce_method', 'median')  # 'mean'|'median'|'min'
        self.declare_parameter('lidar_min_valid', 0.05)

        # ===== Sectorization params =====
        self.declare_parameter('num_sectors', 8)           # จำนวน sector รอบตัว
        self.declare_parameter('sector_span_deg', 45.0)    # กว้างต่อ sector (num_sectors * span ≈ 360)
        self.declare_parameter('start_angle_deg', -180.0)  # มุมเริ่มต้น (rad 0 = ด้านหน้าของ LiDAR)
        # ตัวเลือก: ส่ง front_min ของ “กรวยด้านหน้า” แยก
        self.declare_parameter('pub_front_min', True)
        self.declare_parameter('front_sector_center_deg', 0.0)
        self.declare_parameter('front_sector_width_deg', 30.0)

        # ===== Camera mapping (optional) =====
        self.declare_parameter('camera_hfov_deg', 70.0)
        self.declare_parameter('image_width', 640)

        # read
        self.window_mode     = str(self.get_parameter('window_mode').value)
        self.scans_per_group = int(self.get_parameter('scans_per_group').value)
        self.max_age_s       = float(self.get_parameter('max_age_s').value)
        self.reduce_method   = str(self.get_parameter('reduce_method').value)
        self.lidar_min_valid = float(self.get_parameter('lidar_min_valid').value)

        self.num_sectors     = int(self.get_parameter('num_sectors').value)
        self.sector_span     = math.radians(float(self.get_parameter('sector_span_deg').value))
        self.start_angle     = math.radians(float(self.get_parameter('start_angle_deg').value))

        self.pub_front_min   = bool(self.get_parameter('pub_front_min').value)
        self.front_center    = math.radians(float(self.get_parameter('front_sector_center_deg').value))
        self.front_width     = math.radians(float(self.get_parameter('front_sector_width_deg').value))

        self.cam_hfov        = float(self.get_parameter('camera_hfov_deg').value)
        self.img_w           = int(self.get_parameter('image_width').value)

        # buffers
        self.scan_buf: deque = deque(maxlen=250)
        self.last_yolo_time: Optional[float] = None
        self.last_cx: Optional[float] = None

        # I/O
        scan_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=20,
            durability=QoSDurabilityPolicy.VOLATILE,
        )
        self.sub_scan = self.create_subscription(LaserScan, '/scan', self.cb_scan, qos_profile=scan_qos)
        self.sub_yolo = self.create_subscription(Int32MultiArray, '/target_centroid', self.cb_yolo, 10)

        self.pub_sectors = self.create_publisher(Float32MultiArray, '/scan_sectors', 10)

        self.get_logger().info(
            f"Sectorizer started | mode={self.window_mode} N={self.scans_per_group} "
            f"reduce={self.reduce_method} sectors={self.num_sectors} span_deg={math.degrees(self.sector_span):.1f}"
        )

    # ---------- callbacks ----------
    def cb_scan(self, msg: LaserScan):
        self.scan_buf.append((stamp_to_sec(msg.header.stamp), msg))

    def cb_yolo(self, msg: Int32MultiArray):
        t_now = self.get_clock().now().nanoseconds * 1e-9
        t_prev = self.last_yolo_time or (t_now - self.max_age_s)
        self.last_yolo_time = t_now

        # เก็บ cx ไว้เผื่อแม็พ sector
        self.last_cx = float(msg.data[0]) if len(msg.data) else None

        scans = self._select_scans(t_prev, t_now)
        agg = self._reduce_scans(scans)
        if agg is None:
            self.get_logger().warn("No scans to aggregate; skip publish.")
            return

        # คำนวณ min ต่อ sector
        mins = self.sector_minima(agg,
                                  num_sectors=self.num_sectors,
                                  sector_span=self.sector_span,
                                  start_angle=self.start_angle,
                                  rmin=self.lidar_min_valid)

        # publish
        m = Float32MultiArray()
        m.data = [float(x) for x in mins]
        self.pub_sectors.publish(m)

        # optional: front_min
        if self.pub_front_min:
            fmin = self._front_min_from_scan(agg, center=self.front_center, width=self.front_width)
            # พิมพ์ช่วยวิเคราะห์ + แสดง sector index ที่ YOLO น่าจะอยู่
            sec_idx = self.map_cx_to_sector(self.last_cx, self.img_w, self.cam_hfov,
                                            self.num_sectors, self.start_angle, self.sector_span)
            self.get_logger().info(
                f"scans_used={len(scans)} | front_min={fmin:.3f} | "
                f"cx={self.last_cx} -> sector#{sec_idx}"
            )

    # ---------- selection / aggregation ----------
    def _select_scans(self, t_prev, t_now) -> List[LaserScan]:
        vals = [m for (t, m) in self.scan_buf if t_prev <= t <= t_now]
        if self.window_mode == 'count':
            if len(vals) > self.scans_per_group:
                vals = vals[-self.scans_per_group:]
        else:
            keep = []
            for m in vals:
                tm = stamp_to_sec(m.header.stamp)
                if t_now - tm <= self.max_age_s:
                    keep.append(m)
            vals = keep
        return vals

    def _reduce_scans(self, scans: List[LaserScan]) -> Optional[LaserScan]:
        if not scans:
            return None
        ref = scans[-1]
        n_ref = len(ref.ranges)
        ref_ang = ref.angle_min + np.arange(n_ref) * ref.angle_increment

        def resample_to_ref(s: LaserScan) -> np.ndarray:
            r = np.array(s.ranges, dtype=float)
            ang = s.angle_min + np.arange(len(r)) * s.angle_increment
            valid = np.isfinite(r) & (r > self.lidar_min_valid)
            if valid.sum() < 2:
                return np.full_like(ref_ang, np.nan, dtype=float)
            y = np.interp(ref_ang, ang[valid], r[valid])
            y[(ref_ang < ang[valid][0]) | (ref_ang > ang[valid][-1])] = np.nan
            return y

        mats = [resample_to_ref(s) for s in scans]
        A = np.vstack(mats)
        method = (self.reduce_method or 'median').lower()
        if method == 'mean':
            red = np.nanmean(A, axis=0)
        elif method == 'min':
            red = np.nanmin(A, axis=0)
        else:
            red = np.nanmedian(A, axis=0)

        out = LaserScan()
        out.header          = ref.header
        out.angle_min       = ref.angle_min
        out.angle_max       = ref.angle_max
        out.angle_increment = ref.angle_increment
        out.time_increment  = ref.time_increment
        out.scan_time       = ref.scan_time
        out.range_min       = ref.range_min
        out.range_max       = ref.range_max
        red[np.isnan(red)] = float('inf')
        out.ranges = red.tolist()
        out.intensities = []
        return out

    # ---------- sectorization ----------
    @staticmethod
    def _normalize_angle(a):
        """wrap to (-pi, pi]"""
        a = math.fmod(a + math.pi, 2*math.pi)
        if a < 0:
            a += 2*math.pi
        return a - math.pi

    def sector_minima(self, scan: LaserScan, num_sectors: int, sector_span: float,
                      start_angle: float, rmin: float) -> List[float]:
        """
        หาระยะต่ำสุดในแต่ละ sector
        - num_sectors * sector_span ควร ≈ 2π (360°) (เหลื่อมเล็กน้อยได้)
        - start_angle: มุมของขอบซ้ายของ sector#0 (rad), โดย 0 rad คือ “ด้านหน้าของ LiDAR”
        """
        n = len(scan.ranges)
        ang_min = scan.angle_min
        ang_inc = scan.angle_increment

        # สร้างขอบเขต sector ตาม [start + k*span, start + (k+1)*span)
        mins = [float('inf')] * num_sectors
        for i in range(n):
            r = scan.ranges[i]
            if not math.isfinite(r) or r <= rmin:
                continue
            ang = ang_min + i * ang_inc
            # แปลงมุมเป็นออฟเซ็ตจาก start_angle แล้วหาร sector index
            rel = self._normalize_angle(ang - start_angle)
            # ทำให้ rel อยู่ใน [0, 2π)
            if rel < 0:
                rel += 2*math.pi
            idx = int(rel // sector_span)
            if 0 <= idx < num_sectors:
                if r < mins[idx]:
                    mins[idx] = r

        # ไม่มีข้อมูล -> inf
        return mins

    def _front_min_from_scan(self, scan: LaserScan, center: float, width: float) -> float:
        ang_min = scan.angle_min
        ang_inc = scan.angle_increment
        n = len(scan.ranges)
        half = width / 2.0
        i0 = max(0, int((center - half - ang_min) / ang_inc))
        i1 = min(n - 1, int((center + half - ang_min) / ang_inc))
        vals = [
            scan.ranges[i] for i in range(i0, i1 + 1)
            if math.isfinite(scan.ranges[i]) and scan.ranges[i] > self.lidar_min_valid
        ]
        return min(vals) if vals else float('inf')

    # ---------- camera → sector mapping ----------
    def map_cx_to_sector(self, cx_px: Optional[float], img_w: int, hfov_deg: float,
                         num_sectors: int, start_angle: float, sector_span: float) -> Optional[int]:
        """
        แปลง centroid X (px) → มุมในกล้อง → มุมบนเฟรม LiDAR → sector index
        giảใช้ว่าแกน 0 rad ของ LiDAR = แกนกลางภาพ (ต้องปรับ offset เองถ้าไม่ตรง)
        """
        if cx_px is None or img_w <= 1 or hfov_deg <= 0:
            return None
        center = (img_w - 1) / 2.0
        px_per_deg = img_w / hfov_deg
        yaw_cam_deg = (cx_px - center) / px_per_deg           # +ขวา/-ซ้าย
        yaw_cam = math.radians(yaw_cam_deg)

        # สมมุติกล้องหันทิศเดียวกับแกน 0 rad ของ LiDAR (ถ้าไม่ ให้บวก offset ที่นี่)
        ang = yaw_cam

        # คำนวณ sector เหมือนใน sector_minima()
        rel = self._normalize_angle(ang - start_angle)
        if rel < 0:
            rel += 2 * math.pi
        idx = int(rel // sector_span)
        return idx if 0 <= idx < num_sectors else None


def main():
    rclpy.init()
    node = LidarSectorizer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
