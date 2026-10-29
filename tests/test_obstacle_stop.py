"""Obstacle stop in follow_stop_node: anything in the LiDAR corridor, other than the target, stops the robot."""

import math
import unittest

from test_follow_stop_early_turn import _Float32MultiArray, _LaserScan, _load_follow_stop

M = _load_follow_stop()


def scan(points_robot, rays=720):
    """A LaserScan in the laser frame (turned 180 deg, as on the robot) with returns at robot-frame (x, y)."""
    ranges = [math.inf] * rays
    inc = 2.0 * math.pi / rays
    for x, y in points_robot:
        a = math.atan2(y, x) - math.pi  # laser angle = robot angle - 180 deg (lidar_angle_offset_deg 180)
        i = int(round((a + math.pi) / inc)) % rays
        ranges[i] = min(ranges[i], math.hypot(x, y))
    msg = _LaserScan(ranges)
    msg.angle_increment = inc
    return msg


def person(x, y, r=0.2, n=9):
    """Returns off the front of a round person at (x, y), as the LiDAR sees them."""
    out = []
    for k in range(-n, n + 1):
        b = math.atan2(y, x) + k * (r / math.hypot(x, y)) / n
        out.append(((math.hypot(x, y) - r) * math.cos(b), (math.hypot(x, y) - r) * math.sin(b)))
    return out


class CorridorTest(unittest.TestCase):
    def test_only_returns_in_the_corridor_ahead_count(self):
        pts = [(1.0, 0.1), (0.8, 0.6), (-0.5, 0.0)]
        self.assertAlmostEqual(M.corridor_clearance(pts, 0.35), 1.0)
        self.assertAlmostEqual(M.corridor_clearance(pts, 0.35, direction=-1.0), 0.5)

    def test_the_target_does_not_count(self):
        pts = [(1.0, 0.0), (1.05, 0.1)]
        self.assertEqual(M.corridor_clearance(pts, 0.35, exclude=(1.0, 0.0), exclude_r=0.45), math.inf)

    def test_the_corridor_bends_with_the_turn(self):
        on_arc = (math.sin(1.2), 1.0 - math.cos(1.2))  # 1.2 m along a 1 m radius left turn
        self.assertAlmostEqual(M.corridor_clearance([on_arc], 0.3, curvature=1.0), 1.2)
        self.assertEqual(M.corridor_clearance([(1.0, 0.0)], 0.3, curvature=1.0), math.inf)  # the turn misses it
        self.assertEqual(M.corridor_clearance([on_arc], 0.3), math.inf)  # off the straight corridor

    def test_speed_cap_stops_short_of_the_obstacle(self):
        self.assertEqual(M.obstacle_speed_cap(0.45, 0.45, 0.8, 0.2, 0.0), 0.0)
        self.assertAlmostEqual(M.obstacle_speed_cap(1.45, 0.45, 0.8, 0.0, 0.0), math.sqrt(1.6))
        self.assertLess(M.obstacle_speed_cap(1.45, 0.45, 0.8, 0.2, 1.0), math.sqrt(1.6))


class NodeTest(unittest.TestCase):
    def drive(self, scan_points, **params):
        node = M.FollowStopNode()
        node.obstacle_avoid = False  # the stop alone; AvoidTest covers the way round
        for k, v in params.items():
            setattr(node, k, v)
        if scan_points is not None:
            node.cb_scan(scan(scan_points))
        msg = _Float32MultiArray()
        msg.data = [320.0, 240.0, 0.8, 4.0, 0.9, 0.9, 0.9, 10.0]  # lock at 0.8 m
        node.cb_fused(msg)
        msg.data = [320.0, 240.0, 1.6, 4.0, 0.9, 0.9, 0.9, 10.0]  # the target 1.6 m ahead: drive on
        node.cb_fused(msg)
        return node.pub.messages[-1].linear.x

    def test_the_target_alone_lets_the_robot_drive(self):
        self.assertGreater(self.drive(person(1.8, 0.0)), 0.3)

    def test_something_close_in_the_path_stops_the_robot(self):
        self.assertEqual(self.drive(person(1.8, 0.0) + person(0.5, 0.15, r=0.06)), 0.0)  # a post 0.44 m ahead

    def test_something_farther_in_the_path_slows_the_robot(self):
        free = self.drive(person(1.8, 0.0))
        post = self.drive(person(1.8, 0.0) + person(0.85, 0.15, r=0.06))  # a post 0.8 m ahead
        self.assertGreater(post, 0.0)
        self.assertLess(post, free)

    def test_without_a_scan_the_robot_does_not_move(self):
        self.assertEqual(self.drive(None), 0.0)

    def test_the_stop_can_be_turned_off(self):
        self.assertGreater(self.drive(person(1.8, 0.0) + person(0.5, 0.15, r=0.06), obstacle_stop=False), 0.3)

    def test_someone_beside_the_target_still_counts(self):
        # a bystander a step in front of and beside the target is not part of the target (blind_corner run)
        pts = person(1.0, 0.0) + person(0.6, 0.25)
        self.assertLess(M.corridor_clearance(pts, 0.3, exclude=(0.8, 0.0), exclude_r=0.30), 0.6)
        self.assertEqual(M.corridor_clearance(person(1.0, 0.0), 0.3, exclude=(0.8, 0.0), exclude_r=0.30), math.inf)

    def test_each_scan_rechecks_the_last_command(self):
        # target messages stop after a moving command (a single false box in the blind_corner run);
        # someone stepping into the corridor is still seen on the next scan
        node = M.FollowStopNode()
        node.cb_scan(scan(person(1.8, 0.0)))
        msg = _Float32MultiArray()
        msg.data = [320.0, 240.0, 0.8, 4.0, 0.9, 0.9, 0.9, 10.0]
        node.cb_fused(msg)
        msg.data = [320.0, 240.0, 1.6, 4.0, 0.9, 0.9, 0.9, 10.0]
        node.cb_fused(msg)
        self.assertGreater(node.pub.messages[-1].linear.x, 0.3)
        sent = len(node.pub.messages)
        node.cb_scan(scan(person(1.8, 0.0)))  # nothing new: no extra command
        self.assertEqual(len(node.pub.messages), sent)
        node.cb_scan(scan(person(1.8, 0.0) + person(0.6, -0.1)))  # someone 0.4 m ahead
        self.assertEqual(node.pub.messages[-1].linear.x, 0.0)


class AvoidTest(unittest.TestCase):
    TARGET = (1.6, 0.0)

    def offset(self, pts, prefer=0.0):
        return M.aim_offset(pts + person(1.8, 0.0), 0.3, self.TARGET, 0.3, prefer)

    def test_a_clear_path_aims_at_the_target(self):
        self.assertEqual(self.offset([]), 0.0)
        self.assertEqual(self.offset(person(0.8, 0.75)), 0.0)  # beside the path, not on it

    def test_a_worker_beside_the_line_is_passed_on_the_other_side(self):
        # pass_by: a crouched worker 0.42 m left of the target's line
        o = self.offset(person(0.9, 0.42))
        self.assertLess(o, 0.0)
        self.assertGreater(o, -0.35)  # the smallest shift that clears, not a wide detour

    def test_the_side_already_taken_is_kept(self):
        pts = person(1.2, 0.0, r=0.06)  # a post dead ahead: both sides are as good
        self.assertLess(self.offset(pts, prefer=-0.2), 0.0)
        self.assertGreater(self.offset(pts, prefer=0.2), 0.0)

    def test_no_shift_that_keeps_the_target_in_view_means_none(self):
        wall = [(0.8, y / 20.0) for y in range(-30, 31)]  # 3 m across the path
        self.assertIsNone(self.offset(wall))

    def test_the_node_aims_beside_the_target_past_a_worker(self):
        node = M.FollowStopNode()
        pts = person(1.8, 0.0) + person(0.9, 0.42)
        node.cb_scan(scan(pts))
        v, w = node.obstacle_command(0.4, 0.0, self.TARGET, 0.0)
        self.assertGreater(v, 0.12)
        self.assertLess(w, 0.0)  # right, away from the worker
        node.obstacle_avoid, node.avoid_offset = False, 0.0
        self.assertEqual(node.obstacle_command(0.4, 0.0, self.TARGET, 0.0)[1], 0.0)

    def test_a_robot_held_beside_an_obstacle_can_start_again(self):
        # pass_by s4: the robot stood beside the worker (left) while the target walked on. The speed ramp from
        # a stop asks for 0.05 m/s with a left turn, a tight arc into the worker, which the stop held at zero
        # for 5 s. Arcs tighter than 2/m are now taken as straight by the stop, and avoid starts from a crawl.
        node = M.FollowStopNode()
        tgt = (1.5 * math.cos(math.radians(11)), 1.5 * math.sin(math.radians(11)))
        node.cb_scan(scan(person(0.07, 0.54) + person(tgt[0] + 0.2, tgt[1])))
        node.obstacle_avoid = False
        self.assertEqual(node.obstacle_command(0.05, 0.2, tgt, math.radians(11))[0], 0.05)


if __name__ == "__main__":
    unittest.main()
