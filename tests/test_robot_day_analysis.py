"""Offline tests for tools/robot_day/analyze.py (no ROS, no bags) and the /yolo_frame layout."""

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "robot_day"))

import analyze as A  # noqa: E402


def frame(stamp, boxes, w=640, h=480):
    data = [int(stamp), int(round((stamp % 1) * 1e9)), w, h, len(boxes)]
    for b in boxes:
        data.extend(b)
    return A.parse_frame(data)


class LabelTest(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(A.parse_label("e1_b-20_d2.0"), {"exp": "e1", "bearing_deg": -20.0, "distance_m": 2.0})
        self.assertEqual(A.parse_label("e3_d0.5_back"), {"exp": "e3", "distance_m": 0.5, "facing": "back"})
        self.assertEqual(A.parse_label("e4_overlap_same_shade"),
                         {"exp": "e4", "overlap": True, "clothes": "same", "light": "shade"})
        self.assertEqual(A.parse_label("follow_straight_1")["exp"], "other")


class GeometryTest(unittest.TestCase):
    def test_camera_bearing_matches_the_fusion_node(self):
        self.assertAlmostEqual(A.camera_bearing_rad(320, 640), 0.0)
        self.assertAlmostEqual(math.degrees(A.camera_bearing_rad(0, 640)), 35.0, places=6)

    def test_scan_points_undo_the_backwards_mount(self):
        # a return straight ahead of the robot is at scan angle -pi with the 180 deg mount
        pts = A.scan_points(-math.pi, math.pi / 2, [2.0, math.inf, 3.0, 0.0])
        self.assertEqual(len(pts), 2)
        self.assertAlmostEqual(pts[0][0], 0.0)
        self.assertAlmostEqual(abs(pts[1][0]), math.pi)

    def test_nearest_return_in_window(self):
        pts = [(math.radians(-1), 1.8), (math.radians(4), 1.5), (math.radians(30), 0.6)]
        self.assertEqual(A.nearest_return(pts, 0.0, math.radians(10))[1], 1.5)
        self.assertIsNone(A.nearest_return(pts, math.radians(-60), math.radians(5)))


class ExperimentTest(unittest.TestCase):
    def test_e1_perfect_alignment(self):
        truth = {"bearing_deg": 0.0, "distance_m": 2.0}
        pts = [(0.0, 1.8)]
        r = A.e1_stats(truth, [(0.0, 320), (0.1, 320)], [(0.0, pts), (0.1, pts)])
        self.assertEqual(r["camera_bearing_err_deg"]["mae"], 0.0)
        self.assertEqual(r["lidar_range_err_m"]["bias"], 0.0)
        self.assertEqual(r["lidar_hit_share"], 1.0)

    def test_e1_offset_shows_as_bias(self):
        truth = {"bearing_deg": 10.0, "distance_m": 2.0}
        r = A.e1_stats(truth, [(0.0, 320)], [(0.0, [(0.0, 1.8)])])
        self.assertAlmostEqual(r["camera_bearing_err_deg"]["bias"], -10.0)

    def test_e2_latency(self):
        frames = [(10.05, frame(10.0, [(0, 0, 10, 10, 900, 128, 128)])), (10.15, frame(10.1, []))]
        r = A.e2_latency(frames, [10.08, 10.2])
        self.assertAlmostEqual(r["capture_to_detection_ms"]["median"], 50.0, places=0)
        self.assertAlmostEqual(r["detection_to_cmd_vel_ms"]["median"], 30.0, places=0)

    def test_e2_flags_unusable_capture_stamps(self):
        box = [(0, 0, 10, 10, 900, 128, 128)]
        frames = [(10.05, frame(10.0, box)), (10.15, frame(0.0, box)), (10.25, frame(10.4, box))]
        r = A.e2_latency(frames, [10.3])
        self.assertEqual(r["bad_stamps"], 2)  # a zero stamp, and one later than its receive time
        self.assertAlmostEqual(r["capture_to_detection_ms"]["median"], 50.0, places=0)

    def test_e3_rate_and_clipping(self):
        clipped, whole = (100, 0, 200, 479, 800, 128, 128), (100, 50, 200, 400, 900, 128, 128)
        frames = [(0.0, frame(0.0, [clipped])), (0.5, frame(0.5, [])), (1.0, frame(1.0, [whole]))]
        r = A.e3_stats({"distance_m": 0.5}, frames)
        self.assertEqual(r["detection_rate"], 0.667)
        self.assertEqual(r["clipped_share"], 0.5)
        self.assertEqual(r["fps"], 2.0)

    def test_e4_separates_red_and_blue_but_not_the_same_colour(self):
        red, blue = (110, 165), (160, 110)
        frames = [(i, frame(i, [(10, 0, 100, 400, 900, *red), (300, 0, 400, 400, 900, *blue)])) for i in range(5)]
        r = A.e4_stats({}, frames)
        self.assertEqual(r["nearest_mean_accuracy"], 1.0)
        self.assertGreater(r["between_person_distance"], 70)
        same = [(i, frame(i, [(10, 0, 100, 400, 900, 110 + i % 2, 165), (300, 0, 400, 400, 900, 111 - i % 2, 165)]))
                for i in range(6)]
        self.assertLess(A.e4_stats({}, same)["nearest_mean_accuracy"], 0.75)

    def test_overlap_shift(self):
        base = {"mean_a": [110, 165], "mean_b": [160, 110]}
        over = {"mean_a": [113, 161], "mean_b": [160, 110]}
        self.assertEqual(A.e4_overlap_shift(base, over), {"shift_a": 5.0, "shift_b": 0.0})


if __name__ == "__main__":
    unittest.main()
