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
    names = ["rclpy", "rclpy.node", "rclpy.qos", "std_msgs", "std_msgs.msg", "sensor_msgs", "sensor_msgs.msg",
             "geometry_msgs", "geometry_msgs.msg"]
    stubs = {n: types.ModuleType(n) for n in names}
    stubs["rclpy.node"].Node = object
    for k in ("QoSProfile", "QoSReliabilityPolicy", "QoSHistoryPolicy", "QoSDurabilityPolicy"):
        setattr(stubs["rclpy.qos"], k, object)
    stubs["std_msgs.msg"].Int32MultiArray = object
    stubs["std_msgs.msg"].Float32MultiArray = object
    stubs["sensor_msgs.msg"].LaserScan = object
    stubs["geometry_msgs.msg"].Twist = object
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
        cls.scan_is_fresh = staticmethod(module.scan_is_fresh)
        cls.StaticMap = module.StaticMap

    def test_old_or_missing_scans_are_not_used(self):
        self.assertTrue(self.scan_is_fresh(10.0, 9.9, 0.3))
        self.assertFalse(self.scan_is_fresh(10.0, 6.0, 0.3))   # Codex's 4 s old scan
        self.assertFalse(self.scan_is_fresh(10.0, None, 0.3))  # never received
        self.assertFalse(self.scan_is_fresh(10.0, 10.5, 0.3))  # clock went backwards

    @staticmethod
    def _blob(centre_deg, rng, width_m, step_deg=0.5):
        """Returns of a round object of a given width at (bearing, range)."""
        half = math.degrees(width_m / 2.0 / rng)
        n = max(1, int(2 * half / step_deg))
        return [(D(centre_deg - half + i * step_deg), rng) for i in range(n + 1)]

    def test_lidar_track_finds_the_target_beside_the_image(self):
        pts = self._blob(-58, 0.85, 0.4) + self._blob(10, 3.0, 0.4) + self._blob(170, 0.5, 0.4)
        found = self.lidar_track(pts, D(-50), 0.8, D(25), 0.5)
        self.assertAlmostEqual(found[1], 0.85)
        self.assertAlmostEqual(math.degrees(found[0]), -58, delta=1.0)
        self.assertIsNone(self.lidar_track(pts, D(40), 0.8, D(25), 0.5))   # nothing there
        self.assertIsNone(self.lidar_track(pts, D(-50), 2.0, D(25), 0.5))  # wrong range

    def test_lidar_track_ignores_a_row_seen_at_an_angle(self):
        # integration's reproducer: a row 1 m to the side, from 1.6 m to 3.0 m ahead
        pts = []
        x = 1.6
        while x <= 3.0:
            pts.append((math.atan2(1.0, x), math.hypot(x, 1.0)))
            x += 0.02
        self.assertIsNone(self.lidar_track(pts, 0.5, 2.0, D(25), 0.5))

    def test_lidar_track_ignores_posts_and_rows(self):
        # one range per bearing, as a real scan: person, then a post, then a crop row
        person = self._blob(-62, 0.9, 0.4)            # about -75 to -49 deg
        post = self._blob(-45, 0.75, 0.05)            # thin post near the prediction
        row = [(D(a / 2.0), 1.1) for a in range(-80, 21)]  # -40 to +10 deg at 1.1 m: about 0.96 m wide
        self.assertIsNone(self.lidar_track(post + row, D(-50), 0.8, D(25), 0.5))
        found = self.lidar_track(post + row + person, D(-50), 0.8, D(25), 0.5)
        self.assertAlmostEqual(math.degrees(found[0]), -62, delta=1.0)

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

    def test_two_boxes_in_one_frame_do_not_lose_the_target(self):
        g = self.Gate()
        for i in range(5):
            self.assertTrue(g.accept(0.1 * i, 0.0, 0.8))
        self.assertTrue(g.accept(0.5, 0.0, 0.8))
        g.accept(0.501, D(4), 0.8)  # a second, offset box on the same person, 1 ms later
        for i in range(6, 30):
            self.assertTrue(g.accept(0.1 * i, 0.0, 0.8), i)

    def test_rate_is_estimated_at_high_frame_rates(self):
        for fps in (10, 30, 60):
            g = self.Gate()
            for i in range(3 * fps):
                g.accept(i / fps, 0.3 * i / fps, 0.8)
            self.assertAlmostEqual(g.bearing_rate, 0.3, delta=0.02, msg=fps)

    def test_long_loss_returns_to_the_lock_on_window(self):
        g = self.Gate()
        g.accept(0.0, 0.0, 0.8)
        g.accept(0.1, 0.0, 0.8)
        self.assertFalse(g.accept(7.0, D(20), 3.5))  # a false box 3.5 m away after 7 s unseen
        self.assertFalse(g.locked)
        self.assertTrue(g.accept(9.0, D(2), 0.8))     # the person walks back to the robot

    def test_static_map_flags_a_post_but_not_a_walking_person(self):
        m = self.StaticMap(static_s=2.0, radius_m=0.3)
        t = 0.0
        for i in range(31):  # 3 s at 10 Hz; the robot drives forward at 0.5 m/s
            t = 0.1 * i
            if i:
                m.move(0.5, 0.0, 0.1)
            x = m.pose[0]
            post = (math.atan2(1.0, 3.0 - x), math.hypot(3.0 - x, 1.0))        # still, at (3, 1)
            px, py = 2.0 + 1.0 * t, -0.5                                         # walking at 1 m/s
            person = (math.atan2(py, px - x), math.hypot(px - x, py))
            m.update(t, [post, person])
        self.assertTrue(m.is_static(*post))
        self.assertFalse(m.is_static(*person))

    def test_lidar_track_skips_excluded_clusters(self):
        pts = [(D(40 + i * 0.5), 1.2) for i in range(-12, 13)]  # one person-sized cluster at 40 deg
        self.assertIsNotNone(self.lidar_track(pts, D(40), 1.2, D(25), 0.5))
        self.assertIsNone(self.lidar_track(pts, D(40), 1.2, D(25), 0.5, exclude=lambda b, r: True))

    def test_old_three_value_messages_work(self):
        g = self.Gate()
        self.assertTrue(g.accept(0.0, 0.0, 0.8, None))
        self.assertTrue(g.accept(0.1, 0.0, 0.82, None))
        self.assertTrue(g.accept(0.2, 0.0, 0.84, RED))  # colour learned once it appears


if __name__ == "__main__":
    unittest.main()
