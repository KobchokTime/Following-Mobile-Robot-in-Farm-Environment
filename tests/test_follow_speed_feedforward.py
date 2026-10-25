"""Offline tests for the follow controller's speed feed-forward (Arena 2 entry, no ROS)."""

import importlib.util
import math
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLLOW_STOP = ROOT / "ros2_yolo_ws" / "scripts" / "MAIN" / "Control" / "follow_stop_node.py"


def _load():
    stubs = {"rclpy": types.ModuleType("rclpy"), "rclpy.node": types.ModuleType("rclpy.node"),
             "std_msgs": types.ModuleType("std_msgs"), "std_msgs.msg": types.ModuleType("std_msgs.msg"),
             "geometry_msgs": types.ModuleType("geometry_msgs"),
             "geometry_msgs.msg": types.ModuleType("geometry_msgs.msg")}
    stubs["rclpy.node"].Node = object
    stubs["std_msgs.msg"].Float32MultiArray = object
    stubs["geometry_msgs.msg"].Twist = object
    previous = {k: sys.modules.get(k) for k in stubs}
    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location("follow_stop_ff_under_test", FOLLOW_STOP)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for k, v in previous.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


PARAMS = dict(linear_gain=1.5, tolerance=0.1, max_linear_speed=3.5, ff_gain=1.0, ff_max=1.0, ff_decay_s=0.3)


class SpeedFeedForwardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cmd = staticmethod(_load().speed_command)

    def test_feedforward_grows_while_behind_and_is_capped(self):
        ff = 0.0
        for _ in range(200):
            _, ff = self.cmd(1.0, ff, 0.1, **PARAMS)
        self.assertAlmostEqual(ff, 1.0)

    def test_feedforward_bleeds_off_when_too_close(self):
        _, ff = self.cmd(-0.05, 0.8, 0.3, **PARAMS)
        self.assertAlmostEqual(ff, 0.8 * 0.36787944, places=5)

    def test_too_close_backs_off_without_feedforward(self):
        linear, _ = self.cmd(-0.3, 0.8, 0.1, **PARAMS)
        self.assertAlmostEqual(linear, -0.45)

    def test_inside_the_band_holds_the_learned_speed(self):
        linear, ff = self.cmd(0.05, 0.6, 0.1, **PARAMS)
        self.assertAlmostEqual(linear, ff)
        self.assertGreater(ff, 0.6)

    def test_first_sample_is_plain_proportional(self):
        linear, ff = self.cmd(0.5, 0.0, 0.0, **PARAMS)
        self.assertAlmostEqual(linear, 0.75)
        self.assertEqual(ff, 0.0)

    def test_long_gaps_between_samples_are_clamped(self):
        _, ff = self.cmd(1.0, 0.0, 30.0, **PARAMS)
        self.assertAlmostEqual(ff, 0.5)

    def test_braking_caps_speed_to_what_can_stop_in_the_gap(self):
        linear, _ = self.cmd(0.2, 1.0, 0.1, **PARAMS, max_decel=0.8)
        self.assertAlmostEqual(linear, (2 * 0.8 * 0.2) ** 0.5)
        linear, _ = self.cmd(2.0, 1.0, 0.1, **PARAMS, max_decel=0.8)
        self.assertGreater(linear, 1.7)  # far away: not limited

    def test_braking_allows_for_the_gap_closed_during_latency(self):
        # at 1.0 m/s with 0.2 s latency the robot is 0.2 m nearer than the 0.3 m measured
        linear, _ = self.cmd(0.3, 1.0, 0.1, **PARAMS, max_decel=0.8, latency_s=0.2, prev_linear=1.0)
        self.assertAlmostEqual(linear, (2 * 0.8 * 0.1) ** 0.5)
        linear, _ = self.cmd(0.3, 1.0, 0.1, **PARAMS, max_decel=0.8, latency_s=0.2, prev_linear=-0.5)
        self.assertAlmostEqual(linear, (2 * 0.8 * 0.3) ** 0.5)  # reversing never loosens the cap

    def test_wheel_speed_estimate_follows_the_bridge_ramp(self):
        est = _load().wheel_speed_estimate
        self.assertAlmostEqual(est(1.0, 0.0, 0.1, 1.0), 0.9)   # slowing: wheels lag the stop command
        self.assertAlmostEqual(est(0.0, 0.5, 0.1, 1.0), 0.1)   # speeding up
        self.assertAlmostEqual(est(0.45, 0.5, 0.1, 1.0), 0.5)  # reaches the command
        self.assertAlmostEqual(est(-0.3, 0.0, 0.1, 1.0), -0.2)

    def test_braking_uses_the_wheel_speed_not_the_command(self):
        # Codex T11: gap error 0.2 m, latency 0.2 s, last command 0 but wheels still at 1.0 m/s
        linear, _ = self.cmd(0.2, 1.0, 0.1, **PARAMS, max_decel=0.8, latency_s=0.2, prev_linear=1.0)
        self.assertEqual(linear, 0.0)

    def test_camera_bearing_matches_the_pinhole_model(self):
        m = _load()
        self.assertAlmostEqual(m.camera_bearing(320, 640, 70.0), 0.0)
        self.assertAlmostEqual(m.camera_bearing(0, 640, 70.0), math.radians(35.0))     # left edge, left positive
        self.assertAlmostEqual(m.camera_bearing(640, 640, 70.0), -math.radians(35.0))

    def test_bearing_turn_leads_the_target_and_saturates(self):
        turn = _load().bearing_turn
        self.assertEqual(turn(math.radians(2), 0.0, 0.2, 2.5, 1.2, math.radians(3)), 0.0)  # deadband
        self.assertAlmostEqual(turn(0.2, 0.0, 0.2, 2.5, 1.2, 0.05), 0.5)
        self.assertAlmostEqual(turn(0.2, 1.0, 0.2, 2.5, 1.2, 0.05), 1.0)   # moving left: turn sooner
        self.assertAlmostEqual(turn(0.1, -1.0, 0.2, 2.5, 1.2, 0.05), -0.25)  # already swinging back
        self.assertEqual(turn(1.0, 0.0, 0.2, 2.5, 1.2, 0.05), 1.2)

    def test_output_is_clamped_to_max_speed(self):
        linear, _ = self.cmd(5.0, 1.0, 0.1, **PARAMS)
        self.assertEqual(linear, 3.5)


if __name__ == "__main__":
    unittest.main()
