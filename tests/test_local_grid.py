"""grib (experiment, off by default): the rolling local grid, its A* planner, and the follower's safety layers
staying the final authority over what the planner proposes."""

import importlib.util
import math
import unittest
from pathlib import Path

from test_follow_stop_early_turn import _Float32MultiArray, _load_follow_stop
from test_obstacle_stop import person, scan

GRID_PATH = Path(__file__).resolve().parents[1] / "ros2_yolo_ws" / "scripts" / "MAIN" / "Control" / "local_grid.py"
_spec = importlib.util.spec_from_file_location("grib_local_grid", GRID_PATH)
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)
M = _load_follow_stop()


def wall(x0, y0, x1, y1, step=0.05):
    n = max(1, int(round(math.hypot(x1 - x0, y1 - y0) / step)))
    return [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n + 1)]


def scored(points, scans=3, **kw):
    grid = G.LocalGrid(**kw)
    for k in range(scans):
        grid.update(points, 0.1 * k, (0.0, 0.0))
    return grid


class ScoringTest(unittest.TestCase):
    def test_one_scan_is_not_enough_repeated_hits_block(self):
        grid = G.LocalGrid(decay_per_s=0.0)
        grid.update([(1.0, 0.0)], 0.0, (0.0, 0.0))
        self.assertEqual(grid.blocked(), set())
        grid.update([(1.0, 0.0)], 0.1, (0.0, 0.0))
        self.assertEqual(grid.blocked(), {grid.cell_of(1.0, 0.0)})

    def test_many_returns_in_one_cell_count_once_per_scan(self):
        grid = G.LocalGrid()
        grid.update([(1.01, 0.01), (1.02, 0.03), (1.05, 0.05)], 0.0, (0.0, 0.0))
        self.assertEqual(grid.scores, {grid.cell_of(1.0, 0.0): 1.0})

    def test_scores_decay_and_a_cell_clears_once_its_returns_stop(self):
        grid = G.LocalGrid(decay_per_s=2.0, threshold=2.0, max_score=4.0)
        for k in range(10):  # long enough to reach the cap
            grid.update([(1.0, 0.0)], 0.1 * k, (0.0, 0.0))
        c = grid.cell_of(1.0, 0.0)
        self.assertEqual(grid.scores[c], 4.0)
        grid.update([], 1.4, (0.0, 0.0))  # 0.5 s later: 4 - 1 = 3, still blocked
        self.assertIn(c, grid.blocked())
        grid.update([], 2.0, (0.0, 0.0))  # 1.1 s after the last hit: 4 - 2.2 < 2
        self.assertNotIn(c, grid.blocked())
        grid.update([], 3.5, (0.0, 0.0))
        self.assertNotIn(c, grid.scores)

    def test_returns_at_the_target_are_not_scored(self):
        grid = G.LocalGrid()
        grid.update([(1.0, 0.0), (2.0, 0.0)], 0.0, (0.0, 0.0), exclude=(2.0, 0.05), exclude_r=0.3)
        self.assertEqual(set(grid.scores), {grid.cell_of(1.0, 0.0)})

    def test_the_window_rolls_with_the_robot(self):
        grid = G.LocalGrid(size_m=6.0, decay_per_s=0.0)
        grid.update([(2.5, 0.0), (3.5, 0.0)], 0.0, (0.0, 0.0))  # 3.5 m is outside the 6 x 6 m window
        self.assertEqual(set(grid.scores), {grid.cell_of(2.5, 0.0)})
        grid.update([], 0.1, (6.0, 0.0))  # the robot has moved on 6 m: the old cell is dropped
        self.assertEqual(grid.scores, {})


class InflationTest(unittest.TestCase):
    def test_blocked_cells_grow_by_the_inflation_radius(self):
        grid = scored([(1.05, 0.05)], inflate_m=0.25)
        bad = grid.inflated()
        c = grid.cell_of(1.05, 0.05)
        self.assertIn(c, bad)
        self.assertIn((c[0] + 2, c[1]), bad)       # 0.2 m away
        self.assertIn((c[0] + 1, c[1] + 2), bad)   # 0.22 m away
        self.assertNotIn((c[0] + 3, c[1]), bad)    # 0.3 m away
        self.assertNotIn((c[0] + 2, c[1] + 2), bad)  # 0.28 m away

    def test_no_inflation_leaves_only_the_blocked_cells(self):
        grid = scored([(1.05, 0.05), (0.55, -0.45)], inflate_m=0.0)
        self.assertEqual(grid.inflated(), grid.blocked())


class PlannerTest(unittest.TestCase):
    def test_a_clear_grid_plans_straight(self):
        grid = scored([])
        path = grid.plan((0.05, 0.05), (2.05, 0.05))
        self.assertAlmostEqual(G.path_length((0.05, 0.05), path), 2.0, places=6)
        self.assertEqual(grid.waypoint((0.05, 0.05), path, 1.0), (1.05, 0.05))

    def test_a_star_goes_round_a_wall(self):
        grid = scored(wall(1.0, -1.0, 1.0, 1.0))  # a 2 m wall across the way, 1 m ahead
        start, goal = (0.05, 0.05), (2.05, 0.05)
        path = grid.plan(start, goal)
        self.assertIsNotNone(path)
        bad = grid.inflated()
        self.assertFalse(any(grid.cell_of(*p) in bad for p in path[1:]))
        self.assertTrue(any(abs(p[1]) > 1.2 for p in path))  # round an end of the wall
        self.assertGreater(G.path_length(start, path), 3.0)
        wp = grid.waypoint(start, path, 1.0)
        self.assertTrue(grid.line_clear(start, wp, bad))
        self.assertGreater(abs(wp[1]), 0.3)  # the first waypoint already leads off to one side

    def test_a_star_keeps_off_people_where_there_is_room(self):
        # blind_corner: someone 0.55 m left of the robot's line; the path passes them on the right, farther than
        # the inflation alone would allow
        grid = scored(person(1.5, 0.55))
        path = grid.plan((0.05, 0.05), (3.05, 0.05))
        near = min(path, key=lambda p: abs(p[0] - 1.5))
        self.assertLess(near[1], 0.05)

    def test_no_path_when_boxed_in(self):
        box = wall(-0.6, -0.6, 0.6, -0.6) + wall(0.6, -0.6, 0.6, 0.6) + wall(0.6, 0.6, -0.6, 0.6) \
            + wall(-0.6, 0.6, -0.6, -0.6)
        grid = scored(box)
        self.assertIsNone(grid.plan((0.05, 0.05), (2.05, 0.05)))

    def test_a_goal_outside_the_window_is_pulled_in(self):
        grid = scored([])
        path = grid.plan((0.05, 0.05), (10.0, 0.05))
        self.assertIsNotNone(path)
        self.assertLessEqual(path[-1][0], 3.0)


class NodeGribTest(unittest.TestCase):
    """The grid only proposes: the obstacle stop, the spin circle and the per-scan re-check still decide."""

    def node(self):
        node = M.FollowStopNode()
        self.assertFalse(node.grib)  # off by default
        self.assertIsNone(node.grid)
        node.grib, node.grid = True, M.LocalGrid()
        return node

    def fused(self, node, dist, cx=320.0):
        msg = _Float32MultiArray()
        msg.data = [cx, 240.0, dist, 4.0, 0.9, 0.9, 0.9, 10.0]
        node.cb_fused(msg)
        return node.pub.messages[-1].linear.x, node.pub.messages[-1].angular.z

    def test_grib_is_off_by_default_and_changes_no_existing_default(self):
        node = M.FollowStopNode()
        self.assertFalse(node.parameters['grib'])
        self.assertIsNone(node.grid)
        for name, value in (('obstacle_stop', True), ('obstacle_half_width_m', 0.30), ('obstacle_stop_m', 0.45),
                            ('spin_clear_radius_m', 0.40), ('recheck_max_s', 1.0), ('avoid_trail', False),
                            ('trail_hold_s', 0.0)):
            self.assertEqual(node.parameters[name], value, name)

    def test_the_planner_goes_round_and_never_faster_than_asked(self):
        node = self.node()
        pts = person(2.4, 0.0) + person(1.0, 0.1, r=0.1)  # the target 2.4 m ahead, a post on the line at 0.9 m
        for _ in range(3):
            node.cb_scan(scan(pts))
        self.fused(node, 0.8)  # lock
        node.cb_scan(scan(pts))
        asked, _ = M.speed_command(2.4 - 0.5, 0.0, 0.0, node.linear_gain, node.tolerance, node.max_linear_speed,
                                   node.speed_ff_gain, node.speed_ff_max, node.speed_ff_decay_s, node.max_decel,
                                   node.latency_s, 0.0)
        v, w = self.fused(node, 2.4)
        self.assertTrue(node.gribbing)
        self.assertLessEqual(v, asked)
        self.assertNotEqual(w, 0.0)  # steering off the line, round the post

    def test_a_grib_command_into_the_corridor_is_stopped(self):
        node = self.node()
        pts = person(1.6, 0.0) + person(0.5, 0.15, r=0.06)  # a post 0.44 m ahead, inside the stop distance
        for _ in range(3):
            node.cb_scan(scan(pts))
        # a planner that ignores the post: straight at the target
        node.grid.plan = lambda start, goal, goal_r=0.0: [(0.05, 0.05), (0.55, 0.05), (1.05, 0.05)]
        node.grid.waypoint = lambda start, path, lookahead=1.0: (1.05, 0.05)
        self.fused(node, 0.8)
        node.cb_scan(scan(pts))
        v, _ = self.fused(node, 1.6)
        self.assertTrue(node.gribbing)
        self.assertEqual(v, 0.0)

    def test_a_grib_turn_with_someone_in_the_spin_circle_is_not_sent(self):
        # a planner that wants a sharp left with a post 0.44 m ahead: the stop holds every arc, so only a turn in
        # place is left. With the spin circle clear it is sent (control); with a post beside the rear corner, not.
        for rear, expect in (([], (0.0, 0.4)), (person(-0.15, 0.32, r=0.03), (0.0, 0.0))):
            node = self.node()
            pts = person(1.6, 0.0) + person(0.5, 0.0, r=0.06) + rear
            for _ in range(3):
                node.cb_scan(scan(pts))
            node.grid.plan = lambda start, goal, goal_r=0.0: [(0.05, 0.05), (0.05, 0.55), (0.05, 1.05)]
            node.grid.waypoint = lambda start, path, lookahead=1.0: (0.05, 1.05)
            self.fused(node, 0.8)
            node.cb_scan(scan(pts))
            v, w = self.fused(node, 1.6)
            self.assertTrue(node.gribbing)
            self.assertEqual((v, w), expect)

    def test_a_published_grib_command_is_rechecked_on_the_next_scan(self):
        node = self.node()
        pts = person(2.4, 0.0) + person(1.0, 0.1, r=0.1)
        for _ in range(3):
            node.cb_scan(scan(pts))
        self.fused(node, 0.8)
        node.cb_scan(scan(pts))
        v, _ = self.fused(node, 2.4)
        self.assertTrue(node.gribbing)
        self.assertGreater(v, 0.0)
        node.cb_scan(scan(pts + person(0.45, 0.0, r=0.06)))  # someone steps in close ahead
        self.assertEqual(node.pub.messages[-1].linear.x, 0.0)

    def test_grib_never_steers_away_from_a_target_in_view(self):
        # blind_corner probe: the path round the bystander swerved right while the target turned left
        node = self.node()
        node.cb_scan(scan(person(0.9, 0.3, r=0.1)))
        node.grid.plan = lambda start, goal, goal_r=0.0: [(0.05, 0.05), (0.55, -0.45), (1.05, -0.45)]
        node.grid.waypoint = lambda start, path, lookahead=1.0: (0.55, -0.45)
        tb = 0.2
        v, w = node.obstacle_command(0.4, 0.0, (1.5 * math.cos(tb), 1.5 * math.sin(tb)), tb)
        self.assertTrue(node.gribbing)
        self.assertGreaterEqual(w, 0.0)

    def test_the_goal_at_the_image_edge_is_never_behind_the_robot(self):
        node = self.node()
        node.grib_seen = [(0.0, 1.0, 0.0), (-0.5, 1.0, 0.5)]  # last seen walking back past the robot's left
        half = math.radians(node.camera_hfov_deg / 2.0)
        edge_xy = (1.2 * math.cos(half), 1.2 * math.sin(half))  # sync_fusion: at the left edge, 1.2 m
        gx, gy = node.grib_edge_goal(edge_xy, 1.0)
        self.assertAlmostEqual(math.hypot(gx, gy), 1.2)
        self.assertGreaterEqual(gx, -1e-9)  # at most 90 deg to the left
        self.assertGreater(gy, 0.0)
        node.grib_seen = [(1.0, 0.0, 0.0), (1.0, -0.4, 0.5)]  # predicted to the right, reported at the left edge
        gx, gy = node.grib_edge_goal(edge_xy, 1.0)
        self.assertAlmostEqual(math.atan2(gy, gx), half)


if __name__ == "__main__":
    unittest.main()
