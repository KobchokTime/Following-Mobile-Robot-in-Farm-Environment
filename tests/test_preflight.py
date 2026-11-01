"""Offline tests for tools/robot_day/preflight.py (no ROS)."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "robot_day"))

import preflight as P  # noqa: E402


class PreflightTest(unittest.TestCase):
    def test_rate_verdict(self):
        self.assertEqual(P.rate_verdict("/scan", 50, 5.0)[0], "PASS")
        self.assertEqual(P.rate_verdict("/scan", 25, 5.0)[0], "WARN")
        self.assertEqual(P.rate_verdict("/scan", 0, 5.0)[0], "FAIL")

    def test_scan_verdict(self):
        self.assertEqual(P.scan_verdict([], 12.0)[0], "FAIL")
        self.assertEqual(P.scan_verdict([float("inf")] * 9 + [1.0], 12.0)[0], "WARN")
        self.assertEqual(P.scan_verdict([2.0] * 10, 12.0)[0], "PASS")

    def test_speed_params(self):
        self.assertEqual(P.check_speed_params("mps", 0.085, 0.5, 1.0)[0], "PASS")
        self.assertEqual(P.check_speed_params("mps", 0.085, 1.4, 1.0)[0], "WARN")
        self.assertEqual(P.check_speed_params("mps", 85, 0.5, 1.0)[0], "FAIL")
        self.assertEqual(P.check_speed_params("rpm", 0.085, 0.5, 1.0)[0], "FAIL")

    def test_obstacle_params(self):
        # T18 re-review (Codex 2026-11-01 09:52, items 3-4)
        self.assertEqual(P.check_obstacle_params(True, False, 0.0)[0], "PASS")
        self.assertEqual(P.check_obstacle_params(False, False, 0.0)[0], "FAIL")
        self.assertEqual(P.check_obstacle_params(True, False, 3.0)[0], "FAIL")
        self.assertEqual(P.check_obstacle_params(True, True, 0.0)[0], "WARN")

    def test_launch_passes_one_obstacle_stop_to_both_nodes(self):
        # the launch file, with stand-ins for the launch package: follow_stop and sync_fusion get the same value,
        # and avoid_trail is off by default on the robot
        import importlib.util
        import types
        actions_mod = types.SimpleNamespace(DeclareLaunchArgument=lambda *a, **k: None, OpaqueFunction=lambda **k: None,
                                            ExecuteProcess=lambda **k: k)
        saved = {k: sys.modules.get(k) for k in ("launch", "launch.actions")}
        sys.modules["launch"] = types.SimpleNamespace(LaunchDescription=list)
        sys.modules["launch.actions"] = actions_mod
        try:
            spec = importlib.util.spec_from_file_location(
                "bringup", ROOT / "ros2_yolo_ws" / "launch" / "follow_bringup.launch.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        finally:
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v
        for value in ("true", "false"):
            procs = {p["name"]: p["cmd"] for p in mod.actions({**mod.DEFAULTS, "obstacle_stop": value})}
            self.assertIn(f"obstacle_stop:={value}", procs["follow_stop"])
            self.assertIn(f"obstacle_stop:={value}", procs["sync_fusion"])
        self.assertIn("avoid_trail:=false", {p["name"]: p["cmd"] for p in mod.actions(mod.DEFAULTS)}["follow_stop"])

    def test_model_and_calibration(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(P.check_model(d)[0], "FAIL")
            (Path(d) / "yolov8n.xml").write_text("")
            self.assertEqual(P.check_model(d)[0], "PASS")
            cal = Path(d) / "cal.md"
            cal.write_text("wheel_radius_m is not measured on this chassis yet\n")
            self.assertEqual(P.check_calibration(cal)[0], "WARN")
            cal.write_text("wheel_radius_m = 0.083 (measured 2026-11-02)\n")
            self.assertEqual(P.check_calibration(cal)[0], "PASS")


if __name__ == "__main__":
    unittest.main()
