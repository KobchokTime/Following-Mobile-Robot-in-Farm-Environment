"""The measured robot mount has raw 0 ahead and raw negative bearings to the left."""

import math
import unittest

from test_follow_stop_early_turn import _LaserScan, _load_follow_stop, _load_sectorizer
from test_walk_up import make_node


def mounted_scan(ranges):
    msg = _LaserScan(ranges)
    msg.angle_min = -math.pi / 6
    msg.angle_max = math.pi / 6
    msg.angle_increment = math.pi / (3 * (len(ranges) - 1))
    return msg


class LidarFrameCalibrationTest(unittest.TestCase):
    def test_controller_places_raw_left_post_on_robot_left(self):
        node = _load_follow_stop().FollowStopNode()
        node.lidar_offset = 0.0
        node.lidar_sign = -1.0
        node.cb_scan(mounted_scan([1.0, 2.0, 3.0]))
        self.assertAlmostEqual(node.scan_xy[0][0], math.cos(math.pi / 6))
        self.assertAlmostEqual(node.scan_xy[0][1], 0.5)
        self.assertAlmostEqual(node.scan_xy[1][0], 2.0)
        self.assertAlmostEqual(node.scan_xy[1][1], 0.0)
        self.assertAlmostEqual(node.scan_xy[2][1], -1.5)

    def test_controller_stops_for_raw_front_post(self):
        node = _load_follow_stop().FollowStopNode()
        node.lidar_offset = 0.0
        node.lidar_sign = -1.0
        node.cb_scan(mounted_scan([math.inf, 0.4, math.inf]))
        self.assertEqual(node.obstacle_limited(0.5, None), 0.0)

    def test_fusion_agrees_with_controller_bearings(self):
        _, node = make_node(lidar_angle_offset_deg=0.0, lidar_angle_sign=-1.0)
        node.cb_scan(mounted_scan([1.0, 2.0, 3.0]))
        self.assertAlmostEqual(node.scan_points[0][0], math.pi / 6)
        self.assertAlmostEqual(node.scan_points[1][0], 0.0)
        self.assertAlmostEqual(node.scan_points[2][0], -math.pi / 6)
        self.assertEqual([r for _, r in node.scan_points], [1.0, 2.0, 3.0])

    def test_sectorizer_keeps_left_and_right_in_camera_order(self):
        node = _load_sectorizer().LidarSectorizer()
        node.angle_offset = 0.0
        node.angle_sign = -1.0
        node.cb(mounted_scan([1.0, math.inf, math.inf, 3.0, math.inf, math.inf, 2.0]))
        distances = node.pub_dist.messages[-1].data
        self.assertAlmostEqual(distances[0], 2.0)  # robot right: raw positive angle
        self.assertAlmostEqual(distances[4], 3.0)  # robot front
        self.assertAlmostEqual(distances[-1], 1.0)  # robot left: raw negative angle


if __name__ == "__main__":
    unittest.main()
