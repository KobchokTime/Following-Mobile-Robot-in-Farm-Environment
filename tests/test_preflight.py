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
        self.assertEqual(P.check_obstacle_params(True, True, 0.0)[0], "FAIL")  # trail on: never ready (02:15)
        for hold in (float("nan"), -1.0):
            self.assertEqual(P.check_obstacle_params(True, False, hold)[0], "FAIL")

    def test_live_params(self):
        # T18 (Codex 2026-11-01 12:49): --live reads the running nodes' values, not the operator's flags
        self.assertEqual(P.param_value("Boolean value is: True"), True)
        self.assertEqual(P.param_value("Double value is: 0.0"), 0.0)
        self.assertIsNone(P.param_value("Node not found"))
        good = {("/follow_stop_node", "obstacle_stop"): True, ("/sync_fusion_node", "obstacle_stop"): True,
                ("/follow_stop_node", "avoid_trail"): False, ("/follow_stop_node", "trail_hold_s"): 0.0}

        def get(changes):
            vals = {**good, **changes}
            return lambda node, name: vals.get((node, name))
        self.assertEqual(P.check_live_params(get({}))[0], "PASS")
        self.assertEqual(P.check_live_params(get({("/sync_fusion_node", "obstacle_stop"): False}))[0], "FAIL")
        self.assertEqual(P.check_live_params(get({("/sync_fusion_node", "obstacle_stop"): None}))[0], "FAIL")
        self.assertEqual(P.check_live_params(get({("/follow_stop_node", "trail_hold_s"): 3.0}))[0], "FAIL")
        # T18 (Codex 2026-11-03 02:15): the trail on, or a hold that is not exactly 0, is a FAIL, never ready
        self.assertEqual(P.check_live_params(get({("/follow_stop_node", "avoid_trail"): True}))[0], "FAIL")
        for hold in (float("nan"), -1.0, float("inf")):
            self.assertEqual(P.check_live_params(get({("/follow_stop_node", "trail_hold_s"): hold}))[0], "FAIL")
        self.assertEqual(P.check_live_params(get({("/follow_stop_node", "trail_hold_s"): "abc"}))[0], "FAIL")

    def test_motion_params(self):
        # T18 (Codex 2026-11-03 02:15): the rest of the motion configuration is read back and compared
        running = {("/follow_stop_node", "obstacle_stop_m"): 0.45, ("/follow_stop_node", "spin_clear_radius_m"): 0.40,
                   ("/follow_stop_node", "max_decel"): 0.8, ("/follow_stop_node", "recheck_max_s"): 1.0,
                   ("/zlac_drive_bridge", "speed_mode"): "mps", ("/zlac_drive_bridge", "max_speed_mps"): 0.5,
                   ("/zlac_drive_bridge", "wheel_radius_m"): 0.085, ("/zlac_drive_bridge", "turn_dir"): 1.0,
                   ("/zlac_drive_bridge", "forward_dir"): -1.0}
        expected = dict(running)

        def get(changes):
            vals = {**running, **changes}
            return lambda node, name: vals.get((node, name))
        self.assertEqual(P.check_motion_params(get({}), expected)[0], "PASS")
        self.assertEqual(P.check_motion_params(get({("/zlac_drive_bridge", "max_speed_mps"): 1.4}), expected)[0], "FAIL")
        self.assertEqual(P.check_motion_params(get({("/follow_stop_node", "spin_clear_radius_m"): 0.3}), expected)[0],
                         "FAIL")
        self.assertEqual(P.check_motion_params(get({("/zlac_drive_bridge", "speed_mode"): None}), expected)[0], "FAIL")
        self.assertEqual(P.check_motion_params(get({("/zlac_drive_bridge", "forward_dir"): 1.0}), expected)[0], "FAIL")
        self.assertEqual(P.check_motion_params(get({("/zlac_drive_bridge", "wheel_radius_m"): 0.0757}), expected)[0], "FAIL")
        self.assertEqual(P.check_motion_params(get({("/follow_stop_node", "max_decel"): float("nan")}), expected)[0],
                         "FAIL")

    def test_lidar_frame_params(self):
        running = {key: (-1.0 if key[1].endswith("sign") else 0.0) for key in P.LIDAR_FRAME_PARAMS}

        def get(changes):
            vals = {**running, **changes}
            return lambda node, name: vals.get((node, name))

        self.assertEqual(P.check_lidar_frame_params(get({}), 0.0, -1.0)[0], "PASS")
        for key in P.LIDAR_FRAME_PARAMS:
            wrong = 1.0 if key[1].endswith("sign") else 180.0
            self.assertEqual(P.check_lidar_frame_params(get({key: wrong}), 0.0, -1.0)[0], "FAIL")
            self.assertEqual(P.check_lidar_frame_params(get({key: None}), 0.0, -1.0)[0], "FAIL")
        self.assertEqual(P.check_lidar_frame_params(get({}), float("nan"), -1.0)[0], "FAIL")
        self.assertEqual(P.check_lidar_frame_params(get({}), 0.0, 0.0)[0], "FAIL")

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
        procs = {p["name"]: p["cmd"] for p in mod.actions(mod.DEFAULTS)}
        for name in ("follow_stop", "sync_fusion"):
            self.assertIn("lidar_angle_offset_deg:=0.0", procs[name])
            self.assertIn("lidar_angle_sign:=-1.0", procs[name])
        self.assertIn("angle_offset_deg:=0.0", procs["lidar_sectorizer"])
        self.assertIn("angle_sign:=-1.0", procs["lidar_sectorizer"])
        self.assertIn("forward_dir:=1.0", procs["zlac_bridge"])
        self.assertIn("forward_dir:=-1.0", {p["name"]: p["cmd"] for p in
                                            mod.actions({**mod.DEFAULTS, "forward_dir": "-1.0"})}["zlac_bridge"])

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
