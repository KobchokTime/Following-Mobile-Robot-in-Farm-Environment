#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from rclpy.clock import ClockType
from rclpy.duration import Duration

from sensor_msgs.msg import LaserScan
from std_msgs.msg import Int32MultiArray

import csv
import math
import os
import time
from dataclasses import dataclass
from typing import Optional, Dict


def fmt(x: Optional[float], nd=3):
    if x is None:
        return ""
    try:
        return f"{x:.{nd}f}"
    except Exception:
        return str(x)


@dataclass
class CentroidMsg:
    cx_px: Optional[int]
    cy_px: Optional[int]
    stamp: float


class FusionLogger(Node):
    def __init__(self):
        super().__init__("fusion_logger")

        # ---------- Parameters ----------
        self.declare_parameter("hfov_deg", 70.0)              # camera HFOV
        self.declare_parameter("img_width_px", 640)           # camera width
        self.declare_parameter("lidar_min_valid", 0.05)       # min valid range
        self.declare_parameter("target_timeout", 1.5)         # sec
        self.declare_parameter("timer_hz", 10.0)              # Hz
        self.declare_parameter("csv_path", os.path.expanduser("~/logs/fusion_log.csv"))

        # guard/lock parameters (เหมือน follow node)
        self.declare_parameter("init_dist", 1.0)              # m
        self.declare_parameter("confirm_needed", 5)           # frames
        self.declare_parameter("stop_dist", 0.5)              # m
        self.declare_parameter("resume_margin", 0.05)         # m

        # state → color mapping (ปรับได้)
        self.declare_parameter(
            "state_colors",
            "Follow:green,WaitingInit:yellow,TooClose:red,Timeout:red,LiDARGap:yellow"
        )

        self.hfov_deg = float(self.get_parameter("hfov_deg").value)
        self.img_w = int(self.get_parameter("img_width_px").value)
        self.lidar_min_valid = float(self.get_parameter("lidar_min_valid").value)
        self.target_timeout = float(self.get_parameter("target_timeout").value)
        self.timer_hz = float(self.get_parameter("timer_hz").value)
        self.csv_path = os.path.expanduser(self.get_parameter("csv_path").value)

        self.init_dist = float(self.get_parameter("init_dist").value)
        self.confirm_needed = int(self.get_parameter("confirm_needed").value)
        self.stop_dist = float(self.get_parameter("stop_dist").value)
        self.resume_margin = float(self.get_parameter("resume_margin").value)

        # parse state → color
        self.state_color_map: Dict[str, str] = self._parse_state_colors(
            self.get_parameter("state_colors").value
        )

        # ---------- Internal buffers ----------
        self.scan_msg: Optional[LaserScan] = None
        self.scan_stamp: Optional[float] = None
        self.cent: Optional[CentroidMsg] = None

        # locking/confirm logic
        self.locked: bool = False
        self.init_ok_count: int = 0

        # ---------- QoS ----------
        # LiDAR บางตัวใช้ BEST_EFFORT → ตั้ง subscriber ให้รับได้ทั้งสองแบบ
        qos_lidar = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
        )
        # YOLO topic โดยปกติ RELIABLE; ใช้ default QoS ก็พอ
        qos_yolo = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
        )

        # ---------- Subscribers ----------
        self.sub_scan = self.create_subscription(
            LaserScan, "/scan", self.on_scan, qos_lidar
        )
        self.sub_cent = self.create_subscription(
            Int32MultiArray, "/target_centroid", self.on_centroid, qos_yolo
        )

        # ---------- Timer ----------
        period = 1.0 / max(1e-6, self.timer_hz)
        self.timer = self.create_timer(period, self.on_timer)

        # ---------- CSV ----------
        self._ensure_csv()

        self.get_logger().info("FusionLogger started")

    # -------------------- Helpers --------------------
    def _parse_state_colors(self, s: str) -> Dict[str, str]:
        out: Dict[str, str] = {}
        try:
            pairs = [p.strip() for p in s.split(",") if p.strip()]
            for p in pairs:
                k, v = [x.strip() for x in p.split(":", 1)]
                if k:
                    out[k] = v
        except Exception as e:
            self.get_logger().warn(f"Failed to parse state_colors: {e}")
        # defaults fallback
        defaults = {
            "Follow": "green",
            "WaitingInit": "yellow",
            "TooClose": "red",
            "Timeout": "red",
            "LiDARGap": "yellow",
        }
        for k, v in defaults.items():
            out.setdefault(k, v)
        return out

    def _ensure_csv(self):
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        newfile = not os.path.exists(self.csv_path)
        if newfile:
            with open(self.csv_path, "w", newline="") as f:
                wr = csv.writer(f)
                wr.writerow([
                    "stamp",
                    "front_min_m",
                    "cx_px",
                    "cx_deg",
                    "range_to_target_m",
                    "state",
                    "state_color",
                ])

    def _csv_write(self, row):
        with open(self.csv_path, "a", newline="") as f:
            csv.writer(f).writerow(row)

    def _now(self) -> float:
        # use ROS clock if available; fallback to wall time
        try:
            t = self.get_clock().now()
            return t.nanoseconds * 1e-9
        except Exception:
            return time.time()

    # -------------------- Callbacks --------------------
    def on_scan(self, msg: LaserScan):
        self.scan_msg = msg
        self.scan_stamp = self._now()

    def on_centroid(self, msg: Int32MultiArray):
        cx = None
        cy = None
        if msg.data and len(msg.data) >= 2:
            cx = int(msg.data[0])
            cy = int(msg.data[1])
        self.cent = CentroidMsg(cx_px=cx, cy_px=cy, stamp=self._now())

    # -------------------- Core logic --------------------
    def _front_min(self, scan: LaserScan) -> Optional[float]:
        # ใช้ค่าที่เป็น valid และไม่น้อยกว่า lidar_min_valid
        rngs = [r for r in scan.ranges if (not math.isinf(r)) and (not math.isnan(r)) and (r >= self.lidar_min_valid)]
        if not rngs:
            return None
        return min(rngs)

    def _cx_to_deg(self, cx_px: Optional[int]) -> Optional[float]:
        if cx_px is None:
            return None
        # 0..img_w  →  -hfov/2 .. +hfov/2
        norm = (cx_px / max(1.0, float(self.img_w))) - 0.5
        return norm * self.hfov_deg

    def _range_at_angle(self, scan: LaserScan, deg: float) -> Optional[float]:
        # สมมติ camera & lidar ตรงแกนกัน และ 0 rad = ด้านหน้า
        ang = math.radians(deg)
        idx = int(round((ang - scan.angle_min) / scan.angle_increment))
        if idx < 0 or idx >= len(scan.ranges):
            return None
        r = scan.ranges[idx]
        if math.isinf(r) or math.isnan(r) or r < self.lidar_min_valid:
            return None
        return r

    def _state_and_lock(self, front_min: Optional[float], r_tgt: Optional[float], cent_ok: bool) -> str:
        now = self._now()

        # Timeout เมื่อ YOLO หายไปเกิน target_timeout
        if not cent_ok:
            self.locked = False
            self.init_ok_count = 0
            return "Timeout"

        # LiDAR gap (ไม่มีข้อมูล lidar ที่เชื่อถือได้)
        if front_min is None:
            # ยังมี YOLO แต่วัดระยะไม่ได้ → แจ้ง LiDARGap
            return "LiDARGap"

        # TooClose
        if front_min < self.stop_dist:
            self.locked = True
            return "TooClose"

        # WaitingInit: ต้องเห็น r_tgt ใกล้ค่า init_dist ต่อเนื่อง confirm_needed เฟรม
        waiting_band = 0.1  # ±0.1 m band เผื่อ noise
        if not self.locked:
            if r_tgt is not None and (self.init_dist - waiting_band) <= r_tgt <= (self.init_dist + waiting_band):
                self.init_ok_count += 1
            else:
                self.init_ok_count = 0

            if self.init_ok_count < self.confirm_needed:
                return "WaitingInit"
            else:
                self.locked = True  # ได้ lock แล้ว

        # Follow เงื่อนไขทั่วไปเมื่อไม่ TooClose/Timeout/LiDARGap/WaitingInit
        # เพิ่ม hysteresis resume ให้ปลอดภัยขึ้น
        if self.locked and r_tgt is not None:
            if r_tgt < (self.stop_dist + self.resume_margin):
                return "TooClose"

        return "Follow"

    def on_timer(self):
        now = self._now()

        scan = self.scan_msg
        cent = self.cent

        # ตรวจ timeout ของ YOLO centroid
        cent_ok = False
        cx_px = None
        cx_deg = None
        if cent is not None:
            cx_px = cent.cx_px
            cx_deg = self._cx_to_deg(cx_px)
            if (now - cent.stamp) <= self.target_timeout and cx_px is not None:
                cent_ok = True

        front_min = None
        r_tgt = None
        if scan is not None:
            front_min = self._front_min(scan)
            if cx_deg is not None:
                r_tgt = self._range_at_angle(scan, cx_deg)

        state = self._state_and_lock(front_min, r_tgt, cent_ok)
        color = self.state_color_map.get(state, "off")

        # CSV
        self._csv_write([
            f"{now:.3f}",
            fmt(front_min),
            "" if cx_px is None else str(cx_px),
            fmt(cx_deg, 2),
            fmt(r_tgt),
            state,
            color,
        ])

        # Console print (อ่านง่าย ใช้ fmt ป้องกัน format error)
        self.get_logger().info(
            f"[STATE={state} COLOR={color}] "
            f"front_min={fmt(front_min)} cx={'' if cx_px is None else cx_px} "
            f"cx_deg={fmt(cx_deg,2)} range_tgt={fmt(r_tgt)} "
            f"locked={self.locked} init_ok={self.init_ok_count}"
        )


def main():
    rclpy.init()
    node = FusionLogger()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

