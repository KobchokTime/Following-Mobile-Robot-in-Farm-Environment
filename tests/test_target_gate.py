"""Offline tests for TargetGate in Image/sync_fusion_node.py (Arena 3 entry, no ROS)."""

import importlib.util
import math
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODE = ROOT / "ros2_yolo_ws" / "scripts" / "Image" / "sync_fusion_node.py"


def _load():
    names = ["rclpy", "rclpy.node", "rclpy.qos", "std_msgs", "std_msgs.msg", "sensor_msgs", "sensor_msgs.msg"]
    stubs = {n: types.ModuleType(n) for n in names}
    stubs["rclpy.node"].Node = object
    for k in ("QoSProfile", "QoSReliabilityPolicy", "QoSHistoryPolicy", "QoSDurabilityPolicy"):
        setattr(stubs["rclpy.qos"], k, object)
    stubs["std_msgs.msg"].Int32MultiArray = object
    stubs["std_msgs.msg"].Float32MultiArray = object
    stubs["sensor_msgs.msg"].LaserScan = object
    previous = {k: sys.modules.get(k) for k in stubs}
    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location("sync_fusion_gate_under_test", NODE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for k, v in previous.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


D = math.radians
RED, BLUE = (110, 165), (160, 110)


class TargetGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        module = _load()
        cls.Gate = module.TargetGate
        cls.in_path = staticmethod(module.in_path)
        cls.lidar_track = staticmethod(module.lidar_track)
        cls.bearing_to_cx = staticmethod(module.bearing_to_cx)

    def test_lidar_track_finds_the_target_beside_the_image(self):
        pts = [(D(-60), 0.9), (D(-58), 0.85), (D(10), 3.0), (D(170), 0.5)]
        self.assertAlmostEqual(self.lidar_track(pts, D(-50), 0.8, D(25), 0.5)[1], 0.85)
        self.assertIsNone(self.lidar_track(pts, D(40), 0.8, D(25), 0.5))   # nothing there
        self.assertIsNone(self.lidar_track(pts, D(-50), 2.0, D(25), 0.5))  # wrong range

    def test_bearing_to_cx_is_the_inverse_and_clamps(self):
        self.assertEqual(self.bearing_to_cx(0.0, 640, 70.0), 320)
        self.assertEqual(self.bearing_to_cx(D(80), 640, 70.0), 0)     # far left of the image
        self.assertEqual(self.bearing_to_cx(D(-80), 640, 70.0), 639)  # far right

    def test_lidar_fix_moves_the_track(self):
        g = self.Gate()
        g.accept(0.0, 0.0, 0.8)
        g.accept_lidar(0.5, D(-45), 0.9)
        self.assertLess(g.bearing, D(-20))

    def test_corridor(self):
        self.assertTrue(self.in_path(D(10), 1.0, 0.45))    # 0.17 m to the side
        self.assertFalse(self.in_path(D(-21), 1.7, 0.45))  # 0.61 m to the side
        self.assertFalse(self.in_path(D(170), 1.0, 0.45))  # behind

    def test_locks_only_in_the_start_window(self):
        g = self.Gate()
        self.assertFalse(g.accept(0.0, D(-21), 1.7))  # farther person off-centre
        self.assertFalse(g.accept(0.0, D(30), 0.8))   # close but far off-centre
        self.assertTrue(g.accept(0.1, 0.0, 0.8))

    def test_rejects_a_second_person_beside_the_target(self):
        g = self.Gate()
        g.accept(0.0, 0.0, 0.8, RED)
        for i in range(1, 30):
            t = 0.1 * i
            self.assertTrue(g.accept(t, 0.0, 0.8 + 0.01 * i, RED))
            self.assertFalse(g.accept(t + 0.001, D(-21), 1.7, BLUE))

    def test_geometry_alone_rejects_a_same_coloured_person(self):
        g = self.Gate()
        g.accept(0.0, 0.0, 0.8, RED)
        for i in range(1, 20):
            g.accept(0.1 * i, 0.0, 0.8, RED)
            self.assertFalse(g.accept(0.1 * i + 0.001, D(-21), 1.7, RED))

    def test_colour_rejects_a_differently_dressed_person_at_the_same_place(self):
        g = self.Gate()
        g.accept(0.0, 0.0, 0.8, RED)
        g.accept(0.1, 0.0, 0.8, RED)
        self.assertFalse(g.accept(0.2, D(2), 0.85, BLUE))
        self.assertTrue(g.accept(0.2, D(2), 0.85, RED))

    def test_shade_on_the_target_is_tolerated(self):
        g = self.Gate()
        g.accept(0.0, 0.0, 0.8, RED)
        shaded = (119, 146)  # saturation halved towards grey
        self.assertTrue(g.accept(0.1, 0.0, 0.8, shaded))

    def test_follows_a_turning_target(self):
        g = self.Gate()
        g.accept(0.0, 0.0, 0.8)
        for i in range(1, 40):  # bearing drifts 3 deg per frame
            self.assertTrue(g.accept(0.1 * i, D(3 * i) if i < 10 else D(30 - 3 * (i - 10)), 0.8))

    def test_gate_widens_after_a_loss(self):
        g = self.Gate()
        g.accept(0.0, 0.0, 0.8)
        g.accept(0.1, 0.0, 0.8)
        self.assertFalse(g.accept(0.2, D(8), 1.6))  # a jump of 0.8 m at once is not the target
        self.assertTrue(g.accept(4.1, D(8), 1.9))    # after 4 s unseen the target may have walked on

    def test_old_three_value_messages_work(self):
        g = self.Gate()
        self.assertTrue(g.accept(0.0, 0.0, 0.8, None))
        self.assertTrue(g.accept(0.1, 0.0, 0.82, None))
        self.assertTrue(g.accept(0.2, 0.0, 0.84, RED))  # colour learned once it appears


if __name__ == "__main__":
    unittest.main()
