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
