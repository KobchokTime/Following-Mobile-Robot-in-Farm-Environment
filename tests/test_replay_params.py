"""Replay must route field parameters to the correct ROS nodes, without starting ROS."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sim.replay.replay_bag as replay_mod
from sim.replay.replay_bag import parse_node_params
from sim.twin.pipeline import Processes


class ReplayParamsTest(unittest.TestCase):
    def test_field_parameters_reach_only_the_named_node(self):
        params = parse_node_params([
            'lidar_sectorizer.angle_offset_deg=6.2',
            'lidar_sectorizer.angle_sign=-1.0',
            'sync_fusion.lidar_angle_offset_deg=6.2',
            'sync_fusion.lidar_angle_sign=-1.0',
            'follow_stop.target_distance=1.0',
            'follow_stop.front_band_radius=2',
            'follow_stop.wide_front_radius=2',
            'follow_stop.lidar_angle_offset_deg=6.2',
            'follow_stop.lidar_angle_sign=-1.0',
        ])
        calls = {}
        procs = Processes(Path('.'), {})
        procs.start = lambda name, cmd, _cwd: calls.setdefault(name, cmd)
        procs.start_robot_nodes(node_params=params)
        self.assertIn('target_distance:=1.0', calls['follow_stop'])
        self.assertIn('lidar_angle_sign:=-1.0', calls['sync_fusion'])
        self.assertIn('angle_offset_deg:=6.2', calls['lidar_sectorizer'])
        self.assertIn('angle_sign:=-1.0', calls['lidar_sectorizer'])
        self.assertNotIn('lidar_angle_offset_deg:=6.2', calls['lidar_sectorizer'])
        self.assertNotIn('target_distance:=1.0', calls['sync_fusion'])
        self.assertIn('lidar_angle_sign:=-1.0', calls['follow_stop'])
        self.assertNotIn('lidar_angle_sign:=-1.0', calls['fusion_prob'])
        self.assertNotIn('--ros-args', calls['fusion_prob'])

    def test_unknown_node_and_malformed_override_fail(self):
        for item in ('unknown.target_distance=1.0', 'follow_stop.no-value',
                     'follow_stop.x=', 'follow_stop.bad-name=1'):
            with self.subTest(item=item), self.assertRaises(ValueError):
                parse_node_params([item])

    def test_limited_replay_flushes_after_interrupt_without_starting_bridge(self):
        class FakePlay:
            pid = 123

            def __init__(self):
                self.waits = []

            def wait(self, timeout=None):
                self.waits.append(timeout)
                if len(self.waits) == 1:
                    raise subprocess.TimeoutExpired('ros2 bag play', timeout)
                return 0

        class FakeProcesses:
            instance = None

            def __init__(self, _out, env):
                self.commands = {}
                self.play = FakePlay()
                self.stopped = False
                self.env = env
                FakeProcesses.instance = self

            def start_robot_nodes(self, node_params=None):
                self.node_params = node_params

            def start(self, name, command, _cwd):
                self.commands[name] = command
                return self.play if name == 'bag_play' else None

            def stop(self):
                self.stopped = True

        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(replay_mod, 'Processes', FakeProcesses), \
             mock.patch.object(replay_mod, 'isolated_env', return_value={'ROS_DOMAIN_ID': '188'}), \
             mock.patch.object(replay_mod, 'read_cmd_vel', return_value=[]), \
             mock.patch.object(replay_mod.time, 'sleep'), \
             mock.patch.object(replay_mod.os, 'killpg', create=True) as interrupt:
            replay_mod.replay(Path('bag'), Path(directory), replay_mod.DEFAULT_INPUTS, 1.0,
                              start_offset=580.0, max_wall_s=40.0, domain_id=187)
            procs = FakeProcesses.instance
            self.assertEqual(procs.env['ROS_DOMAIN_ID'], '187')
            self.assertIn('--start-offset', procs.commands['bag_play'])
            self.assertIn('580.0', procs.commands['bag_play'])
            self.assertIn('/yolo_frame', procs.commands['bag_record'])
            self.assertIn('/yolo_frame', procs.commands['bag_play'])
            self.assertNotIn('zlac_drive_bridge', procs.commands)
            self.assertEqual(procs.play.waits, [40.0, 10])
            interrupt.assert_called_once_with(123, replay_mod.signal.SIGINT)
            self.assertTrue(procs.stopped)


if __name__ == '__main__':
    unittest.main()
