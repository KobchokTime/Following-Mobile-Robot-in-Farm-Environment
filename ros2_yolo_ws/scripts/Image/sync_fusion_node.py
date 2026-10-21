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
        if len(msg.data) < 3:
            return
        cx, cy, sector_id = msg.data[:3]
        self.buf_yolo.append((t, {'cx': cx, 'cy': cy, 'sector_id': sector_id}))
        self.try_sync_from_yolo(t, cx, cy, sector_id)

    def cb_lidar(self, msg):
        t = self.now_sec()
        if not msg.data:
            return
        self.buf_lidar.append((t, list(msg.data)))

    def cb_angles(self, msg):
        self.lidar_angles = list(msg.data)

    def try_sync_from_yolo(self, ty, cx, cy, sector_id):
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
