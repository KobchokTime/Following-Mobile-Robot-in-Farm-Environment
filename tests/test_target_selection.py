"""Offline tests for the Arena 3 target association in sync_fusion_node."""

import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "ros2_yolo_ws" / "scripts" / "Image" / "sync_fusion_node.py"


def _load_sync_module():
    rclpy = types.ModuleType("rclpy")
    node = types.ModuleType("rclpy.node")
    node.Node = object
    qos = types.ModuleType("rclpy.qos")
    for name in ("QoSProfile", "QoSReliabilityPolicy", "QoSHistoryPolicy", "QoSDurabilityPolicy"):
        setattr(qos, name, object)
    std_msgs = types.ModuleType("std_msgs")
    std_msgs_msg = types.ModuleType("std_msgs.msg")
    std_msgs_msg.Int32MultiArray = std_msgs_msg.Float32MultiArray = object
    modules = {"rclpy": rclpy, "rclpy.node": node, "rclpy.qos": qos,
               "std_msgs": std_msgs, "std_msgs.msg": std_msgs_msg}
    previous = {key: sys.modules.get(key) for key in modules}
    sys.modules.update(modules)
    try:
        spec = importlib.util.spec_from_file_location("target_selection_under_test", SYNC)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for key, old in previous.items():
            if old is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = old


class TargetSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_sync_module()

    def test_parses_legacy_and_chroma_detections(self):
        self.assertEqual(self.module.parse_yolo_detection([320, 240, 4]),
                         (320, 240, 4, None, None))
        self.assertEqual(self.module.parse_yolo_detection([320, 240, 4, 110, 165]),
                         (320, 240, 4, 110, 165))
        self.assertIsNone(self.module.parse_yolo_detection([320, 240]))

    def test_locks_only_to_a_detection_in_the_initial_range(self):
        selector = self.module.TargetSelector()
        self.assertFalse(selector.consider(320, 1.8, 0.0, 160, 110))
        self.assertTrue(selector.consider(320, 0.9, 0.1, 110, 165))

    def test_rejects_side_by_side_distractor_with_same_clothes(self):
        selector = self.module.TargetSelector()
        self.assertTrue(selector.consider(320, 0.9, 0.0, 110, 165))
        # Same chroma cannot override the target's nearby range and bearing.
        self.assertFalse(selector.consider(500, 1.8, 0.01, 110, 165))
        self.assertAlmostEqual(selector.last_dist, 0.9)

    def test_uses_chroma_to_reject_a_geometrically_plausible_distractor(self):
        selector = self.module.TargetSelector()
        self.assertTrue(selector.consider(320, 0.9, 0.0, 110, 165))
        self.assertFalse(selector.consider(325, 1.0, 0.1, 160, 110))
        self.assertAlmostEqual(selector.last_dist, 0.9)

    def test_accepts_target_chroma_shift_towards_grey_in_shade(self):
        selector = self.module.TargetSelector()
        self.assertTrue(selector.consider(320, 0.9, 0.0, 110, 165))
        self.assertTrue(selector.consider(322, 0.95, 0.1, 119, 147))
        self.assertAlmostEqual(selector.last_dist, 0.95)

    def test_accepts_legacy_detection_without_chroma_after_lock(self):
        selector = self.module.TargetSelector()
        self.assertTrue(selector.consider(320, 0.9, 0.0))
        self.assertTrue(selector.consider(325, 0.95, 0.1))


if __name__ == "__main__":
    unittest.main()
