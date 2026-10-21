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


def in_path(bearing, rng, half_width_m):
    """True if a return at (bearing, range) lies ahead within the robot's driving corridor."""
    return rng * math.cos(bearing) > 0.0 and abs(rng * math.sin(bearing)) <= half_width_m


class TargetGate:
    """Keeps one person as the target when several are detected (Arena 3).

    The camera node publishes one message per person, with no identity. Each detection gets a cost
    against the target track: bearing and range against an alpha-beta prediction, plus the clothing
    chroma when the message carries it. Only a detection within the gate is the target. Colour is
    a soft cost, so shade or matching clothes leave the decision to geometry. The gates widen while
    the target is not seen, so it can be found again after a short loss.

    Lock-on uses the controller's start window: range 0.5-1.0 m, near the image centre.
    """

    def __init__(self, lock_range=(0.5, 1.0), lock_bearing_deg=15.0, bearing_sigma_deg=5.0,
                 range_sigma_m=0.15, chroma_sigma=15.0, gate=9.0, widen_per_s=1.0,
                 alpha=0.6, beta=0.2, chroma_rate=0.05):
        self.lock_range = lock_range
        self.lock_bearing = math.radians(lock_bearing_deg)
        self.sb = math.radians(bearing_sigma_deg)
        self.sr = range_sigma_m
        self.sc = chroma_sigma
        self.gate = gate
        self.widen_per_s = widen_per_s
        self.alpha, self.beta = alpha, beta
        self.chroma_rate = chroma_rate
        self.reset()

    def reset(self):
        self.locked = False
        self.t = None
        self.bearing = self.bearing_rate = 0.0
        self.range = self.range_rate = 0.0
        self.chroma = None

    def _predict(self, t):
        dt = max(0.0, min(t - self.t, 1.0))
        return self.bearing + self.bearing_rate * dt, self.range + self.range_rate * dt

    def cost(self, t, bearing, rng, chroma=None):
        """Normalised squared distance of a detection from the target (inf before lock-on)."""
        if not self.locked:
            return math.inf
        pb, pr = self._predict(t)
        widen = 1.0 + self.widen_per_s * max(0.0, t - self.t - 0.2)
        c = ((bearing - pb) / (self.sb * widen)) ** 2 + ((rng - pr) / (self.sr * widen)) ** 2
        if chroma is not None and self.chroma is not None:
            c += ((chroma[0] - self.chroma[0]) ** 2 + (chroma[1] - self.chroma[1]) ** 2) / self.sc ** 2
        return c

    def accept(self, t, bearing, rng, chroma=None):
        """True if this detection is the target; updates the track when it is."""
        if not self.locked:
            if self.lock_range[0] <= rng <= self.lock_range[1] and abs(bearing) <= self.lock_bearing:
                self.locked, self.t = True, t
                self.bearing, self.range = bearing, rng
                self.chroma = tuple(chroma) if chroma is not None else None
                return True
            return False
        if self.cost(t, bearing, rng, chroma) > self.gate:
            return False
        dt = max(1e-3, t - self.t)
        pb, pr = self._predict(t)
        eb, er = bearing - pb, rng - pr
        self.bearing, self.range = pb + self.alpha * eb, pr + self.alpha * er
        if dt < 1.0:
            self.bearing_rate += self.beta * eb / dt
            self.range_rate += self.beta * er / dt
        else:
            self.bearing_rate = self.range_rate = 0.0
        self.t = t
        if chroma is not None:
            if self.chroma is None:
                self.chroma = tuple(chroma)
            else:
                k = self.chroma_rate
                self.chroma = (self.chroma[0] + k * (chroma[0] - self.chroma[0]),
                               self.chroma[1] + k * (chroma[1] - self.chroma[1]))
        return True


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
        # Target gate (Arena 3): publish only the person being followed
        self.declare_parameter('target_gate', True)
        self.declare_parameter('use_chroma', True)
        # Someone else in the corridor and nearer than the target sets the distance the controller sees
        self.declare_parameter('path_half_width_m', 0.7)
        self.declare_parameter('path_hold_s', 0.5)
        self.declare_parameter('path_margin_m', 0.4)  # treat them as this much nearer, so the robot gives way early

        self.max_dt = float(self.get_parameter('max_dt').value)
        self.buffer_sec = float(self.get_parameter('buffer_sec').value)
        self.yolo_topic = str(self.get_parameter('yolo_topic').value)
        self.lidar_topic = str(self.get_parameter('lidar_topic').value)
        self.camera_hfov_deg = float(self.get_parameter('camera_hfov_deg').value)
        self.image_width = int(self.get_parameter('image_width').value)
        self.lidar_angles = []  # centre angle of each LiDAR sector, robot frame, left positive
        self.use_gate = bool(self.get_parameter('target_gate').value)
        self.use_chroma = bool(self.get_parameter('use_chroma').value)
        self.gate = TargetGate()
        self.path_half_width = float(self.get_parameter('path_half_width_m').value)
        self.path_hold = float(self.get_parameter('path_hold_s').value)
        self.path_margin = float(self.get_parameter('path_margin_m').value)
        self.path_block = None  # (time, range) of the latest other person in the corridor
        self.last_target = None  # (cx, cy, sector_id) last published for the target

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
        # [cx, cy, sector, cb, cr] carries the clothing chroma; old 3-value messages have none
        chroma = (msg.data[3], msg.data[4]) if len(msg.data) >= 5 and self.use_chroma else None
        self.buf_yolo.append((t, {'cx': cx, 'cy': cy, 'sector_id': sector_id}))
        self.try_sync_from_yolo(t, cx, cy, sector_id, chroma)

    def cb_lidar(self, msg):
        t = self.now_sec()
        if not msg.data:
            return
        self.buf_lidar.append((t, list(msg.data)))

    def cb_angles(self, msg):
        self.lidar_angles = list(msg.data)

    def publish_synced(self, cx, cy, dist, sector_id, best_dt):
        stamp = self.get_clock().now().nanoseconds * 1e-9
        out = Float32MultiArray()
        out.data = [float(cx), float(cy), float(dist), float(sector_id), float(best_dt * 1000.0), float(stamp)]
        self.pub_synced.publish(out)

    def try_sync_from_yolo(self, ty, cx, cy, sector_id, chroma=None):
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

        if self.use_gate and not self.gate.accept(ty, bearing, dist, chroma):
            # another person, not the one being followed: remember them only if they are in the way
            if in_path(bearing, dist, self.path_half_width):
                self.path_block = (ty, dist)
                if self.last_target is not None:
                    # They may hide the target, so give way now instead of waiting to see the target again
                    cx_t, cy_t, sector_t = self.last_target
                    self.publish_synced(cx_t, cy_t, max(0.0, dist - self.path_margin), sector_t, best_dt)
            return
        if self.path_block is not None and ty - self.path_block[0] <= self.path_hold:
            dist = min(dist, max(0.0, self.path_block[1] - self.path_margin))  # give way to whoever is in it

        self.last_target = (cx, cy, sector_id)
        self.publish_synced(cx, cy, dist, sector_id, best_dt)

        self.sync_count += 1
        if self.sync_count % 10 == 0:
            self.get_logger().info(
                f"[SYNC] cx={cx:.1f}, cy={cy:.1f}, dist={dist:.2f}m, sector={sector_id}, dt={best_dt * 1000.0:.1f}ms"
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
