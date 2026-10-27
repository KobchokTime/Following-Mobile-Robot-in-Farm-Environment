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

    def test_a_box_far_behind_a_near_person_gets_its_own_range(self):
        near = self._person(0.8, 0.0)
        far_b = math.radians(18.0)
        far = self._person(7.0 * math.cos(far_b), 7.0 * math.sin(far_b))
        scan = [p for p in near + far if not any(abs(p[0] - q[0]) < 1e-9 and q[1] < p[1] for q in near + far)]
        mids = sectorizer_mids()
        sector_min = min(r for b, r in scan if abs(b - mids[self.m.nearest_sector(far_b, mids)]) <= math.radians(3.9))
        self.assertLess(sector_min, 1.0)  # the old sector minimum is the near person's range
        self.assertAlmostEqual(self.m.box_range(scan, far_b), 6.8, delta=0.1)
        self.assertAlmostEqual(self.m.box_range(scan, 0.0), 0.6, delta=0.05)

    def test_a_box_between_two_legs_finds_them(self):
        legs = self._person(1.0, 0.1, radius=0.06) + self._person(1.0, -0.1, radius=0.06)
        self.assertAlmostEqual(self.m.box_range(legs, 0.0), 0.94, delta=0.03)

    def test_no_cluster_near_the_box_gives_none(self):
        self.assertIsNone(self.m.box_range(self._person(2.0, 0.0), math.radians(30.0)))
        self.assertIsNone(self.m.box_range([], 0.0))


if __name__ == "__main__":
    unittest.main()
