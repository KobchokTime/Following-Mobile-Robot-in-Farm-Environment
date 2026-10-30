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

    def test_the_recheck_ends_with_the_bridge_timeout_and_stops_the_turn(self):
        # T18 review: the re-check resent lowered commands with no age limit, ending in a turn in place
        node = M.FollowStopNode()
        clock = {'t': 0.0}
        now = type('Now', (), {'nanoseconds': property(lambda self_: int(clock['t'] * 1e9))})
        node.get_clock = lambda: type('Clock', (), {'now': lambda self_: now()})()
        node.cb_scan(scan(person(1.8, 0.0)))
        cmd = M.Twist(); cmd.linear.x = 0.5; cmd.angular.z = 0.6
        node.send(cmd, (1.6, 0.0))
        clock['t'] = 0.2
        node.cb_scan(scan(person(1.8, 0.0) + person(0.55, -0.05)))  # someone steps in: stop
        last = node.pub.messages[-1]
        self.assertEqual((last.linear.x, last.angular.z), (0.0, 0.0))
        node.moving_cmd = cmd  # had it not stopped: a command 1.2 s old is no longer re-sent
        sent = len(node.pub.messages)
        clock['t'] = 1.2
        node.cb_scan(scan(person(1.8, 0.0) + person(0.9, -0.05)))
        self.assertEqual(len(node.pub.messages), sent)


class StoppedTurnTest(unittest.TestCase):
    """T18 (Codex): a zero speed cap must not leave a turn in place running."""

    def edge_commands(self, scan_points):
        node = M.FollowStopNode()
        node.obstacle_avoid = False
        msg = _Float32MultiArray()
        for d in (0.8, 1.6):  # the target at the image edge: the controller asks for a full-rate turn
            if scan_points is not None:
                node.cb_scan(scan(scan_points))
            msg.data = [0.0, 240.0, d, 8.0, 0.9, 0.9, 0.9, 10.0]
            node.cb_fused(msg)
        return [(m.linear.x, m.angular.z) for m in node.pub.messages]

    def test_no_scan_sends_no_turn(self):
        self.assertTrue(all(c == (0.0, 0.0) for c in self.edge_commands(None)))

    def test_something_inside_the_spin_circle_stops_the_turn_too(self):
        self.assertTrue(all(c == (0.0, 0.0) for c in self.edge_commands(person(0.45, 0.0, r=0.06))))

    def test_with_the_spin_circle_clear_the_robot_may_turn_in_place(self):
        cmds = self.edge_commands(person(0.6, 0.0, r=0.06))  # a post ahead, outside the 0.40 m spin circle
        self.assertEqual(cmds[0], (0.0, -0.8))  # still standing: the turn alone is allowed

    def test_a_creep_with_a_sharp_turn_is_checked_as_a_spin(self):
        # T18 integration probe: a post beside the rear quarter, inside the spin circle but outside the corridor
        node = M.FollowStopNode()
        node.cb_scan(scan(person(-0.15, 0.32, r=0.03)))
        for cmd in ((0.0, -0.8), (0.03, -0.8), (0.06, -0.8), (-0.03, -0.8)):
            self.assertEqual(node.obstacle_command(cmd[0], cmd[1], (1.5, 0.0), 0.0), (cmd[0], 0.0), cmd)  # no turn
        node.cb_scan(scan([]))  # the same with the circle clear: sent as asked
        self.assertEqual(node.obstacle_command(0.06, -0.8, (1.5, 0.0), 0.0), (0.06, -0.8))

    def test_a_lowered_resend_goes_through_the_spin_check(self):
        # T18 integration probe: (0.3, 0.8) sent with the circle clear; then a post beside the rear quarter and
        # something closing ahead. The re-check lowered the speed and kept the turn, each resend a tighter arc.
        node = M.FollowStopNode()
        node.cb_scan(scan([]))
        cmd = M.Twist(); cmd.linear.x = 0.3; cmd.angular.z = 0.8
        node.send(cmd, (1.5, 0.0))
        node.cb_scan(scan(person(-0.15, 0.32, r=0.03) + person(0.55, 0.0, r=0.06)))
        last = node.pub.messages[-1]
        self.assertLess(last.linear.x, 0.3)
        self.assertEqual(last.angular.z, 0.0)

    def test_a_new_obstacle_in_the_spin_circle_stops_a_published_turn(self):
        # T18 (Codex 10:43): a turn in place, then a scan with a post inside the spin circle and no new target
        # message; the turn kept running until the next fused message or the bridge timeout
        node = M.FollowStopNode()
        node.obstacle_avoid = False
        node.cb_scan(scan(person(0.6, 0.0, r=0.06)))
        msg = _Float32MultiArray()
        msg.data = [0.0, 240.0, 0.8, 8.0, 0.9, 0.9, 0.9, 10.0]
        node.cb_fused(msg)
        node.cb_fused(msg)
        self.assertEqual((node.pub.messages[-1].linear.x, node.pub.messages[-1].angular.z), (0.0, -0.8))
        node.cb_scan(scan(person(0.6, 0.0, r=0.06) + person(-0.15, 0.32, r=0.03)))
        self.assertEqual((node.pub.messages[-1].linear.x, node.pub.messages[-1].angular.z), (0.0, 0.0))

    def test_a_new_obstacle_in_the_spin_circle_stops_a_near_spin(self):
        node = M.FollowStopNode()
        node.cb_scan(scan([]))
        cmd = M.Twist(); cmd.linear.x = 0.06; cmd.angular.z = -0.8
        node.send(cmd, (1.5, 0.0))
        node.cb_scan(scan(person(-0.15, 0.32, r=0.03)))  # the creep's cap does not drop; the turn must
        last = node.pub.messages[-1]
        self.assertEqual(last.angular.z, 0.0)
        self.assertLessEqual(abs(last.linear.x), 0.06)

    def test_the_scan_is_subscribed_best_effort(self):
        seen = []
        original = M.FollowStopNode.create_subscription
        M.FollowStopNode.create_subscription = lambda self_, *args: seen.append(args) or object()
        try:
            M.FollowStopNode()
        finally:
            M.FollowStopNode.create_subscription = original
        qos = [a[3] for a in seen if a[0] is M.LaserScan]
        self.assertEqual(qos, [M.qos_profile_sensor_data])


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
        node.avoid_delay = 0.0
        pts = person(1.8, 0.0) + person(0.9, 0.42)
        node.cb_scan(scan(pts))
        v, w = node.obstacle_command(0.4, 0.0, self.TARGET, 0.0)
        self.assertGreater(v, 0.12)
        self.assertLess(w, 0.0)  # right, away from the worker
        node.obstacle_avoid, node.avoid_offset = False, 0.0
        self.assertEqual(node.obstacle_command(0.4, 0.0, self.TARGET, 0.0)[1], 0.0)

    def test_someone_level_with_the_robot_is_beside_it_not_ahead(self):
        # pass_by s3/s8: the worker 0.28 m from the robot's centre line, level with it, inside the 0.30 m
        # corridor but outside the 0.235 m body; driving on slides past them
        pts = person(0.05, 0.48)
        self.assertEqual(M.corridor_clearance(pts, 0.3), math.inf)
        self.assertFalse(M.segment_blocked(pts, 0.3, (1.5, 0.0)))
        self.assertLess(M.corridor_clearance(person(0.5, 0.48), 0.3), 1.0)  # the same, ahead: in the way

    def test_someone_crossing_is_waited_for_not_gone_round(self):
        node = M.FollowStopNode()  # avoid_delay_s 1.0; the test clock stands still
        node.cb_scan(scan(person(1.8, 0.0) + person(0.9, 0.42)))
        self.assertEqual(node.obstacle_command(0.4, 0.0, self.TARGET, 0.0)[1], 0.0)
        self.assertIsNotNone(node.blocked_since)

    def test_avoid_turns_on_a_real_arc_beside_the_worker(self):
        # pass_by s1 on 838598d: the worker 0.66 m away at 52 deg, just inside the corridor ahead; the avoid's slow
        # sharp turn was a near spin (straight, blocked) and the spin circle was not clear, so the robot stood
        node = M.FollowStopNode()
        node.avoid_delay = 0.0
        b = math.radians(52)
        tgt = (1.1, 0.1)
        node.cb_scan(scan(person(0.66 * math.cos(b), 0.66 * math.sin(b)) + person(tgt[0] + 0.2, tgt[1])))
        v, w = node.obstacle_command(0.12, 0.0, tgt, math.atan2(tgt[1], tgt[0]))
        self.assertGreater(v, 0.0)
        self.assertLess(w, 0.0)  # away from the worker
        self.assertLessEqual(abs(w / v), 2.0 + 1e-9)

    def test_avoid_never_speeds_up_toward_a_close_target(self):
        # T18 integration review of 2e75972: |w|/2 as a minimum speed reached 0.17-0.26 m/s with the target
        # 0.7-1.1 m away while the follower asked for 0.02 m/s
        node = M.FollowStopNode()
        node.avoid_delay = 0.0
        tgt = (0.7, 0.0)
        node.cb_scan(scan(person(0.45, 0.32, r=0.1) + person(tgt[0] + 0.2, tgt[1])))  # 0.4 m/s before the fix
        v, w = node.obstacle_command(0.02, 0.0, tgt, 0.0)
        self.assertLessEqual(v, node.avoid_min_speed + 1e-9)
        self.assertLessEqual(abs(w), 2.0 * node.avoid_min_speed + 1e-9)

    def test_held_everywhere_it_turns_slowly_and_keeps_the_target_in_view(self):
        # pass_by s2 on 7ac1cd1: straight and every gentler arc held; it spun at 0.8 rad/s and lost the target
        node = M.FollowStopNode()
        node.cb_scan(scan([(0.44, y / 20.0) for y in range(-8, 9)]))  # something across the lane, outside the circle
        v, w = node.moving_turn(0.4, -0.8, None, 0.0)
        self.assertEqual(v, 0.0)
        self.assertGreaterEqual(w, -0.4)
        self.assertLess(w, 0.0)
        self.assertEqual(node.moving_turn(0.4, -0.8, None, 0.25)[1], 0.0)  # the target 14 deg left: hold
        self.assertEqual(node.moving_turn(0.4, -0.8, None, 0.5)[1], 0.4)  # the target 29 deg left: turn to it

    def test_with_no_way_round_it_backs_off_slowly_if_nothing_is_behind(self):
        # blind_corner s2 on f01dd98: stopped 0.68 m from the bystander with the target 2.9 m out behind them;
        # no aim within 0.5 rad clears, and it stood there 14 s
        tb = math.radians(7.0)
        tgt = (2.86 * math.cos(tb), 2.86 * math.sin(tb))
        by = (0.68 * math.cos(math.radians(-11.0)), 0.68 * math.sin(math.radians(-11.0)))
        node = M.FollowStopNode()
        node.avoid_delay = 0.0
        node.cb_scan(scan(person(*by) + person(tgt[0] + 0.2, tgt[1])))
        v, w = node.obstacle_command(0.4, 0.0, tgt, tb)
        self.assertLess(v, 0.0)
        self.assertGreaterEqual(v, -node.avoid_back_mps)
        self.assertEqual(w, 0.0)
        # blocked long before (s2 on 3a4ac4a turned in place 4 s first): the back-off time starts with it
        node = M.FollowStopNode()
        node.avoid_delay = 0.0
        node.cb_scan(scan(person(*by) + person(tgt[0] + 0.2, tgt[1])))
        node.blocked_since = node.get_clock().now().nanoseconds / 1e9 - 10.0
        self.assertLess(node.obstacle_command(0.4, 0.0, tgt, tb)[0], 0.0)
        node = M.FollowStopNode()
        node.avoid_delay = 0.0
        node.cb_scan(scan(person(*by) + person(tgt[0] + 0.2, tgt[1]) + person(-0.5, 0.0)))  # someone behind
        self.assertEqual(node.obstacle_command(0.4, 0.0, tgt, tb)[0], 0.0)

    def test_a_fast_request_beside_a_worker_still_goes_round_at_a_crawl(self):
        # pass_by s2 on a30c90d: asked for 1.3 m/s, the way round was a near straight arc held like straight,
        # and it stood 5 s beside the worker while the target walked on
        def at(r, deg):
            return r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg))
        node = M.FollowStopNode()
        node.avoid_delay = 0.0
        tgt = at(2.05, 15.0)
        node.cb_scan(scan(person(*at(0.67, 51.0)) + person(*at(2.25, 15.0))))
        v, w = node.obstacle_command(1.34, -0.15, tgt, math.radians(15.0))
        self.assertGreater(v, 0.0)
        self.assertLessEqual(v, node.avoid_min_speed + 1e-9)
        self.assertLessEqual(abs(w), 2.0 * v + 1e-9)

    def test_an_arc_held_by_someone_beside_it_goes_gentler_or_straight(self):
        # blind_corner s2 on f47c6d7: the arc towards the target brushed the bystander, the straight line was
        # clear, and the robot stood 4 s while the target walked out of range
        node = M.FollowStopNode()
        node.obstacle_avoid = False
        node.cb_scan(scan(person(0.3, 0.6)))  # on the arc, clear of the straight line
        tgt = (2.0, 0.3)
        self.assertEqual(node.obstacle_limited(0.4, tgt, 0.3), 0.0)
        v, w = node.obstacle_command(0.4, 0.3, tgt, math.atan2(0.3, 2.0))
        self.assertGreater(v, 0.0)
        self.assertLess(w, 0.3)

    def test_a_robot_held_beside_an_obstacle_can_start_again(self):
        # pass_by s4: the robot stood beside the worker (left) while the target walked on. The speed ramp from
        # a stop asks for 0.05 m/s with a left turn, a tight arc into the worker, which the stop held at zero
        # for 5 s. Arcs tighter than 2/m are now taken as straight by the stop, and avoid starts from a crawl.
        node = M.FollowStopNode()
        tgt = (1.5 * math.cos(math.radians(11)), 1.5 * math.sin(math.radians(11)))
        node.cb_scan(scan(person(0.07, 0.54) + person(tgt[0] + 0.2, tgt[1])))
        node.obstacle_avoid = False
        self.assertEqual(node.obstacle_command(0.05, 0.2, tgt, math.radians(11)), (0.05, 0.0))  # straight past


class TrailTest(unittest.TestCase):
    """blind_corner: the target turned left round someone standing at the inside of the corner; the robot
    cut the corner, stopped and lost the target. It follows the target's own path instead."""
    CRUMBS = [(x / 10.0, 0.0) for x in range(0, 21)] + [(2.0, y / 10.0) for y in range(1, 15)]

    def test_the_newest_clear_crumb_is_the_corner_not_the_target(self):
        pose = (0.9, 0.0, 0.0)
        bystander = person(1.45 - 0.9, 0.55)  # robot frame: at the inside of the corner
        aim = M.trail_aim(self.CRUMBS, pose, bystander, 0.3)
        self.assertIsNotNone(aim)
        self.assertGreater(aim[0], 0.9)    # on to the corner (1.1 m ahead), not stopping short of the bystander
        self.assertLess(aim[1], 0.05)      # on the target's first leg, or just right of it, never cutting left
        self.assertGreater(aim[1], -0.35)

    def test_past_the_corner_the_trail_turns(self):
        pose = (2.0, 0.0, math.pi / 2)  # at the corner, facing the target's second leg
        aim = M.trail_aim(self.CRUMBS, pose, [], 0.3)
        self.assertGreater(aim[0], 1.0)  # straight on up the second leg

    def test_nothing_reachable_means_no_aim(self):
        wall = [(0.3, y / 20.0) for y in range(-40, 41)]
        self.assertIsNone(M.trail_aim(self.CRUMBS, (0.0, 0.0, 0.0), wall, 0.3))

    def test_the_trail_does_not_turn_away_from_a_target_off_to_the_other_side(self):
        # blind_corner s0 on a30c90d: the crumbs lay right, the target walked on 35 deg left; turning to the
        # crumbs took it out of the image
        tb = math.radians(35.0)
        tgt = (1.2 * math.cos(tb), 1.2 * math.sin(tb))
        node = M.FollowStopNode()
        node.avoid_delay = 0.0
        node.avoid_back_mps = 0.0
        node.cb_scan(scan(person(0.6, 0.42) + person(tgt[0] + 0.2 * math.cos(tb), tgt[1] + 0.2 * math.sin(tb))))
        node.crumbs = [(0.7, -0.25, 0.0), (0.9, -0.25, 0.0)]
        self.assertIsNone(M.aim_offset(node.scan_xy, node.obstacle_half_w, tgt, node.obstacle_excl))
        node.obstacle_command(0.4, 0.0, tgt, tb)
        self.assertTrue(node.trailing)
        self.assertGreaterEqual(node.obstacle_command(0.4, 0.0, tgt, tb)[1], 0.0)

    def test_a_blocked_line_follows_the_trail_at_once(self):
        # blind_corner on 56a6a89: every run that stood out the 1 s avoid delay at the inside of the corner lost
        # the target; every run that drove on along the target's path to the corner kept it
        node = M.FollowStopNode()
        node.cb_scan(scan(person(0.9, 0.42)))
        node.crumbs = [(x / 10.0, 0.0, 0.0) for x in range(0, 17)]
        v, w = node.obstacle_command(0.4, 0.0, (1.6, 0.0), 0.0)
        self.assertTrue(node.trailing)
        self.assertGreater(v, 0.0)

    def test_the_trail_is_driven_at_the_speed_of_the_way_left_along_it(self):
        # blind_corner s1/s3 on 47109fb: 0.8 m from the target in a straight line, a corner away along its path,
        # the trail crawled to the corner and the target was out of view 2.7 s (in view 0.897)
        node = M.FollowStopNode()
        node.crumbs = [(1.0, 0.0, 0.0), (1.0, 0.8, 0.0)]
        self.assertAlmostEqual(node.trail_length((1.0, 0.0)), 1.8)
        node.cb_scan(scan(person(0.55, 0.55)))
        v, _ = node.obstacle_command(0.1, 0.0, (1.0, 0.8), math.atan2(0.8, 1.0))
        self.assertTrue(node.trailing)
        self.assertGreater(v, 0.2)  # not the 0.12 crawl; the stop still caps it near the bystander

    def test_dead_reckoning_and_crumbs(self):
        node = M.FollowStopNode()
        clock = {'t': 0.0}
        now = type('Now', (), {'nanoseconds': property(lambda self_: int(clock['t'] * 1e9))})
        node.get_clock = lambda: type('Clock', (), {'now': lambda self_: now()})()
        node.advance_pose()
        node.v_wheels, node.last_angular = 0.5, 0.0
        for k in (1, 2, 3, 4, 5):
            clock['t'] = 0.2 * k
            node.advance_pose()
        self.assertAlmostEqual(node.pose[0], 0.5, places=6)
        node.add_crumb((1.0, 0.0), clock['t'])
        node.add_crumb((1.05, 0.0), clock['t'])  # under 0.1 m from the last: not kept
        self.assertEqual([c[:2] for c in node.crumbs], [(1.5, 0.0)])


if __name__ == "__main__":
    unittest.main()
