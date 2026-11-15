"""T22: a LiDAR-only edge track must stop when an in-image person disagrees."""

import importlib.util
import math
import sys
import types
import unittest
from pathlib import Path

from test_obstacle_stop import M as FOLLOW, person as obstacle_person, scan as obstacle_scan
from test_follow_stop_early_turn import _Float32MultiArray
import test_walk_up
from test_walk_up import make_node, person, scan


ROOT = Path(__file__).resolve().parents[1]
PROB_NODE = ROOT / "ros2_yolo_ws" / "scripts" / "Image" / "fusion_prob_node.py"


class EdgeConflictTest(unittest.TestCase):
    def test_fast_step_past_static_cluster_stops_instead_of_turning_away(self):
        helper = test_walk_up.LidarAssistTest()
        m, node = make_node()
        t = helper.lock(node, target=(0.9, 0.0))
        node.scan_points = scan(person(0.9, 0.33))
        self.assertTrue(helper.box(node, t, 0.9, 0.33))

        # The camera loses the target after a fast side step. A static cluster on the left
        # carries the LiDAR-only gate to the edge, as happened in both field bags.
        cluster = (0.9, 0.75)
        for k in range(1, 11):
            helper.scan_at(node, t + 0.1 * k, [cluster])
        self.assertTrue(any(p[0] == 0 for p in node.published))

        # A real in-image box is now near the centre/right. Its identity is uncertain;
        # choosing the LiDAR edge or switching to this box would both be unsafe.
        before = len(node.published)
        node.buf_lidar.clear()
        node.buf_lidar.append((t + 1.1, [1.0]))
        node.try_sync_from_yolo(t + 1.1, 337, 240, 4)  # -1.9 deg, field run at t=24 s
        self.assertEqual(len(node.published), before + 1)
        self.assertEqual(node.published[-1][:4], [-1.0, -1.0, -1.0, -1.0])
        self.assertTrue(node.camera_conflict_latched)
        helper.scan_at(node, t + 1.2, [cluster])
        node.try_sync_from_yolo(t + 1.2, 500, 240, 7)  # person on the right
        self.assertEqual(len(node.published), before + 1)

    def test_same_side_camera_box_does_not_trip_the_edge_guard(self):
        m, node = make_node()
        node.lidar_driven_bearing = math.radians(35.0)
        self.assertFalse(m.camera_disagrees_with_lidar_edge(
            math.radians(25.0), node.lidar_driven_bearing, node.edge_rad, node.camera_hfov_deg))
        self.assertTrue(m.camera_disagrees_with_lidar_edge(
            math.radians(-30.5), node.lidar_driven_bearing, node.edge_rad, node.camera_hfov_deg))

    def test_controller_stops_immediately_instead_of_holding_wrong_turn(self):
        node = FOLLOW.FollowStopNode()
        node.cb_scan(obstacle_scan(obstacle_person(1.8, 0.0)))
        msg = _Float32MultiArray()
        msg.data = [320.0, 240.0, 0.8, 4.0, 0.9, 0.9, 0.9, 10.0]
        node.cb_fused(msg)
        msg.data = [0.0, 240.0, 1.6, 0.0, 0.9, 0.9, 0.9, 10.0]
        node.cb_fused(msg)
        self.assertNotEqual(node.pub.messages[-1].angular.z, 0.0)
        node.trailing = node.trail_since_msg = True
        msg.data = [-1.0, -1.0, -1.0, -1.0, 0.0, 0.0, 0.0, 0.0]
        node.cb_fused(msg)
        self.assertEqual((node.pub.messages[-1].linear.x, node.pub.messages[-1].angular.z), (0.0, 0.0))
        self.assertFalse(node.trailing)
        self.assertFalse(node.trail_since_msg)


class ProbabilityStopTest(unittest.TestCase):
    def test_conflict_bypasses_confidence_smoothing(self):
        class FakeNode:
            def __init__(self, _name):
                self.published = []

            def declare_parameter(self, _name, _default):
                pass

            def get_parameter(self, name):
                return types.SimpleNamespace(value={
                    'dist_max': 2.0, 'camera_weight': 0.7, 'lidar_weight': 0.3,
                    'alpha_base': 0.7, 'dt_ref': 0.33, 'center_penalty': 0.0,
                }[name])

            def create_subscription(self, *_args):
                pass

            def create_publisher(self, *_args):
                return types.SimpleNamespace(publish=lambda msg: self.published.append(msg.data))

            def get_logger(self):
                return types.SimpleNamespace(info=lambda _msg: None)

        class Array:
            def __init__(self):
                self.data = []

        saved = {name: sys.modules.get(name) for name in
                 ('rclpy', 'rclpy.node', 'std_msgs', 'std_msgs.msg')}
        mods = {name: types.ModuleType(name) for name in saved}
        mods['rclpy.node'].Node = FakeNode
        mods['std_msgs.msg'].Float32MultiArray = Array
        sys.modules.update(mods)
        try:
            spec = importlib.util.spec_from_file_location('t22_fusion_prob', PROB_NODE)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            for name, previous in saved.items():
                if previous is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = previous
        node = module.FusionProbNode()
        node.prev_p_fused = 0.99
        node.lidar_buffer = [(0.0, 0.99)]
        msg = Array()
        msg.data = [-1.0, -1.0, -1.0, -1.0, 0.0, 0.0]
        node.cb_sync(msg)
        self.assertEqual(node.published[-1], [-1.0, -1.0, -1.0, -1.0, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual(node.prev_p_fused, 0.0)
        self.assertEqual(node.lidar_buffer, [])


if __name__ == '__main__':
    unittest.main()
