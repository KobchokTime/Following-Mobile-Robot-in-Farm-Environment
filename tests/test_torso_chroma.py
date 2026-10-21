"""Offline test for the clothing chroma in ros2_yolo_live.py (no ROS, no camera, no model)."""

import importlib.util
import sys
import types
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
NODE = ROOT / "ros2_yolo_ws" / "scripts" / "ros2_yolo_live.py"


def _load():
    names = ["rclpy", "rclpy.node", "sensor_msgs", "sensor_msgs.msg", "std_msgs", "std_msgs.msg",
             "cv_bridge", "cv2", "ultralytics"]
    stubs = {n: types.ModuleType(n) for n in names}
    stubs["rclpy.node"].Node = object
    stubs["sensor_msgs.msg"].Image = object
    stubs["std_msgs.msg"].Int32MultiArray = object
    stubs["cv_bridge"].CvBridge = object
    stubs["ultralytics"].YOLO = object
    previous = {k: sys.modules.get(k) for k in stubs}
    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location("yolo_live_under_test", NODE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for k, v in previous.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


class TorsoChromaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chroma = staticmethod(_load().torso_chroma)

    def test_grey_is_neutral(self):
        frame = np.full((100, 100, 3), 90, np.uint8)
        self.assertEqual(self.chroma(frame, 10, 10, 90, 90), (128, 128))

    def test_red_shirt_has_high_cr_low_cb(self):
        frame = np.zeros((200, 100, 3), np.uint8)
        frame[:, :] = (0, 0, 200)  # BGR red
        cb, cr = self.chroma(frame, 0, 0, 100, 200)
        self.assertGreater(cr, 160)
        self.assertLess(cb, 128)

    def test_background_and_legs_are_ignored(self):
        frame = np.zeros((200, 100, 3), np.uint8)
        frame[:, :] = (200, 0, 0)          # blue background and legs
        frame[40:110, 25:75] = (0, 0, 200)  # red torso band
        cb, cr = self.chroma(frame, 0, 0, 100, 200)
        self.assertGreater(cr, 160)

    def test_darker_light_pulls_chroma_towards_grey(self):
        frame = np.zeros((100, 100, 3), np.uint8)
        frame[:, :] = (40, 40, 160)
        bright = self.chroma(frame, 0, 0, 100, 100)
        dim = self.chroma((frame * 0.5).astype(np.uint8), 0, 0, 100, 100)
        self.assertLess(abs(dim[1] - 128), abs(bright[1] - 128))  # the twin's shade model relies on this

    def test_empty_region(self):
        frame = np.zeros((10, 10, 3), np.uint8)
        self.assertEqual(self.chroma(frame, 5, 5, 5, 5), (128, 128))


if __name__ == "__main__":
    unittest.main()
