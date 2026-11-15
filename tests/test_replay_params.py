"""Replay must route field parameters to the correct ROS nodes, without starting ROS."""

import unittest
from pathlib import Path

from sim.replay.replay_bag import parse_node_params
from sim.twin.pipeline import Processes


class ReplayParamsTest(unittest.TestCase):
    def test_field_parameters_reach_only_the_named_node(self):
        params = parse_node_params([
            'lidar_sectorizer.lidar_angle_offset_deg=6.2',
            'sync_fusion.lidar_angle_offset_deg=6.2',
            'sync_fusion.lidar_angle_sign=-1.0',
            'follow_stop.target_distance=1.0',
            'follow_stop.front_band_radius=2',
            'follow_stop.wide_front_radius=2',
        ])
        calls = {}
        procs = Processes(Path('.'), {})
        procs.start = lambda name, cmd, _cwd: calls.setdefault(name, cmd)
        procs.start_robot_nodes(node_params=params)
        self.assertIn('target_distance:=1.0', calls['follow_stop'])
        self.assertIn('lidar_angle_sign:=-1.0', calls['sync_fusion'])
        self.assertNotIn('target_distance:=1.0', calls['sync_fusion'])
        self.assertNotIn('lidar_angle_sign:=-1.0', calls['follow_stop'])
        self.assertNotIn('--ros-args', calls['fusion_prob'])

    def test_unknown_node_and_malformed_override_fail(self):
        for item in ('unknown.target_distance=1.0', 'follow_stop.no-value',
                     'follow_stop.x=', 'follow_stop.bad-name=1'):
            with self.subTest(item=item), self.assertRaises(ValueError):
                parse_node_params([item])


if __name__ == '__main__':
    unittest.main()
