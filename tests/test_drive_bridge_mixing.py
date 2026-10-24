"""Offline tests for angular.z support in MAIN/Control/zlac_joystick_bridge.py (no ROS, no serial)."""

import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "ros2_yolo_ws" / "scripts" / "MAIN" / "Control" / "zlac_joystick_bridge.py"
sys.path.insert(0, str(ROOT))

from sim.twin.world import RobotParams, bridge_rpm  # noqa: E402


def _load_bridge():
    stubs = {}
    rclpy = types.ModuleType("rclpy")
    node = types.ModuleType("rclpy.node")
    node.Node = object
    geometry = types.ModuleType("geometry_msgs")
    geometry_msg = types.ModuleType("geometry_msgs.msg")
    geometry_msg.Twist = object
    modbus = types.ModuleType("minimalmodbus")
    stubs.update({"rclpy": rclpy, "rclpy.node": node, "geometry_msgs": geometry,
                  "geometry_msgs.msg": geometry_msg, "minimalmodbus": modbus})
    previous = {k: sys.modules.get(k) for k in stubs}
    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location("zlac_bridge_under_test", BRIDGE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for k, v in previous.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


class BridgeMixingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = _load_bridge()

    def test_straight_is_unchanged_from_the_old_bridge(self):
        # old bridge: cmd = clamp(linear * 40, +-40); 0x2088 = -cmd, 0x2089 = +cmd
        for linear in (0.0, 0.25, 0.5, 1.0, 3.5, -0.4):
            cmd = max(-40.0, min(40.0, linear * 40.0))
            self.assertEqual(self.b.wheel_commands(linear, 0.0), (-cmd, cmd))

    def test_angular_ignored_when_disabled(self):
        self.assertEqual(self.b.wheel_commands(0.5, 0.25, use_angular=False), self.b.wheel_commands(0.5, 0.0))

    def test_left_turn_speeds_up_the_right_wheel(self):
        reg_2088, reg_2089 = self.b.wheel_commands(0.5, 0.25)
        right, left = -reg_2088, reg_2089  # logical wheel speeds, forward positive
        self.assertGreater(right, left)

    def test_spin_in_place_writes_the_same_sign_to_both_registers(self):
        reg_2088, reg_2089 = self.b.wheel_commands(0.0, 0.5)
        self.assertLess(reg_2088, 0)
        self.assertLess(reg_2089, 0)

    def test_turn_dir_flips_rotation_only(self):
        a = self.b.wheel_commands(0.5, 0.25, turn_dir=1.0)
        b = self.b.wheel_commands(0.5, 0.25, turn_dir=-1.0)
        # mirrored motors: forward part is 0x2089 - 0x2088, rotation part is 0x2088 + 0x2089
        self.assertAlmostEqual(a[1] - a[0], b[1] - b[0])
        self.assertAlmostEqual(a[0] + a[1], -(b[0] + b[1]))
        self.assertNotEqual(a[0] + a[1], 0.0)

    def test_clamp_keeps_the_turn_ratio(self):
        reg_2088, reg_2089 = self.b.wheel_commands(3.5, 0.25)
        right, left = -reg_2088, reg_2089
        self.assertAlmostEqual(max(abs(right), abs(left)), 40.0)
        unclamped_ratio = (3.5 - 0.25 * 0.2) / (3.5 + 0.25 * 0.2)
        self.assertAlmostEqual(left / right, unclamped_ratio)

    def test_non_finite_command_stops(self):
        for lin, ang in ((float("inf"), 0.0), (float("-inf"), 0.0), (float("nan"), 0.0), (0.5, float("nan"))):
            self.assertEqual(self.b.wheel_commands(lin, ang), (0.0, 0.0))

    def test_turn_dir_is_a_sign_only(self):
        self.assertEqual(self.b.wheel_commands(0.5, 0.25, turn_dir=2.0), self.b.wheel_commands(0.5, 0.25, turn_dir=1.0))

    def test_sim_fixed_mode_matches_the_bridge(self):
        r = RobotParams(bridge_mode="fixed")
        for linear, angular in ((0.5, 0.0), (0.5, 0.25), (0.0, -0.25), (3.5, 0.25), (-0.3, 0.1)):
            reg_2088, reg_2089 = self.b.wheel_commands(linear, angular)
            left, right = bridge_rpm(r, (linear, angular), 0.1)
            self.assertAlmostEqual(left, reg_2089)
            self.assertAlmostEqual(right, -reg_2088)


class BridgeMpsTest(unittest.TestCase):
    """speed_mode "mps": /cmd_vel in m/s, RPM from the wheel radius, per-wheel cap, ramp."""

    @classmethod
    def setUpClass(cls):
        cls.b = _load_bridge()

    def test_straight_one_mps_is_the_right_rpm(self):
        reg_2088, reg_2089 = self.b.wheel_commands_mps(1.0, 0.0, wheel_radius=0.085)
        rpm = 60.0 / (2 * 3.141592653589793 * 0.085)
        self.assertAlmostEqual(reg_2089, rpm)
        self.assertAlmostEqual(reg_2088, -rpm)

    def test_cap_keeps_the_turn_shape(self):
        reg_2088, reg_2089 = self.b.wheel_commands_mps(3.0, 1.0, wheel_radius=0.085, max_speed=1.4)
        right, left = -reg_2088, reg_2089
        self.assertAlmostEqual(max(abs(right), abs(left)), self.b.mps_to_rpm(1.4, 0.085))
        self.assertAlmostEqual(left / right, (3.0 - 0.2) / (3.0 + 0.2))

    def test_same_signs_and_turn_as_legacy(self):
        for lin, ang in ((0.5, 0.0), (0.3, 0.4), (0.0, -0.5), (-0.2, 0.1)):
            a = self.b.wheel_commands(lin, ang)
            b = self.b.wheel_commands_mps(lin, ang)
            for x, y in zip(a, b):
                self.assertEqual(x > 0, y > 0)
                self.assertEqual(x < 0, y < 0)

    def test_non_finite_stops(self):
        self.assertEqual(self.b.wheel_commands_mps(float("nan"), 0.0), (0.0, 0.0))

    def test_ramp(self):
        self.assertEqual(self.b.ramp(0.0, 100.0, 11.0), 11.0)
        self.assertEqual(self.b.ramp(50.0, 0.0, 11.0), 39.0)
        self.assertEqual(self.b.ramp(5.0, 8.0, 11.0), 8.0)

    def test_sim_mps_mode_matches_the_bridge(self):
        r = RobotParams(bridge_mode="mps")
        for linear, angular in ((0.5, 0.0), (1.0, 0.3), (0.0, -0.5), (3.0, 0.2), (-0.3, 0.1)):
            reg_2088, reg_2089 = self.b.wheel_commands_mps(linear, angular)
            left, right = bridge_rpm(r, (linear, angular), 0.1)
            self.assertAlmostEqual(left, reg_2089)
            self.assertAlmostEqual(right, -reg_2088)


if __name__ == "__main__":
    unittest.main()
