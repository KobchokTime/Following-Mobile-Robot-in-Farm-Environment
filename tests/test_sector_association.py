"""Offline tests for direction-based camera/LiDAR sector matching in sync_fusion_node."""

import importlib.util
import math
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "ros2_yolo_ws" / "scripts" / "Image" / "sync_fusion_node.py"


def _load_sync_module():
    class _Node:
        pass

    stubs = {}
    rclpy = types.ModuleType("rclpy")
    node = types.ModuleType("rclpy.node")
    node.Node = _Node
    qos = types.ModuleType("rclpy.qos")
    for name in ("QoSProfile", "QoSReliabilityPolicy", "QoSHistoryPolicy", "QoSDurabilityPolicy"):
        setattr(qos, name, object)
    std_msgs = types.ModuleType("std_msgs")
    std_msgs_msg = types.ModuleType("std_msgs.msg")
    std_msgs_msg.Int32MultiArray = std_msgs_msg.Float32MultiArray = object
    sensor_msgs = types.ModuleType("sensor_msgs")
    sensor_msgs_msg = types.ModuleType("sensor_msgs.msg")
    sensor_msgs_msg.LaserScan = object
    stubs.update({"rclpy": rclpy, "rclpy.node": node, "rclpy.qos": qos,
                  "std_msgs": std_msgs, "std_msgs.msg": std_msgs_msg,
                  "sensor_msgs": sensor_msgs, "sensor_msgs.msg": sensor_msgs_msg})
    previous = {k: sys.modules.get(k) for k in stubs}
    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location("sync_fusion_node_under_test", SYNC)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for k, v in previous.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def sectorizer_mids(fov_min_deg=-35.0, fov_max_deg=35.0, n=9):
    """Sector centre angles exactly as lidar_sectorizer_node.py publishes them."""
    a, b = math.radians(fov_min_deg), math.radians(fov_max_deg)
    edges = [a + (b - a) * i / n for i in range(n + 1)]
    return [(edges[i] + edges[i + 1]) / 2.0 for i in range(n)]


class SectorAssociationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load_sync_module()

    def test_image_centre_is_straight_ahead(self):
        self.assertAlmostEqual(self.m.camera_bearing_rad(320, 640, 70.0), 0.0, places=6)

    def test_image_edges_are_half_the_field_of_view(self):
        self.assertAlmostEqual(math.degrees(self.m.camera_bearing_rad(0, 640, 70.0)), 35.0, places=3)
        self.assertAlmostEqual(math.degrees(self.m.camera_bearing_rad(640, 640, 70.0)), -35.0, places=3)

    def test_person_on_the_left_maps_to_left_lidar_sector(self):
        mids = sectorizer_mids()
        # Left side of the image (small cx) is a positive bearing -> high LiDAR sector index,
        # which is the opposite numbering to the camera's sector 0..8.
        idx = self.m.nearest_sector(self.m.camera_bearing_rad(40, 640, 70.0), mids)
        self.assertEqual(idx, 8)
        idx = self.m.nearest_sector(self.m.camera_bearing_rad(600, 640, 70.0), mids)
        self.assertEqual(idx, 0)

    def test_every_camera_column_finds_a_sector_within_half_a_sector(self):
        mids = sectorizer_mids()
        half = (mids[1] - mids[0]) / 2.0 + 1e-9
        for cx in range(0, 641, 16):
            bearing = self.m.camera_bearing_rad(cx, 640, 70.0)
            idx = self.m.nearest_sector(bearing, mids)
            self.assertLessEqual(abs(mids[idx] - bearing), half, cx)

    def test_no_angles_yet_returns_none(self):
        self.assertIsNone(self.m.nearest_sector(0.1, []))

    @staticmethod
    def _person(x, y, radius=0.2, step_deg=0.5):
        """Scan returns (bearing, range) off a round person at (x, y), as the twin draws them."""
        pts = []
        for i in range(-180, 181):
            b = math.radians(i * step_deg)
            ux, uy = math.cos(b), math.sin(b)
            t = x * ux + y * uy
            d2 = x * x + y * y - t * t
            if t > 0 and d2 <= radius * radius:
                pts.append((b, t - math.sqrt(radius * radius - d2)))
        return pts

    @staticmethod
    def _sector_median(scan, bearing):
        """The range lidar_sectorizer_node.py publishes for the sector a box at this bearing matches:
        the median of the returns in [a1, a2), sectors evenly over -35..35 deg."""
        mids = sectorizer_mids()
        a = math.radians(-35.0) + math.radians(70.0) / 9 * min(range(9), key=lambda k: abs(mids[k] - bearing))
        rs = sorted(r for b, r in scan if a <= b < a + math.radians(70.0) / 9)
        n = len(rs)
        return (rs[n // 2] + rs[(n - 1) // 2]) / 2.0

    def test_a_box_far_behind_a_near_person_gets_its_own_range(self):
        """T13: the target fills +-17 deg at 0.8 m; a look-alike stands at 18 deg, 7.43 m (Codex's replay)."""
        near = [(math.radians(0.5 * k), 0.8) for k in range(-34, 35)]
        far = [(math.radians(17.5 + 0.5 * k), 7.43) for k in range(4)]
        scan = near + far
        far_b = math.radians(18.0)
        self.assertAlmostEqual(self._sector_median(scan, far_b), 0.8)  # the old path borrows the target's range
        self.assertAlmostEqual(self.m.box_range(scan, far_b), 7.43)
        self.assertAlmostEqual(self.m.box_range(scan, 0.0), 0.8)
        # through the gate: target last seen at 2 deg, 0.8 m, unseen 1.2 s; same clothes
        for rng, taken in ((self._sector_median(scan, far_b), True), (self.m.box_range(scan, far_b), False)):
            g = self.m.TargetGate()
            for k in range(5):
                g.accept(0.1 * k, math.radians(2.0), 0.8)
            self.assertEqual(g.accept(1.6, far_b, rng), taken)

    def test_a_box_between_two_legs_finds_them(self):
        legs = self._person(1.0, 0.1, radius=0.06) + self._person(1.0, -0.1, radius=0.06)
        self.assertAlmostEqual(self.m.box_range(legs, 0.0), 0.94, delta=0.03)

    def test_a_person_beside_the_box_does_not_lend_their_range(self):
        """The box looks at the target's edge; a person just beside it has the nearer cluster middle."""
        target = self._person(0.85, 0.0)
        side = math.radians(-20.0)
        other = self._person(1.5 * math.cos(side), 1.5 * math.sin(side))
        scan = [p for p in target + other if not any(abs(p[0] - q[0]) < 1e-9 and q[1] < p[1] for q in target + other)]
        self.assertAlmostEqual(self.m.box_range(scan, math.radians(-12.0)), 0.65, delta=0.05)

    def test_a_person_against_a_crop_row_gets_the_range_at_the_box(self):
        """Person 2 m ahead touching a row that runs past them from 1.2 m away on the right."""
        person = self._person(2.0, 0.0)
        row = []
        for i in range(60):  # the row: a line y = -0.2, x from 1.2 to 2.0 m, joined to the person
            x = 1.2 + i * 0.8 / 60
            row.append((math.atan2(-0.2, x), math.hypot(x, -0.2)))
        scan = sorted(person + row)
        self.assertAlmostEqual(self.m.box_range(scan, 0.0), 1.8, delta=0.05)

    def test_no_cluster_near_the_box_gives_none(self):
        self.assertIsNone(self.m.box_range(self._person(2.0, 0.0), math.radians(30.0)))
        self.assertIsNone(self.m.box_range([], 0.0))


if __name__ == "__main__":
    unittest.main()
