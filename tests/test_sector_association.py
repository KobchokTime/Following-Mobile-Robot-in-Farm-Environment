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
    stubs.update({"rclpy": rclpy, "rclpy.node": node, "rclpy.qos": qos,
                  "std_msgs": std_msgs, "std_msgs.msg": std_msgs_msg})
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


if __name__ == "__main__":
    unittest.main()
