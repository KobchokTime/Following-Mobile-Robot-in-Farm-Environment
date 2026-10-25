"""Offline tests for the twin world model (sim/twin). No ROS needed."""

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sim.twin.scenarios import SCENARIOS, build  # noqa: E402
from sim.twin.score import score  # noqa: E402
from sim.twin.world import PERSON_RADIUS_M, Person, Realism, World  # noqa: E402


def world_with(*people, **robot):
    w = World(people=list(people), seed=1)
    w.sensors.lidar_noise_m = 0.0
    w.sensors.centroid_noise_px = 0.0
    for k, v in robot.items():
        setattr(w.robot, k, v)
    return w


class BridgeModelTest(unittest.TestCase):
    def test_current_bridge_ignores_angular_and_clamps(self):
        w = world_with(Person("t", [(0, 2, 0)], True))
        w.command(5.0, 1.0)
        w.step(0.1)
        self.assertEqual((w.rpm_left, w.rpm_right), (40.0, 40.0))
        self.assertEqual(w.w, 0.0)

    def test_command_times_out_after_one_second(self):
        w = world_with(Person("t", [(0, 2, 0)], True))
        w.command(0.5, 0.0)
        for _ in range(9):
            w.step(0.1)
        self.assertGreater(w.v, 0.0)
        for _ in range(3):
            w.step(0.1)
        self.assertEqual(w.v, 0.0)

    def test_diff_drive_turns_left_for_positive_angular(self):
        w = world_with(Person("t", [(0, 2, 0)], True), bridge_mode="diff_drive")
        for _ in range(10):
            w.command(0.0, 0.5)
            w.step(0.1)
        self.assertGreater(w.yaw, 0.3)


class SensorModelTest(unittest.TestCase):
    def test_lidar_sees_person_ahead_through_mount_yaw(self):
        w = world_with(Person("t", [(0, 2.0, 0.0)], True))
        ranges = w.scan()
        # Robot-forward is lidar angle -pi + pi = 0 -> middle ray in a mount-yaw=pi frame is behind,
        # so the hit must be at lidar angle -pi (index 0).
        self.assertAlmostEqual(ranges[0], 2.0 - PERSON_RADIUS_M, places=2)
        self.assertTrue(math.isinf(ranges[len(ranges) // 2]))

    def test_camera_sector_left_person_has_small_cx(self):
        w = world_with(Person("t", [(0, 3.0, 1.0)], True))
        (det,) = w.detections()
        self.assertLess(det.cx, 320)
        self.assertLess(det.sector_id, 4)

    def test_occluded_person_is_not_detected(self):
        w = world_with(Person("t", [(0, 4.0, 0.0)], True), Person("d", [(0, 2.0, 0.0)]))
        self.assertEqual([d.person for d in w.detections()], ["d"])

    def test_blackout_hides_everyone(self):
        w = world_with(Person("t", [(0, 2.0, 0.0)], True))
        w.blackouts = [(0.0, 1.0)]
        self.assertEqual(w.detections(), [])


class ScenarioAndScoreTest(unittest.TestCase):
    def test_every_scenario_starts_inside_controller_init_window(self):
        for name in SCENARIOS:
            w = build(name)
            gap = w.state()["people"]["target"]["range_m"] - PERSON_RADIUS_M
            self.assertTrue(0.5 <= gap <= 1.0, name)

    def test_score_reports_stop_latency_after_blackout(self):
        w = build("target_loss")
        rows = []
        while w.t < 16.0:
            if not w.state()["blackout"] and w.t > 3.0:
                w.command(0.5, 0.0)
            w.step(0.1)
            rows.append(w.state())
        result = score(rows)
        self.assertAlmostEqual(result["stop_latency_s"], 1.0, delta=0.15)
        self.assertFalse(result["contact"])


if __name__ == "__main__":
    unittest.main()


class RealismTest(unittest.TestCase):
    def test_off_by_default_and_bit_identical(self):
        a, b = build("straight", seed=3), build("straight", seed=3)
        self.assertIsNone(a.realism)
        for _ in range(20):
            for w in (a, b):
                w.command(0.3, 0.1)
                w.step(0.1)
        self.assertEqual(a.scan(), b.scan())
        self.assertEqual(a.detections(), b.detections())

    def test_detections_arrive_late(self):
        w = world_with(Person("t", [(0, 2.0, 0.0)], True))
        w.realism = Realism(detect_dropout=0.0, false_positive_rate=0.0, detect_latency_s=0.15)
        self.assertEqual(w.detections(), [])
        w.step(0.1)
        self.assertEqual(w.detections(), [])
        w.step(0.1)
        self.assertEqual([d.person for d in w.detections()], ["t"])

    def test_dropout_and_false_positives(self):
        w = world_with(Person("t", [(0, 2.0, 0.0)], True))
        w.realism = Realism(detect_dropout=0.5, false_positive_rate=0.5, detect_latency_s=0.0)
        frames = [w.detections() for _ in range(400)]
        seen = sum(any(d.person == "t" for d in f) for f in frames) / len(frames)
        fake = sum(any(d.person == "false_positive" for d in f) for f in frames) / len(frames)
        self.assertAlmostEqual(seen, 0.5, delta=0.1)
        self.assertAlmostEqual(fake, 0.5, delta=0.1)

    def test_clutter_shows_in_scan(self):
        w = world_with()
        clean = w.scan()
        w.realism = Realism(lidar_noise_m=0.0, lidar_ray_dropout=0.0, clutter=((1.0, 0.0, 0.1),))
        ranges = w.scan()
        self.assertTrue(math.isinf(clean[0]))
        self.assertAlmostEqual(ranges[0], 0.9, places=2)
