#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SyncFusionNode (updated stable version)
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy, QoSDurabilityPolicy
from std_msgs.msg import Int32MultiArray, Float32MultiArray
from collections import deque
import math


def camera_bearing_rad(cx, image_width, hfov_deg):
    """Bearing of image column cx in the robot frame (left positive), pinhole model."""
    f = (image_width / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)
    return math.atan2(image_width / 2.0 - cx, f)


def nearest_sector(bearing, sector_angles):
    """Index of the LiDAR sector whose centre angle is closest to bearing (radians)."""
    if not sector_angles:
        return None
    return min(range(len(sector_angles)), key=lambda i: abs(sector_angles[i] - bearing))


def parse_yolo_detection(data):
    """Return the legacy detection fields and optional clothing chroma."""
    if len(data) < 3:
        return None
    cx, cy, sector_id = data[:3]
    cb, cr = (data[3], data[4]) if len(data) >= 5 else (None, None)
    return cx, cy, sector_id, cb, cr


class TargetSelector:
    """Lock onto the initial near, forward person and associate later detections to it."""

    def __init__(self, image_width=640, camera_hfov_deg=70.0,
                 init_dist_min=0.5, init_dist_max=1.0):
        self.image_width = image_width
        self.camera_hfov_deg = camera_hfov_deg
        self.init_dist_min = init_dist_min
        self.init_dist_max = init_dist_max
        self.last_bearing = None
        self.last_dist = None
        self.last_time = None
        self.last_chroma = None

    @staticmethod
    def _angle_delta(a, b):
        return math.atan2(math.sin(a - b), math.cos(a - b))

    def consider(self, cx, dist, stamp, cb=None, cr=None):
        """Accept and remember a target candidate; reject detections of other people."""
        if not math.isfinite(float(dist)):
            return False
        bearing = camera_bearing_rad(cx, self.image_width, self.camera_hfov_deg)
        chroma = (float(cb), float(cr)) if cb is not None and cr is not None else None

        if self.last_time is None:
            if not self.init_dist_min <= dist <= self.init_dist_max:
                return False
            self._remember(bearing, dist, stamp, chroma)
            return True

        dt = max(0.0, stamp - self.last_time)
        # Allow plausible motion between camera callbacks, but don't let a long loss
        # gradually turn every bystander into a valid association.
        bearing_gate = min(0.50, 0.15 + 0.8 * dt)
        range_gate = min(0.75, 0.4 + 0.4 * dt)
        if abs(self._angle_delta(bearing, self.last_bearing)) > bearing_gate:
            return False
        if abs(dist - self.last_dist) > range_gate:
            return False
        if self.last_chroma is not None and chroma is not None:
            color_delta = math.hypot(chroma[0] - self.last_chroma[0],
                                     chroma[1] - self.last_chroma[1])
            if color_delta > 45.0:
                return False

        self._remember(bearing, dist, stamp, chroma)
        return True

    def _remember(self, bearing, dist, stamp, chroma):
        self.last_bearing = bearing
        self.last_dist = float(dist)
        self.last_time = float(stamp)
        if chroma is not None:
            if self.last_chroma is None:
                self.last_chroma = chroma
            else:
                self.last_chroma = tuple(0.8 * old + 0.2 * new
                                         for old, new in zip(self.last_chroma, chroma))


class SyncFusionNode(Node):
    def __init__(self):
        super().__init__('sync_fusion_node')

        # ---------- params ----------
        self.declare_parameter('max_dt', 0.10)
        self.declare_parameter('buffer_sec', 2.0)
        self.declare_parameter('yolo_topic', '/target_centroid_sector')
        self.declare_parameter('lidar_topic', '/lidar_sector_dists')
        self.declare_parameter('lidar_angles_topic', '/lidar_sector_angles')
        # Camera geometry, used to turn a centroid column into a bearing (Image/Camera.py: 70 deg, 640 px)
        self.declare_parameter('camera_hfov_deg', 70.0)
        self.declare_parameter('image_width', 640)

        self.max_dt = float(self.get_parameter('max_dt').value)
        self.buffer_sec = float(self.get_parameter('buffer_sec').value)
        self.yolo_topic = str(self.get_parameter('yolo_topic').value)
        self.lidar_topic = str(self.get_parameter('lidar_topic').value)
        self.camera_hfov_deg = float(self.get_parameter('camera_hfov_deg').value)
        self.image_width = int(self.get_parameter('image_width').value)
        self.lidar_angles = []  # centre angle of each LiDAR sector, robot frame, left positive
        self.target_selector = TargetSelector(self.image_width, self.camera_hfov_deg)

        # ---------- buffers ----------
        self.buf_yolo = deque()
        self.buf_lidar = deque()

        # ---------- QoS ----------
        qos_lidar = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
            durability=QoSDurabilityPolicy.VOLATILE,
        )
        qos_yolo = 10

        # ---------- subs ----------
        self.sub_yolo = self.create_subscription(
            Int32MultiArray, self.yolo_topic, self.cb_yolo, qos_yolo)
        self.sub_lidar = self.create_subscription(
            Float32MultiArray, self.lidar_topic, self.cb_lidar, qos_lidar)
        self.sub_angles = self.create_subscription(
            Float32MultiArray, str(self.get_parameter('lidar_angles_topic').value), self.cb_angles, qos_lidar)

        # ---------- pub ----------
        self.pub_synced = self.create_publisher(
            Float32MultiArray, '/synced_target', 10)

        # ---------- timers ----------
        self.gc_timer = self.create_timer(0.5, self.gc_buffers)
        self.sync_count = 0

        self.get_logger().info(
            f"SyncFusion started ✅ | yolo={self.yolo_topic} lidar={self.lidar_topic} "
            f"max_dt={self.max_dt:.3f}s buffer={self.buffer_sec:.1f}s"
        )

    def now_sec(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def gc_buffers(self):
        tnow = self.now_sec()
        while self.buf_yolo and (tnow - self.buf_yolo[0][0] > self.buffer_sec):
            self.buf_yolo.popleft()
        while self.buf_lidar and (tnow - self.buf_lidar[0][0] > self.buffer_sec):
            self.buf_lidar.popleft()

    def cb_yolo(self, msg):
        t = self.now_sec()
        detection = parse_yolo_detection(msg.data)
        if detection is None:
            return
        cx, cy, sector_id, cb, cr = detection
        self.buf_yolo.append((t, {'cx': cx, 'cy': cy, 'sector_id': sector_id,
                                  'cb': cb, 'cr': cr}))
        self.try_sync_from_yolo(t, cx, cy, sector_id, cb, cr)

    def cb_lidar(self, msg):
        t = self.now_sec()
        if not msg.data:
            return
        self.buf_lidar.append((t, list(msg.data)))

    def cb_angles(self, msg):
        self.lidar_angles = list(msg.data)

    def try_sync_from_yolo(self, ty, cx, cy, sector_id, cb=None, cr=None):
        if not self.buf_lidar or not self.lidar_angles:
            return

        best = None
        best_dt = 1e9
        for tl, data in self.buf_lidar:
            dt = abs(tl - ty)
            if dt < best_dt:
                best_dt = dt
                best = (tl, data)

        if best is None or best_dt > self.max_dt:
            return

        tl, lidar_data = best
        # Match by direction, not by index: camera sectors split the image left to right,
        # LiDAR sectors split an angle range in the other order and over a different width.
        bearing = camera_bearing_rad(cx, self.image_width, self.camera_hfov_deg)
        lidar_sector = nearest_sector(bearing, self.lidar_angles[:len(lidar_data)])
        dist = float('inf')
        if lidar_sector is not None:
            dist = lidar_data[lidar_sector]

        # ✅ skip inf distance
        if not math.isfinite(dist):
            self.get_logger().debug(f"Skip frame: invalid LiDAR dist in sector {sector_id}")
            return

        if not self.target_selector.consider(cx, dist, ty, cb, cr):
            self.get_logger().debug(
                f"Skip non-target detection: cx={cx}, dist={dist:.2f}m, chroma=({cb}, {cr})")
            return

        dt_ms = best_dt * 1000.0
        stamp = self.get_clock().now().nanoseconds * 1e-9

        out = Float32MultiArray()
        out.data = [float(cx), float(cy), float(dist), float(sector_id), float(dt_ms), float(stamp)]
        self.pub_synced.publish(out)

        self.sync_count += 1
        if self.sync_count % 10 == 0:
            self.get_logger().info(
                f"[SYNC] cx={cx:.1f}, cy={cy:.1f}, dist={dist:.2f}m, sector={sector_id}, dt={dt_ms:.1f}ms"
            )


def main():
    rclpy.init()
    node = SyncFusionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
