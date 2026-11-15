"""ROS argument construction for bag replay, without ROS installed."""

import unittest

from sim.replay.replay_bag import node_ros_params


class ReplayParameterTest(unittest.TestCase):
    def test_repeatable_node_parameters_become_ros_overrides(self):
        self.assertEqual(node_ros_params([
            "sync_fusion:lidar_angle_offset_deg:=6.2",
            "sync_fusion:lidar_angle_sign:=-1.0",
            "follow_stop:target_distance:=1.0",
        ]), {
            "sync_fusion": ["-p", "lidar_angle_offset_deg:=6.2", "-p", "lidar_angle_sign:=-1.0"],
            "follow_stop": ["-p", "target_distance:=1.0"],
        })

    def test_bare_ros_parameter_is_broadcast(self):
        self.assertEqual(node_ros_params(["steer_mode:=sector"]), {"*": ["-p", "steer_mode:=sector"]})


if __name__ == "__main__":
    unittest.main()
