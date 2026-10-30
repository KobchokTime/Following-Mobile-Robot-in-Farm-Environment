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


def lidar_track(points, pred_bearing, pred_range, window_rad, range_tol, width_m=(0.15, 0.8)):
    """Where the target is in a LiDAR scan, near its predicted bearing and range.

    points: (robot-frame bearing, range) pairs. Only person-sized clusters count (width_m), so a thin
    post or a long crop row is not taken for the target. Returns (bearing, range) of the cluster
    nearest the prediction, or None. Used while the target is outside the camera's view.
    """
    best, best_cost = None, None
    for b, r, w in lidar_clusters(points):
        db = abs((b - pred_bearing + math.pi) % (2.0 * math.pi) - math.pi)
        if db > window_rad or abs(r - pred_range) > range_tol or not (width_m[0] <= w <= width_m[1]):
            continue
        cost = (db / window_rad) ** 2 + ((r - pred_range) / range_tol) ** 2
        if best is None or cost < best_cost:
            best, best_cost = (b, r), cost
    return best


def box_range(points, bearing, margin_rad=math.radians(5.0)):
    """Range of the LiDAR cluster that belongs to a camera box at this bearing, or None.

    The cluster whose angular span covers the bearing; if none does (a box between two legs), the
    one whose edge is nearest, within margin_rad. A near person fills a wide angle, so the minimum of
    a fixed sector next to them is their range even for a box on someone far behind (T13 follow-up).
    A cluster beside the box is never preferred to the one the box looks at: a person crossing in
    front would otherwise lend their range to the target's box before they cover it. Only returns
    within margin_rad of the box (beyond the edge gap) count, so a long cluster (a person against a
    crop row) gives the range at the box, not the row's nearest point.
    """
    pts = sorted(points)
    best, best_gap = None, None
    start = 0
    for i in range(1, len(pts) + 1):
        if i < len(pts) and abs(pts[i][1] - pts[i - 1][1]) <= 0.15 and pts[i][0] - pts[i - 1][0] <= math.radians(3.0):
            continue
        c = pts[start:i]
        start = i
        gap = max(c[0][0] - bearing, bearing - c[-1][0], 0.0)
        if gap <= margin_rad and (best is None or gap < best_gap):
            # only the returns near the box: a person against a crop row chains into one long cluster
            best, best_gap = min(r for b, r in c if abs(b - bearing) <= gap + margin_rad), gap
    return best


def scan_crowded(points, box_bearing, box_rng, pred_bearing, pred_range, radius_m, spread_m=0.55, max_width_m=1.5):
    """True if the scan shows more than one person near the predicted target (T15 follow-up).

    Only for a box within radius_m of the predicted target, where the wider gate could take a stranger.
    The camera can miss the target's box, or send a stranger's box first in a frame; the scan has both
    people. The returns within radius_m of the prediction are one person if they span less than spread_m
    (a person seen from one side spans at most about 0.45 m); two people side by side span more. The box
    position itself is not compared with the returns: the camera is about 0.15 s behind the scan, so a
    target stepping sideways would look like a second person. Two people side by side chain into one
    cluster, so returns count one by one; returns in a cluster wider than max_width_m (a crop row, a
    wall) do not count.
    """
    bx, by = box_rng * math.cos(box_bearing), box_rng * math.sin(box_bearing)
    px, py = pred_range * math.cos(pred_bearing), pred_range * math.sin(pred_bearing)
    if math.hypot(bx - px, by - py) > radius_m:
        return False  # a box away from the target (a false box, a post)
    near = []
    pts = sorted(points)
    start = 0
    for i in range(1, len(pts) + 1):
        if i < len(pts) and abs(pts[i][1] - pts[i - 1][1]) <= 0.15 and pts[i][0] - pts[i - 1][0] <= math.radians(3.0):
            continue
        c = pts[start:i]
        start = i
        (b0, r0), (b1, r1) = c[0], c[-1]
        if math.hypot(r1 * math.cos(b1) - r0 * math.cos(b0), r1 * math.sin(b1) - r0 * math.sin(b0)) > max_width_m:
            continue
        for b, r in c:
            x, y = r * math.cos(b), r * math.sin(b)
            if math.hypot(x - px, y - py) <= radius_m:
                near.append((x, y))
    return any(math.hypot(x0 - x1, y0 - y1) >= spread_m for i, (x0, y0) in enumerate(near) for x1, y1 in near[i + 1:])


def scan_is_fresh(now, scan_time, max_age):
    """True if the latest scan arrived at most max_age seconds ago (a stopped LiDAR must not steer)."""
    return scan_time is not None and 0.0 <= now - scan_time <= max_age


def bearing_to_cx(bearing, image_width, hfov_deg):
    """Image column for a bearing (inverse of camera_bearing_rad), clamped to the image."""
    f = (image_width / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)
    half = math.radians(hfov_deg) / 2.0
    b = max(-half, min(half, bearing))
    return int(round(min(image_width - 1, max(0, image_width / 2.0 - f * math.tan(b)))))


def bhattacharyya(a, b):
    """Overlap of two normalised histograms: 1 identical, 0 disjoint."""
    return sum(math.sqrt(max(0.0, x) * max(0.0, y)) for x, y in zip(a, b))


def parse_hist(values, bins=48):
    """The torso histogram after cb, cr in a camera message, normalised; None if absent or empty."""
    if len(values) < bins:
        return None
    h = [max(0.0, float(v)) for v in values[:bins]]
    total = sum(h)
    return [v / total for v in h] if total > 0 else None


class TargetGate:
    """Keeps one person as the target when several are detected (Arena 3).

    The camera node publishes one message per person, with no identity. Each detection gets a cost
    against the target track: bearing and range against an alpha-beta prediction, plus the clothing
    clothing colour when the message carries it. Only a detection within the gate is the target. Colour
    is a soft cost, so shade or matching clothes leave the decision to geometry. The gates widen while
    the target is not seen, so it can be found again after a short loss.

    Colour is the Cb/Cr chroma and, when the camera sends one, the torso hue-saturation histogram,
    weighted hist_weight (0.25) against 1 - hist_weight. The histogram follows Kim, Suh and Kwon
    (2024): no brightness channel, and it is re-learned from the target's last hist_window boxes. A
    box is learned only if it is at least as close to the model as the boxes already learned, less
    hist_learn_slack, so one wrong pick does not teach the model the other person's colours.

    Hue keeps a blue top blue in shade, where Cb/Cr turns grey; Cb/Cr keeps black, grey and beige tops
    steady, where hue is noise. On video (experiments/identity/clothing_colour_videos) neither alone
    did well on both. A quarter histogram kept every held-out person as well as Cb/Cr alone did and
    still picked the blue top out in the lab clips; more histogram helped in a crowd but lost a black
    tee (weight_sweep.py).

    Re-acquisition, after Algorithm 1 of Kim, Suh and Kwon (2024): once the target has been unseen for
    reacquire_after_s, a detection is taken as the target again, and the track restarts there, when
    its colour matches the model (colour cost at most reacquire_colour_max), it lies within
    reacquire_bearing_deg of the predicted bearing, and it is where the target could have walked to:
    within reacquire_dist_m + reacquire_speed_mps x (time unseen) of the last place the target was
    seen, at most reacquire_dist_max_m (the paper's T_dist). Clothing alone cannot tell two people in
    the same clothes apart; the distance rule keeps a look-alike elsewhere in the scene out (T13). Only
    with a histogram: Cb/Cr alone cannot tell a blue top in shade from a grey one. The colour
    threshold was chosen on the same seven videos as hist_weight; it is not an identity guarantee.

    Close in, a small sideways step is a large angle (0.25 m is 20 deg at 0.7 m), so the bearing sigma is
    never tighter than lateral_sigma_m sideways: max(bearing_sigma_deg, lateral_sigma_m / range). From
    about 1.7 m out (0.15 m / 5 deg) this is the plain 5 deg; lateral_sigma_m 0 restores it everywhere.
    The wider gate applies only when the target is alone: if within ambiguity_window_s two boxes in one
    frame (ambiguity_frame_s) lay within ambiguity_radius_m of the predicted target and at least
    ambiguity_min_sep_m apart, someone else is close by and the plain 5 deg is kept, so a person beside
    the target is not taken when the target's own box is missed (T15).

    Lock-on uses the controller's start window: range 0.5-1.0 m, near the image centre.
    """

    def __init__(self, lock_range=(0.5, 1.0), lock_bearing_deg=15.0, bearing_sigma_deg=5.0,
                 range_sigma_m=0.15, chroma_sigma=15.0, gate=9.0, widen_per_s=1.0,
                 alpha=0.6, beta=0.2, chroma_rate=0.05, min_rate_dt=0.015, unlock_after_s=5.0,
                 hist_sigma=0.2, hist_window=10, hist_learn_slack=0.1, hist_weight=0.25,
                 reacquire_after_s=1.0, reacquire_colour_max=1.0, reacquire_bearing_deg=35.0,
                 reacquire_dist_m=0.8, reacquire_speed_mps=1.5, reacquire_dist_max_m=3.0,
                 lateral_sigma_m=0.15, ambiguity_window_s=1.0, ambiguity_radius_m=1.0,
                 ambiguity_min_sep_m=0.25, ambiguity_frame_s=0.03):
        self.lock_range = lock_range
        self.lock_bearing = math.radians(lock_bearing_deg)
        self.sb = math.radians(bearing_sigma_deg)
        self.sr = range_sigma_m
        self.lateral_sigma = lateral_sigma_m
        self.ambiguity_window = ambiguity_window_s
        self.ambiguity_radius = ambiguity_radius_m
        self.ambiguity_min_sep = ambiguity_min_sep_m
        self.ambiguity_frame = ambiguity_frame_s
        self.sc = chroma_sigma
        self.gate = gate
        self.widen_per_s = widen_per_s
        self.alpha, self.beta = alpha, beta
        self.chroma_rate = chroma_rate
        # Hellinger distance between histograms: about 0.2 for the same person, 0.5-0.7 for another
        self.hist_sigma = hist_sigma
        self.hist_window = hist_window
        self.hist_learn_slack = hist_learn_slack
        self.hist_weight = hist_weight  # share of the colour cost from the histogram; the rest from Cb/Cr
        self.reacquire_after_s = reacquire_after_s
        self.reacquire_colour_max = reacquire_colour_max
        self.reacquire_bearing = math.radians(reacquire_bearing_deg)
        self.reacquire_dist = reacquire_dist_m
        self.reacquire_speed = reacquire_speed_mps
        self.reacquire_dist_max = reacquire_dist_max_m
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
        self.hists = []  # the target's last learned torso histograms (normalised)
        self.boxes = []  # (t, x, y) of recent boxes near the target, robot frame
        self.ambiguous_until = -math.inf  # someone else was beside the target until then

    def hist_model(self):
        return [sum(col) / len(self.hists) for col in zip(*self.hists)]

    def _learn_hist(self, hist):
        if not self.hists:
            self.hists = [hist]
            return
        model = self.hist_model()
        floor = min(bhattacharyya(h, model) for h in self.hists) - self.hist_learn_slack
        if bhattacharyya(hist, model) >= floor:
            self.hists = (self.hists + [hist])[-self.hist_window:]

    def _predict(self, t):
        dt = max(0.0, min(t - self.t, 1.0))
        return self.bearing + self.bearing_rate * dt, self.range + self.range_rate * dt

    def cost(self, t, bearing, rng, chroma=None, hist=None):
        """Normalised squared distance of a detection from the target (inf before lock-on)."""
        if not self.locked:
            return math.inf
        pb, pr = self._predict(t)
        widen = 1.0 + self.widen_per_s * max(0.0, t - self.t - 0.2)
        sb = self.sb
        if t >= self.ambiguous_until:  # alone: never under lateral_sigma sideways
            sb = max(sb, self.lateral_sigma / max(0.3, (rng + pr) / 2.0))
        c = ((bearing - pb) / (sb * widen)) ** 2 + ((rng - pr) / (self.sr * widen)) ** 2
        return c + self.colour_cost(chroma, hist)

    def colour_cost(self, chroma=None, hist=None):
        """The colour part of the cost: Cb/Cr and, when both sides have one, the histogram."""
        c = 0.0
        w = self.hist_weight if hist is not None and self.hists else 0.0
        if w:
            d = math.sqrt(max(0.0, 1.0 - bhattacharyya(hist, self.hist_model())))
            c += w * (d / self.hist_sigma) ** 2
        if chroma is not None and self.chroma is not None:
            c += (1.0 - w) * ((chroma[0] - self.chroma[0]) ** 2 + (chroma[1] - self.chroma[1]) ** 2) / self.sc ** 2
        return c

    def _reacquire(self, t, bearing, rng, chroma, hist):
        """Take a lost target back by colour near its predicted bearing (see the class docstring)."""
        if hist is None or not self.hists or t - self.t < self.reacquire_after_s:
            return False
        pb, _ = self._predict(t)
        if abs(bearing - pb) > self.reacquire_bearing \
                or self.colour_cost(chroma, hist) > self.reacquire_colour_max:
            return False
        # where the target could have walked to since it was last seen (robot frame; the robot stops
        # or holds while the target is lost, so its own motion is small against this allowance)
        reach = min(self.reacquire_dist_max, self.reacquire_dist + self.reacquire_speed * (t - self.t))
        dx = rng * math.cos(bearing) - self.range * math.cos(self.bearing)
        dy = rng * math.sin(bearing) - self.range * math.sin(self.bearing)
        if math.hypot(dx, dy) > reach:
            return False
        self.t, self.bearing, self.range = t, bearing, rng
        self.bearing_rate = self.range_rate = 0.0
        self._learn_colour(chroma, hist)
        return True

    def _learn_colour(self, chroma, hist):
        if chroma is not None:
            if self.chroma is None:
                self.chroma = tuple(chroma)
            else:
                k = self.chroma_rate
                self.chroma = (self.chroma[0] + k * (chroma[0] - self.chroma[0]),
                               self.chroma[1] + k * (chroma[1] - self.chroma[1]))
        if hist is not None:
            self._learn_hist(hist)

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

    def _note_box(self, t, bearing, rng):
        """Remember boxes near the predicted target; two people there in one frame make it ambiguous."""
        pb, pr = self._predict(t)
        x, y = rng * math.cos(bearing), rng * math.sin(bearing)
        if math.hypot(x - pr * math.cos(pb), y - pr * math.sin(pb)) > self.ambiguity_radius:
            return
        self.boxes = [b for b in self.boxes if t - b[0] <= self.ambiguity_frame] + [(t, x, y)]
        for _, bx, by in self.boxes[:-1]:
            if math.hypot(x - bx, y - by) >= self.ambiguity_min_sep:
                self.ambiguous_until = t + self.ambiguity_window
                break

    def note_crowded(self, t):
        """Someone else is near the target (from the scan): keep the plain gate for ambiguity_window_s."""
        self.ambiguous_until = max(self.ambiguous_until, t + self.ambiguity_window)

    def accept(self, t, bearing, rng, chroma=None, hist=None):
        """True if this detection is the target; updates the track when it is."""
        if self.locked and t - self.t > self.unlock_after_s:
            self.reset()
        if self.locked:
            self._note_box(t, bearing, rng)
        if not self.locked:
            if self.lock_range[0] <= rng <= self.lock_range[1] and abs(bearing) <= self.lock_bearing:
                self.locked, self.t = True, t
                self.bearing, self.range = bearing, rng
                self.chroma = tuple(chroma) if chroma is not None else None
                self.hists = [hist] if hist is not None else []
                # the first second after lock-on keeps the plain gate: nobody else has been checked yet,
                # and a second box in this very frame must meet the lock-on box to count as ambiguous
                self.ambiguous_until = t + self.ambiguity_window
                self.boxes = [(t, rng * math.cos(bearing), rng * math.sin(bearing))]
                return True
            return False
        if self.cost(t, bearing, rng, chroma, hist) > self.gate:
            return self._reacquire(t, bearing, rng, chroma, hist)
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
        self._learn_colour(chroma, hist)
        return True


# TargetGate settings exposed as ROS parameters, with TargetGate's own defaults
GATE_PARAMS = {
    'bearing_sigma_deg': 5.0,
    'lateral_sigma_m': 0.15,
    'ambiguity_window_s': 1.0,
    'ambiguity_radius_m': 1.0,
    'range_sigma_m': 0.15,
    'hist_weight': 0.25,
    'reacquire_after_s': 1.0,
    'reacquire_colour_max': 1.0,
    'reacquire_bearing_deg': 35.0,
    'reacquire_dist_m': 0.8,
    'reacquire_speed_mps': 1.5,
    'reacquire_dist_max_m': 3.0,
}


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
        self.declare_parameter('use_hs_hist', True)  # torso hue-saturation histogram, when the camera sends it
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
        # a box's range from the LiDAR cluster centred on it, not the nearest return in its sector
        self.declare_parameter('box_range_from_scan', True)
        # the scan tells the gate when someone else is near the target, whatever order the boxes come in
        self.declare_parameter('crowd_from_scan', True)
        self.declare_parameter('crowd_radius_m', 0.5)  # only returns this close to the predicted target count
        # each fresh scan moves the target track to the target's own cluster when nobody else is near it,
        # so a fast side step does not leave the camera gate behind (side_step twin failures)
        self.declare_parameter('lidar_assist', True)
        self.declare_parameter('lidar_assist_dist_m', 0.35)  # the cluster must be this close to the prediction
        # nobody walks faster than this: a cluster farther from the target's last fix is someone else
        # (a passer-by covering the target from the LiDAR, twin crossing run)
        self.declare_parameter('lidar_assist_speed_mps', 1.5)
        # the target's box where the gate predicts it, but the LiDAR range there is someone nearer covering it
        # (blind_corner: the bystander at the corner). Use the predicted range rather than the near one, which
        # made the follower stop as if the target were 0.5 m away; the obstacle stop in follow_stop deals with
        # whoever is in front. 0 turns it off.
        self.declare_parameter('occluded_gap_m', 0.4)
        self.declare_parameter('occluded_bearing_deg', 6.0)
        # TargetGate tunables, so an experiment's -p really reaches the gate (undeclared -p are ignored)
        for name, value in GATE_PARAMS.items():
            self.declare_parameter(name, value)

        self.max_dt = float(self.get_parameter('max_dt').value)
        self.buffer_sec = float(self.get_parameter('buffer_sec').value)
        self.yolo_topic = str(self.get_parameter('yolo_topic').value)
        self.lidar_topic = str(self.get_parameter('lidar_topic').value)
        self.camera_hfov_deg = float(self.get_parameter('camera_hfov_deg').value)
        self.image_width = int(self.get_parameter('image_width').value)
        self.lidar_angles = []  # centre angle of each LiDAR sector, robot frame, left positive
        self.use_gate = bool(self.get_parameter('target_gate').value)
        self.use_chroma = bool(self.get_parameter('use_chroma').value)
        self.use_hs_hist = bool(self.get_parameter('use_hs_hist').value)
        gate_args = {name: float(self.get_parameter(name).value) for name in GATE_PARAMS}
        self.gate = TargetGate(**gate_args)
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
        self.box_range_from_scan = bool(self.get_parameter('box_range_from_scan').value)
        self.crowd_from_scan = bool(self.get_parameter('crowd_from_scan').value)
        self.crowd_radius = float(self.get_parameter('crowd_radius_m').value)
        self.crowd_logged = False  # last [CROWD] state written to the log
        self.lidar_assist = bool(self.get_parameter('lidar_assist').value)
        self.assist_dist = float(self.get_parameter('lidar_assist_dist_m').value)
        self.assist_scan_time = None  # the scan the last assist used, so each scan is used once
        self.assist_speed = float(self.get_parameter('lidar_assist_speed_mps').value)
        self.assist_last = None       # (time, bearing, range) of the last assist
        self.occl_gap = float(self.get_parameter('occluded_gap_m').value)
        self.occl_bearing = math.radians(float(self.get_parameter('occluded_bearing_deg').value))
        self.occl_logged = False
        # the effective settings, so a run's log shows what it actually ran with
        self.get_logger().info('[GATE] ' + ' '.join(f'{k}={v:g}' for k, v in sorted(
            {**gate_args, 'crowd_from_scan': float(self.crowd_from_scan), 'crowd_radius_m': self.crowd_radius,
             'lidar_assist': float(self.lidar_assist), 'lidar_assist_dist_m': self.assist_dist,
             'lidar_assist_speed_mps': self.assist_speed, 'occluded_gap_m': self.occl_gap}.items())))
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

        # ---------- pub ----------
        self.pub_synced = self.create_publisher(
            Float32MultiArray, '/synced_target', 10)

        # ---------- timers ----------
        self.gc_timer = self.create_timer(0.5, self.gc_buffers)
        self.track_timer = self.create_timer(0.1, self.on_track_timer)
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
        # [cx, cy, sector, cb, cr, h0..h47] carries the clothing colour; old 3-value messages have none
        chroma = (msg.data[3], msg.data[4]) if len(msg.data) >= 5 and self.use_chroma else None
        hist = parse_hist(msg.data[5:]) if self.use_chroma and self.use_hs_hist else None
        self.buf_yolo.append((t, {'cx': cx, 'cy': cy, 'sector_id': sector_id}))
        self.try_sync_from_yolo(t, cx, cy, sector_id, chroma, hist)

    def cb_lidar(self, msg):
        t = self.now_sec()
        if not msg.data:
            return
        self.buf_lidar.append((t, list(msg.data)))

    def cb_scan(self, msg):
        pts = []
        for i, r in enumerate(msg.ranges):
            if math.isfinite(r) and msg.range_min < r < msg.range_max:
                a = (msg.angle_min + i * msg.angle_increment + self.lidar_offset + math.pi) % (2.0 * math.pi) - math.pi
                pts.append((a, r))
        self.scan_points = pts
        self.scan_time = self.now_sec()

    def on_track_timer(self):
        self.track_with_lidar(self.assist_with_lidar())

    def assist_with_lidar(self):
        """Move the target track to the target's own LiDAR cluster, once per fresh scan.

        The camera track lags a fast side step (0.25 m at 0.7 m is 20 deg in 0.3 s), so the next box falls
        outside the gate even though the LiDAR saw every step. Only a person-sized cluster within
        lidar_assist_dist_m of the prediction is taken, and only when the scan shows nobody else near the
        target (scan_crowded), so a passer-by is never taken this way; with someone close the camera
        decides alone, as before. Not more than lidar_track_max_s after the last camera fix.
        Returns (bearing, range) of the cluster used, or None.
        """
        if not (self.use_gate and self.lidar_assist and self.gate.locked and self.last_camera_fix is not None):
            return None
        now = self.now_sec()
        if not scan_is_fresh(now, self.scan_time, self.scan_max_age) or self.scan_time == self.assist_scan_time:
            return None
        self.assist_scan_time = self.scan_time
        if now - self.last_camera_fix > self.lidar_max:
            return None
        if now < self.gate.ambiguous_until:
            # someone was just near the target (two boxes, or the scan's crowd check): their cluster may have
            # lent its range to the target's box, and following clusters would carry the track off with them
            # (twin crossing runs). Until the window ends the camera decides alone.
            return None
        pb, pr = self.gate._predict(now)
        found = lidar_track(self.scan_points, pb, pr, math.atan2(self.assist_dist, max(pr, 0.3)),
                            self.assist_dist, width_m=(0.05, 0.8))
        if found is None:
            return None
        bearing, rng = found
        px, py = pr * math.cos(pb), pr * math.sin(pb)
        if math.hypot(rng * math.cos(bearing) - px, rng * math.sin(bearing) - py) > self.assist_dist:
            return None
        if scan_crowded(self.scan_points, bearing, rng, pb, pr, self.crowd_radius):
            return None
        if rng < pr - 0.2:
            return None  # well in front of where the target should be: someone covering it from the LiDAR
        # the last fix of the target, by the camera or by an earlier assist
        last = (self.last_camera_fix, self.last_camera_bearing, self.last_target[3]) \
            if self.last_target is not None else None
        if self.assist_last is not None and (last is None or self.assist_last[0] > last[0]):
            last = self.assist_last
        if last is not None:
            _, lb, lr = last
            moved = math.hypot(rng * math.cos(bearing) - lr * math.cos(lb), rng * math.sin(bearing) - lr * math.sin(lb))
            if moved > self.assist_speed * max(0.0, now - last[0]) + 0.08:
                return None  # faster than anyone walks: someone else, such as a passer-by covering the target
        self.gate.accept_lidar(now, bearing, rng)
        self.assist_last = (now, bearing, rng)
        return found

    def track_with_lidar(self, assisted=None):
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
        if assisted is not None:
            bearing, rng = assisted  # the assist already moved the track to the target's own cluster
        else:
            found = lidar_track(self.scan_points, pb, pr, math.radians(25.0), 0.5)
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

    def try_sync_from_yolo(self, ty, cx, cy, sector_id, chroma=None, hist=None):
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
        if self.box_range_from_scan and scan_is_fresh(ty, self.scan_time, self.scan_max_age):
            own = box_range(self.scan_points, bearing)
            dist = own if own is not None else float('inf')

        # ✅ skip inf distance
        if not math.isfinite(dist):
            self.get_logger().debug(f"Skip frame: invalid LiDAR dist in sector {sector_id}")
            return

        reason = 'gate'
        if self.use_gate and self.crowd_from_scan and self.gate.locked:
            if not scan_is_fresh(ty, self.scan_time, self.scan_max_age):
                # no fresh scan (stale, missing or dated ahead): nobody can be ruled out beside the
                # target, so keep the plain gate rather than let a stranger in (T15, Codex)
                self.gate.note_crowded(ty)
                reason = 'no-fresh-scan'
            else:
                pb, pr = self.gate._predict(ty)
                if scan_crowded(self.scan_points, bearing, dist, pb, pr, self.crowd_radius):
                    self.gate.note_crowded(ty)
                    reason = 'scan'
        if self.use_gate:
            # one line each time the plain gate starts or stops being forced, for robot day (E4b)
            crowded = self.gate.locked and ty < self.gate.ambiguous_until
            if crowded != self.crowd_logged:
                self.get_logger().info(f"[CROWD] {'on' if crowded else 'off'} t={ty:.2f}"
                                       + (f" reason={reason}" if crowded else ''))
                self.crowd_logged = crowded

        occluded = False
        if self.use_gate and self.gate.locked and self.occl_gap > 0.0:
            pb, pr = self.gate._predict(ty)
            occluded = abs(bearing - pb) <= self.occl_bearing and dist < pr - self.occl_gap
            if occluded:
                dist = pr  # the target's own range, as predicted; someone nearer covers it from the LiDAR
            if occluded != self.occl_logged:
                self.get_logger().info(f"[OCCL] {'on' if occluded else 'off'} t={ty:.2f}"
                                       + (f" predicted range {pr:.2f} m" if occluded else ''))
                self.occl_logged = occluded
        if self.use_gate and not self.gate.accept(ty, bearing, dist, chroma, hist):
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
