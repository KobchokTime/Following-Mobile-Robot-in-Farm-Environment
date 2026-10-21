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
    names = ["rclpy", "rclpy.node", "rclpy.qos", "std_msgs", "std_msgs.msg"]
    stubs = {n: types.ModuleType(n) for n in names}
    stubs["rclpy.node"].Node = object
    for k in ("QoSProfile", "QoSReliabilityPolicy", "QoSHistoryPolicy", "QoSDurabilityPolicy"):
        setattr(stubs["rclpy.qos"], k, object)
    stubs["std_msgs.msg"].Int32MultiArray = object
    stubs["std_msgs.msg"].Float32MultiArray = object
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
        cls.Gate = _load().TargetGate

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
