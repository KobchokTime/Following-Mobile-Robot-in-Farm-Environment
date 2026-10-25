#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SyncFusionNode (updated stable version)
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy, QoSDurabilityPolicy
from std_msgs.msg import Int32MultiArray, Float32MultiArray
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist
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


def lidar_clusters(points, gap_m=0.15):
    """Group a scan, sorted by bearing, into clusters of neighbouring returns.

    Two neighbours belong together when their ranges differ by less than gap_m. Returns a list of
    (bearing of the middle return, closest range, length in metres from the first to the last return).
    """
    pts = sorted(points)
    clusters, cur = [], []
    for b, r in pts:
        if cur and (abs(r - cur[-1][1]) > gap_m or b - cur[-1][0] > math.radians(3.0)):
            clusters.append(cur)
            cur = []
        cur.append((b, r))
    if cur:
        clusters.append(cur)
    out = []
    for c in clusters:
        rmin = min(r for _, r in c)
        # straight-line distance between the first and last return, so depth counts too: a crop row
        # seen at an angle is long even when it spans a narrow angle
        (b0, r0), (b1, r1) = c[0], c[-1]
        width = math.hypot(r1 * math.cos(b1) - r0 * math.cos(b0), r1 * math.sin(b1) - r0 * math.sin(b0))
        out.append((c[len(c) // 2][0], rmin, width))
    return out


class StaticMap:
    """Remembers LiDAR clusters in an odometry frame and flags the ones that do not move.

    After the idea of a dynamic-object detector that compares scans over a time window and keeps only
    what moved: a cluster that has stayed within radius_m of where it was first seen for static_s is
    static (a post, a bush, a crop row end). A walking person leaves that radius within a second and
    starts a new entry, so is never static unless it stands still for static_s. The robot's pose is
    integrated from its velocity commands, so the map only needs to hold for a few seconds.
    """

    def __init__(self, static_s=2.0, radius_m=0.3, forget_s=1.0):
        self.static_s, self.radius, self.forget_s = static_s, radius_m, forget_s
        self.pose = (0.0, 0.0, 0.0)
        self.entries = []  # [x, y, first_seen, last_seen]

    def move(self, v, w, dt):
        x, y, yaw = self.pose
        dt = max(0.0, min(dt, 0.5))
        self.pose = (x + v * math.cos(yaw) * dt, y + v * math.sin(yaw) * dt, yaw + w * dt)

    def to_world(self, bearing, rng):
        x, y, yaw = self.pose
        return x + rng * math.cos(yaw + bearing), y + rng * math.sin(yaw + bearing)

    def update(self, now, clusters):
        """clusters: (robot-frame bearing, range) of each cluster in the latest scan."""
        self.entries = [e for e in self.entries if now - e[3] <= self.forget_s]
        for b, r in clusters:
            wx, wy = self.to_world(b, r)
            near = min(self.entries, key=lambda e: (e[0] - wx) ** 2 + (e[1] - wy) ** 2, default=None)
            if near is not None and math.hypot(near[0] - wx, near[1] - wy) <= self.radius:
                near[3] = now
            else:
                self.entries.append([wx, wy, now, now])

    def is_static(self, bearing, rng):
        wx, wy = self.to_world(bearing, rng)
        return any(e[3] - e[2] >= self.static_s and math.hypot(e[0] - wx, e[1] - wy) <= self.radius
                   for e in self.entries)


def lidar_track(points, pred_bearing, pred_range, window_rad, range_tol, width_m=(0.15, 0.8), exclude=None):
    """Where the target is in a LiDAR scan, near its predicted bearing and range.

    points: (robot-frame bearing, range) pairs. Only person-sized clusters count (width_m), so a thin
    post or a long crop row is not taken for the target. Returns (bearing, range) of the cluster
    nearest the prediction, or None. Used while the target is outside the camera's view.
    exclude(bearing, range) -> True drops a cluster (StaticMap.is_static: things that never move).
    """
    best, best_cost = None, None
    for b, r, w in lidar_clusters(points):
        db = abs((b - pred_bearing + math.pi) % (2.0 * math.pi) - math.pi)
        if db > window_rad or abs(r - pred_range) > range_tol or not (width_m[0] <= w <= width_m[1]):
            continue
        if exclude is not None and exclude(b, r):
            continue
        cost = (db / window_rad) ** 2 + ((r - pred_range) / range_tol) ** 2
        if best is None or cost < best_cost:
            best, best_cost = (b, r), cost
    return best


def scan_is_fresh(now, scan_time, max_age):
    """True if the latest scan arrived at most max_age seconds ago (a stopped LiDAR must not steer)."""
    return scan_time is not None and 0.0 <= now - scan_time <= max_age


def bearing_to_cx(bearing, image_width, hfov_deg):
    """Image column for a bearing (inverse of camera_bearing_rad), clamped to the image."""
    f = (image_width / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)
    half = math.radians(hfov_deg) / 2.0
    b = max(-half, min(half, bearing))
    return int(round(min(image_width - 1, max(0, image_width / 2.0 - f * math.tan(b)))))


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
                 alpha=0.6, beta=0.2, chroma_rate=0.05, min_rate_dt=0.015, unlock_after_s=5.0):
        self.lock_range = lock_range
        self.lock_bearing = math.radians(lock_bearing_deg)
        self.sb = math.radians(bearing_sigma_deg)
        self.sr = range_sigma_m
        self.sc = chroma_sigma
        self.gate = gate
        self.widen_per_s = widen_per_s
        self.alpha, self.beta = alpha, beta
        self.chroma_rate = chroma_rate
        # Two boxes on one person arrive within a frame; a rate from a ~1 ms step would blow up the
        # prediction and the target would never be accepted again, so such steps update position only.
        # 15 ms is under one frame even at 60 fps, so real frame-to-frame steps always update the rate.
        self.min_rate_dt = min_rate_dt
        # After this long with no fix the widened gates would take almost anything (a false box in
        # front of a post); start over from the lock-on window instead, like the controller does.
        self.unlock_after_s = unlock_after_s
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

    def accept_lidar(self, t, bearing, rng):
        """Update the track from a LiDAR-only fix (the caller already matched it to the prediction)."""
        dt = max(1e-3, t - self.t)
        pb, pr = self._predict(t)
        eb, er = bearing - pb, rng - pr
        self.bearing, self.range = pb + self.alpha * eb, pr + self.alpha * er
        if self.min_rate_dt <= dt < 1.0:
            self.bearing_rate += self.beta * eb / dt
            self.range_rate += self.beta * er / dt
        self.t = t

    def accept(self, t, bearing, rng, chroma=None):
        """True if this detection is the target; updates the track when it is."""
        if self.locked and t - self.t > self.unlock_after_s:
            self.reset()
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
        if dt >= 1.0:
            self.bearing_rate = self.range_rate = 0.0
        elif dt >= self.min_rate_dt:
            self.bearing_rate += self.beta * eb / dt
            self.range_rate += self.beta * er / dt
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
        # only someone at least this much nearer than the target is in the way; a spurious box over the
        # target itself reads the target's own LiDAR range and must not make the robot back off
        self.declare_parameter('path_min_gap_m', 0.2)
        # LiDAR keeps the target when it leaves the camera's view (a side step, a sharp turn)
        self.declare_parameter('lidar_track', True)
        self.declare_parameter('scan_topic', '/scan')
        self.declare_parameter('lidar_angle_offset_deg', 180.0)  # as lidar_sectorizer_node.py angle_offset
        self.declare_parameter('lidar_track_after_s', 0.3)  # camera silent this long -> use the LiDAR
        self.declare_parameter('lidar_track_max_s', 5.0)    # give up after this long without the camera
        self.declare_parameter('lidar_edge_deg', 8.0)  # only when last seen this close to the image edge
        self.declare_parameter('lidar_scan_max_age_s', 0.3)  # older scans are never used to track
        # off by default: never take a cluster that has not moved for static_s as the target
        self.declare_parameter('static_filter', False)
        self.declare_parameter('static_s', 2.0)
        self.declare_parameter('static_radius_m', 0.3)

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
        self.path_min_gap = float(self.get_parameter('path_min_gap_m').value)
        self.path_block = None  # (time, range) of the latest other person in the corridor
        self.last_target = None  # (cx, cy, sector_id, range) last published for the target
        self.use_lidar_track = bool(self.get_parameter('lidar_track').value)
        self.lidar_offset = math.radians(float(self.get_parameter('lidar_angle_offset_deg').value))
        self.lidar_after = float(self.get_parameter('lidar_track_after_s').value)
        self.lidar_max = float(self.get_parameter('lidar_track_max_s').value)
        self.scan_points = []     # latest scan as (robot-frame bearing, range)
        self.scan_time = None     # when it arrived
        self.scan_max_age = float(self.get_parameter('lidar_scan_max_age_s').value)
        self.static_map = StaticMap(float(self.get_parameter('static_s').value),
                                    float(self.get_parameter('static_radius_m').value)) \
            if bool(self.get_parameter('static_filter').value) else None
        self.cmd = (0.0, 0.0)
        self.cmd_time = None
        self.last_scan_stamp = None
        self.last_camera_fix = None  # time of the last camera detection accepted as the target
        self.last_camera_bearing = 0.0
        self.edge_rad = math.radians(self.camera_hfov_deg / 2.0 - float(self.get_parameter('lidar_edge_deg').value))

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
        self.sub_scan = self.create_subscription(
            LaserScan, str(self.get_parameter('scan_topic').value), self.cb_scan, qos_lidar)
        if self.static_map is not None:
            self.sub_cmd = self.create_subscription(Twist, '/cmd_vel', self.cb_cmd, 10)

        # ---------- pub ----------
        self.pub_synced = self.create_publisher(
            Float32MultiArray, '/synced_target', 10)

        # ---------- timers ----------
        self.gc_timer = self.create_timer(0.5, self.gc_buffers)
        self.track_timer = self.create_timer(0.1, self.track_with_lidar)
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

    def cb_cmd(self, msg):
        self.cmd = (msg.linear.x, msg.angular.z)
        self.cmd_time = self.now_sec()

    def cb_scan(self, msg):
        pts = []
        for i, r in enumerate(msg.ranges):
            if math.isfinite(r) and msg.range_min < r < msg.range_max:
                a = (msg.angle_min + i * msg.angle_increment + self.lidar_offset + math.pi) % (2.0 * math.pi) - math.pi
                pts.append((a, r))
        self.scan_points = pts
        self.scan_time = self.now_sec()
        if self.static_map is not None:
            if self.last_scan_stamp is not None:
                # the drive bridge stops the wheels 1 s after its last command, so an old command means standing still
                fresh = self.cmd_time is not None and self.scan_time - self.cmd_time <= 1.0
                v, w = self.cmd if fresh else (0.0, 0.0)
                self.static_map.move(v, w, self.scan_time - self.last_scan_stamp)
            self.last_scan_stamp = self.scan_time
            self.static_map.update(self.scan_time, [(b, r) for b, r, _ in lidar_clusters(pts)])

    def track_with_lidar(self):
        """The target stepped out of the camera's view: keep it with the LiDAR and turn towards it.

        Only when it was last seen near the image edge. If it vanished from the middle of the image
        the camera or detector failed instead, and the controller's normal stop applies.
        """
        if not (self.use_gate and self.use_lidar_track and self.gate.locked and self.last_target is not None):
            return
        now = self.now_sec()
        if self.last_camera_fix is None or now - self.last_camera_fix < self.lidar_after \
                or now - self.last_camera_fix > self.lidar_max:
            return
        pb, pr = self.gate._predict(now)
        # last seen near the edge, or moving fast enough to be past it by now (frames arrive late)
        if abs(self.last_camera_bearing) < self.edge_rad and abs(pb) < self.edge_rad:
            return
        if not scan_is_fresh(now, self.scan_time, self.scan_max_age):
            return  # no recent scan: do not steer by an old one; the controller's normal stop applies
        found = lidar_track(self.scan_points, pb, pr, math.radians(25.0), 0.5,
                            exclude=self.static_map.is_static if self.static_map is not None else None)
        if found is None:
            return
        bearing, rng = found
        self.gate.accept_lidar(now, bearing, rng)
        # the image edge on the target's side: the controller turns that way at its full turn rate
        cx = 0 if bearing > 0 else self.image_width - 1
        sector = 0 if bearing > 0 else 8
        _, cy, _, _ = self.last_target
        self.publish_synced(cx, cy, rng, sector, 0.0)

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
            # Only someone in the corridor and clearly nearer than the target is in the way
            if self.last_target is not None and in_path(bearing, dist, self.path_half_width) \
                    and dist < self.last_target[3] - self.path_min_gap:
                self.path_block = (ty, dist)
                # They may hide the target, so give way now instead of waiting to see the target again
                cx_t, cy_t, sector_t, _ = self.last_target
                self.publish_synced(cx_t, cy_t, max(0.0, dist - self.path_margin), sector_t, best_dt)
            return
        self.last_target = (cx, cy, sector_id, dist)  # the target's own range, before any give-way
        self.last_camera_fix = ty
        self.last_camera_bearing = bearing
        if self.path_block is not None and ty - self.path_block[0] <= self.path_hold:
            dist = min(dist, max(0.0, self.path_block[1] - self.path_margin))  # give way to whoever is in it
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
