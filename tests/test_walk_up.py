"""A stranger who steps out beside the target, through the node's own path (try_sync_from_yolo).

Integration's T15 finding: the wider lateral gate is used while the target looks alone, and "alone" was
only known from two boxes in one frame. A stranger whose box comes first in that frame, or whose box
comes in a frame where the target's is missed, was taken as the target.
"""

import math
import types
import unittest

from test_target_gate import _load
import test_sector_association

person = test_sector_association.SectorAssociationTest._person


def scan(*objects):
    """One return per ray, the nearest, as a LiDAR sees several objects."""
    best = {}
    for pts in objects:
        for b, r in pts:
            best[round(b, 6)] = min(best.get(round(b, 6), math.inf), r)
    return sorted(best.items())


class FakeNode:
    def __init__(self, name):
        self.parameters = {}
        self.published = []

    def declare_parameter(self, name, default):
        self.parameters[name] = self.overrides.get(name, default)

    def get_parameter(self, name):
        return types.SimpleNamespace(value=self.parameters[name])

    def create_subscription(self, *args):
        pass

    create_timer = create_subscription

    def create_publisher(self, *args):
        return types.SimpleNamespace(publish=lambda msg: self.published.append(list(msg.data)))

    def get_logger(self):
        self.logs = getattr(self, 'logs', [])
        return types.SimpleNamespace(info=self.logs.append, debug=lambda *a: None)

    def get_clock(self):
        return types.SimpleNamespace(now=lambda: types.SimpleNamespace(nanoseconds=0))


class Msg:
    def __init__(self):
        self.data = []


def make_node(**overrides):
    FakeNode.overrides = overrides
    m = _load(node_class=FakeNode)
    m.QoSProfile = lambda **kwargs: None
    m.QoSReliabilityPolicy = types.SimpleNamespace(BEST_EFFORT=1)
    m.QoSHistoryPolicy = types.SimpleNamespace(KEEP_LAST=1)
    m.QoSDurabilityPolicy = types.SimpleNamespace(VOLATILE=1)
    m.Float32MultiArray = Msg
    node = m.SyncFusionNode()
    node.lidar_angles = [0.0]
    return m, node


class WalkUpTest(unittest.TestCase):
    W, HFOV = 640, 70.0

    def test_remembered_opposite_boxes_block_edge_track_and_clear_on_camera_fix(self):
        _, node = make_node()
        node.gate.accept(0.0, 0.0, 0.95)
        node.gate.accept(1.2, 0.0, 0.95)
        node.gate.bearing = math.radians(3.0)
        node.gate.range = 0.95
        node.gate.bearing_rate = node.gate.range_rate = 0.0
        node.gate.t = 1.2
        node.last_target = (320, 240, 4, 0.95)
        node.recent_ranges = [(1.2, 0.95)]
        f = (self.W / 2.0) / math.tan(math.radians(self.HFOV) / 2.0)

        def camera(t, deg, rng):
            b = math.radians(deg)
            node.scan_points = scan(person(rng * math.cos(b), rng * math.sin(b)))
            node.scan_time = t
            node.buf_lidar.clear()
            node.buf_lidar.append((t, [rng]))
            cx = int(round(self.W / 2.0 - f * math.tan(b)))
            node.try_sync_from_yolo(t, cx, 240, 4)

        camera(1.3, 3.0, 0.95)
        self.assertEqual(node.last_camera_fix, 1.3)
        # As on the robot (E6 bag, [CROWD] on): someone was just beside the target, so the plain gate applies
        # and the boxes of the person stepping right are rejected; it ends before the LiDAR track call.
        node.gate.ambiguous_until = 1.75
        # Rejected boxes are all recorded while the prediction remains within the edge threshold.
        for k, deg in enumerate((-6.9, -17.3, -26.6, -30.5), 1):
            t = 1.3 + k * 0.1
            node.gate.bearing = math.radians(20.0)
            node.gate.t = t
            self.assertLess(abs(node.gate._predict(t)[0]), node.edge_rad)
            camera(t, deg, 0.9)
            self.assertEqual(node.last_camera_fix, 1.3)
            self.assertFalse(node.camera_lidar_conflict)  # the round-3 latch alone misses this sequence
        self.assertEqual(len(node.rejected_camera_boxes), 4)
        node.gate.bearing = math.radians(31.0)
        node.gate.t = 1.8
        now = 1.9
        node.now_sec = lambda: now
        node.scan_points = [(math.radians(b), 0.95) for b in range(42, 56)]
        node.scan_time = now
        predicted, pr = node.gate._predict(now)
        self.assertGreaterEqual(abs(predicted), node.edge_rad)
        self.assertTrue(node.scan_time is not None and abs(now - node.scan_time) <= node.scan_max_age)
        self.assertTrue(any(abs(b - predicted) < math.radians(25) and abs(r - pr) <= 0.5
                            for b, r, _ in _load().lidar_clusters(node.scan_points)))
        before = len(node.published)
        node.track_with_lidar()
        self.assertTrue(node.camera_lidar_conflict)
        self.assertEqual(len(node.published), before)  # nothing from the LiDAR track

        # A camera-accepted fix clears both the latch and remembered boxes; the next edge track resumes.
        node.gate.bearing = math.radians(3.0)
        node.gate.t = 2.0
        camera(2.0, 3.0, 0.95)
        self.assertFalse(node.camera_lidar_conflict)
        self.assertEqual(node.rejected_camera_boxes, [])
        node.gate.bearing = math.radians(31.0)
        node.gate.t = 2.0
        node.now_sec = lambda: 2.4
        node.scan_points = [(math.radians(b), 0.95) for b in range(42, 56)]  # the left cluster again
        node.scan_time = 2.4
        before = len(node.published)
        node.track_with_lidar()
        self.assertEqual(len(node.published), before + 1)
        self.assertEqual(node.published[-1][0], 0.0)

    def test_rejected_opposite_box_farther_than_behind_limit_does_not_block_edge_track(self):
        _, node = make_node()
        node.gate.accept(0.0, 0.0, 0.9)
        node.gate.accept(1.2, 0.0, 0.9)
        node.gate.bearing = math.radians(3.0)
        node.gate.range = 0.9
        node.gate.bearing_rate = node.gate.range_rate = 0.0
        node.gate.t = 1.2
        node.last_target = (320, 240, 4, 0.9)
        node.last_camera_fix = 1.2
        node.last_camera_bearing = math.radians(3.0)
        node.recent_ranges = [(1.2, 0.9)]
        b = math.radians(-20.0)
        node.scan_points = scan(person(3.0 * math.cos(b), 3.0 * math.sin(b)))
        node.scan_time = 1.3
        node.buf_lidar.clear()
        node.buf_lidar.append((1.3, [3.0]))
        cx = int(round(self.W / 2.0 - (self.W / 2.0 / math.tan(math.radians(self.HFOV) / 2.0))
                       * math.tan(b)))
        node.gate.ambiguous_until = 1.35  # plain gate for this frame, as in the bag
        node.try_sync_from_yolo(1.3, cx, 240, 4)
        self.assertEqual(node.last_camera_fix, 1.2)  # rejected
        self.assertGreater(3.0, node.gate._predict(1.3)[1] + node.lidar_conflict_behind)
        self.assertEqual(node.rejected_camera_boxes, [])  # clearly behind the target
        node.gate.bearing = math.radians(31.0)
        node.gate.range = 0.9
        node.gate.t = 1.4
        node.now_sec = lambda: 1.8
        node.scan_points = [(math.radians(deg), 0.9) for deg in range(42, 56)]
        node.scan_time = 1.8
        self.assertGreaterEqual(abs(node.gate._predict(1.8)[0]), node.edge_rad)
        node.track_with_lidar()
        self.assertFalse(node.camera_lidar_conflict)
        self.assertTrue(node.published)
        self.assertEqual(node.published[-1][0], 0.0)

    def test_rejected_near_centre_box_blocks_edge_track_publication(self):
        _, node = make_node()
        node.gate.accept(0.0, 0.0, 0.95)
        node.gate.accept(1.2, 0.0, 0.95)
        node.gate.bearing, node.gate.range, node.gate.t = math.radians(3), 0.95, 1.2
        node.gate.bearing_rate = node.gate.range_rate = 0.0
        node.last_target = (320, 240, 4, 0.95)
        node.last_camera_fix, node.last_camera_bearing = 1.2, math.radians(3)
        node.recent_ranges = [(1.2, 0.95)]
        node.gate.ambiguous_until = 2.0
        # the track has drifted right (-20 deg) while the person is straight ahead: the centred box is rejected
        node.gate.bearing, node.gate.t = math.radians(-20), 1.3
        node.scan_points = scan(person(0.95, 0.0))
        node.scan_time = 1.3
        node.buf_lidar.append((1.3, [0.95]))
        node.try_sync_from_yolo(1.3, 320, 240, 4)
        self.assertEqual(node.last_camera_fix, 1.2)
        self.assertEqual(len(node.rejected_camera_boxes), 1)
        self.assertLess(abs(node.rejected_camera_boxes[0][1]), node.lidar_conflict_centre)
        # same side as the track (right), so only the centre band can block it (auditor P1)
        node.gate.bearing, node.gate.t = math.radians(-31), 1.4
        node.now_sec = lambda: 1.8
        node.scan_points = [(math.radians(deg), 0.95) for deg in range(-56, -42)]
        node.scan_time = 1.8
        self.assertGreaterEqual(abs(node.gate._predict(1.8)[0]), node.edge_rad)
        before = len(node.published)
        node.track_with_lidar()
        self.assertEqual(len(node.published), before)
        self.assertTrue(node.camera_lidar_conflict)

    def test_nearer_opposite_box_range_mismatch_blocks_edge_track(self):
        self._assert_opposite_box_blocks_edge_track(0.40)

    def test_farther_opposite_box_range_mismatch_blocks_edge_track(self):
        self._assert_opposite_box_blocks_edge_track(1.55)

    def _assert_opposite_box_blocks_edge_track(self, box_range):
        _, node = make_node()
        node.gate.accept(0.0, 0.0, 0.95)
        node.gate.accept(1.2, 0.0, 0.95)
        node.gate.bearing, node.gate.range, node.gate.t = math.radians(3), 0.95, 1.2
        node.gate.bearing_rate = node.gate.range_rate = 0.0
        node.last_target = (320, 240, 4, 0.95)
        node.last_camera_fix, node.last_camera_bearing = 1.2, math.radians(3)
        b = math.radians(-20)
        node.gate.ambiguous_until = 1.5
        node.scan_points = scan(person(box_range * math.cos(b), box_range * math.sin(b)))
        node.scan_time = 1.3
        node.buf_lidar.append((1.3, [box_range]))
        cx = int(round(320 - 320 / math.tan(math.radians(35)) * math.tan(b)))
        node.try_sync_from_yolo(1.3, cx, 240, 4)
        self.assertEqual(node.last_camera_fix, 1.2)
        self.assertTrue(node.rejected_camera_boxes)
        node.gate.bearing, node.gate.t = math.radians(31), 1.4
        node.now_sec = lambda: 1.8
        node.scan_points = [(math.radians(deg), 0.95) for deg in range(42, 56)]
        node.scan_time = 1.8
        self.assertGreaterEqual(abs(node.gate._predict(1.8)[0]), node.edge_rad)
        before = len(node.published)
        node.track_with_lidar()
        self.assertEqual(len(node.published), before)
        self.assertTrue(node.camera_lidar_conflict)

    def test_conflict_parameters_reject_negative_and_nan(self):
        for name in ('lidar_conflict_centre_deg', 'lidar_conflict_behind_m'):
            for value in (-1.0, float('nan')):
                with self.subTest(parameter=name, value=value):
                    with self.assertRaises(ValueError):
                        make_node(**{name: value})

    def test_rejected_opposite_box_without_lidar_range_blocks_edge_track(self):
        _, node = make_node(box_range_from_scan=True)
        node.gate.accept(0.0, 0.0, 0.95)
        node.gate.accept(1.2, 0.0, 0.95)
        node.gate.bearing, node.gate.range, node.gate.t = math.radians(3), 0.95, 1.2
        node.last_target = (320, 240, 4, 0.95)
        node.last_camera_fix, node.last_camera_bearing = 1.2, math.radians(3)
        b = math.radians(-20)
        node.gate.ambiguous_until = 1.5
        node.scan_points = []
        node.scan_time = 1.3
        node.buf_lidar.append((1.3, [0.95]))
        cx = int(round(320 - 320 / math.tan(math.radians(35)) * math.tan(b)))
        node.try_sync_from_yolo(1.3, cx, 240, 4)
        self.assertEqual(node.last_camera_fix, 1.2)
        self.assertEqual(node.rejected_camera_boxes[0][2], math.inf)
        node.gate.bearing, node.gate.t = math.radians(31), 1.4
        node.now_sec = lambda: 1.8
        node.scan_points = [(math.radians(deg), 0.95) for deg in range(42, 56)]
        node.scan_time = 1.8
        before = len(node.published)
        node.track_with_lidar()
        self.assertEqual(len(node.published), before)
        self.assertTrue(node.camera_lidar_conflict)

    def test_expired_rejected_box_no_longer_blocks_edge_track(self):
        _, node = make_node()
        node.gate.accept(0.0, 0.0, 0.95)
        node.gate.accept(1.2, 0.0, 0.95)
        node.gate.bearing, node.gate.range, node.gate.t = math.radians(3), 0.95, 1.2
        node.last_target = (320, 240, 4, 0.95)
        node.last_camera_fix, node.last_camera_bearing = 1.2, math.radians(3)
        node.rejected_camera_boxes = [(1.3, math.radians(-20), 0.95)]
        self.assertIsNotNone(node.last_camera_fix)
        self.assertGreater(7.0 - node.rejected_camera_boxes[0][0], node.lidar_max)
        self.assertIsNone(node._rejected_box_conflicts(7.0, math.radians(31)))
        self.assertEqual(node.rejected_camera_boxes, [])

    def test_box_just_inside_behind_limit_blocks(self):
        self._assert_opposite_box_blocks_edge_track(2.44)

    def _give_way_node(self, remembered=()):
        """Target at +15 deg / 1.4 m; someone at -8 deg / 0.5 m in the path (rejected, not the occluder)."""
        _, node = make_node()
        node.gate.accept(0.0, 0.0, 0.95)
        node.gate.accept(1.2, 0.0, 0.95)
        tb = math.radians(15)
        node.gate.bearing, node.gate.range, node.gate.t = tb, 1.4, 1.2
        node.gate.bearing_rate = node.gate.range_rate = 0.0
        f = (self.W / 2.0) / math.tan(math.radians(self.HFOV) / 2.0)
        node.last_target = (int(round(self.W / 2.0 - f * math.tan(tb))), 240, 2, 1.4)
        node.last_camera_fix, node.last_camera_bearing = 1.2, tb
        node.rejected_camera_boxes = list(remembered)
        node.gate.ambiguous_until = 2.0
        b = math.radians(-8)
        node.scan_points = scan(person(0.5 * math.cos(b), 0.5 * math.sin(b)))
        node.scan_time = 1.3
        node.buf_lidar.append((1.3, [0.5]))
        before = len(node.published)
        node.try_sync_from_yolo(1.3, int(round(self.W / 2.0 - f * math.tan(b))), 240, 4)
        self.assertEqual(node.last_camera_fix, 1.2)  # rejected
        self.assertIsNotNone(node.path_block)
        self.assertEqual(node.path_block[0], 1.3)  # in the path and nearer than the target
        return node, before

    def test_give_way_is_suppressed_when_remembered_box_conflicts(self):
        # an earlier rejected box strictly opposite to the target's column (auditor P5): fail closed
        node, before = self._give_way_node(remembered=[(1.25, math.radians(-20), 0.9)])
        self.assertEqual(len(node.published), before)
        self.assertTrue(node.camera_lidar_conflict)

    def test_give_way_ignores_the_box_being_handled(self):
        # only the box in the path is remembered: give way as before (T18), no latch
        node, before = self._give_way_node()
        self.assertEqual(len(node.published), before + 1)
        self.assertLess(node.published[-1][2], 1.4)  # the give-way range, nearer than the target
        self.assertFalse(node.camera_lidar_conflict)

    def test_conflict_latch_transitions_are_logged_once(self):
        _, node = make_node()
        node._set_camera_lidar_conflict(True, 'edge', math.radians(20), 0.9, math.radians(30))
        node._set_camera_lidar_conflict(True, 'edge', math.radians(20), 0.9, math.radians(30))
        node._set_camera_lidar_conflict(False)
        node._set_camera_lidar_conflict(False)
        lines = [line for line in node.logs if line.startswith('[CONFLICT]')]
        self.assertEqual([line.split()[1] for line in lines], ['on', 'off'])
        self.assertIn('reason=edge', lines[0])
        self.assertIn('box_bearing=', lines[0])
        self.assertIn('box_range=', lines[0])
        self.assertIn('lidar_bearing=', lines[0])

    def test_assist_distance_rejection_does_not_latch_conflict(self):
        m, node = make_node(lidar_assist=True, lidar_assist_dist_m=0.35,
                            lidar_assist_speed_mps=10.0)
        node.gate.accept(0.0, 0.0, 0.9)
        node.gate.accept(1.2, 0.0, 0.9)
        node.last_target = (320, 240, 4, 0.9)
        node.last_camera_fix, node.last_camera_bearing = 1.2, 0.0
        node.rejected_camera_boxes = [(1.25, math.radians(-20), 0.9)]
        node.now_sec = lambda: 1.3
        node.scan_points = scan(person(1.25 * math.cos(math.radians(20)),
                                       1.25 * math.sin(math.radians(20))))
        node.scan_time = 1.3
        node.assist_scan_time = None
        predicted, pr = node.gate._predict(1.3)
        self.assertTrue(abs(1.3 - node.scan_time) <= node.scan_max_age)
        candidate = m.lidar_track(node.scan_points, predicted, pr,
                                  math.atan2(node.assist_dist, max(pr, 0.3)),
                                  node.assist_dist, width_m=(0.05, 0.8))
        self.assertIsNotNone(candidate)  # eligible cluster; the assist's Euclidean distance filter rejects it
        self.assertIsNone(node.assist_with_lidar())
        self.assertFalse(node.camera_lidar_conflict)

    def test_remembered_opposite_box_blocks_assist_without_advancing_gate(self):
        _, node = make_node(lidar_assist=True)
        node.gate.accept(0.0, 0.0, 0.9)
        node.gate.accept(1.2, 0.0, 0.9)
        node.gate.bearing = math.radians(3.0)
        node.gate.range = 0.9
        node.gate.bearing_rate = node.gate.range_rate = 0.0
        node.gate.t = 1.2
        node.last_target = (320, 240, 4, 0.9)
        node.last_camera_fix = 1.2
        node.last_camera_bearing = math.radians(3.0)
        node.recent_ranges = [(1.2, 0.9)]
        b = math.radians(-20.0)
        node.scan_points = scan(person(0.9 * math.cos(b), 0.9 * math.sin(b)))
        node.scan_time = 1.3
        node.buf_lidar.clear()
        node.buf_lidar.append((1.3, [0.9]))
        cx = int(round(self.W / 2.0 - (self.W / 2.0 / math.tan(math.radians(self.HFOV) / 2.0))
                       * math.tan(b)))
        node.gate.ambiguous_until = 1.35  # plain gate for this frame, as in the bag; over before the assist
        node.try_sync_from_yolo(1.3, cx, 240, 4)
        self.assertEqual(node.last_camera_fix, 1.2)  # rejected
        self.assertFalse(node.camera_lidar_conflict)
        self.assertEqual(len(node.rejected_camera_boxes), 1)
        node.gate.bearing = math.radians(31.0)
        node.gate.range = 0.9
        node.gate.t = 1.4
        node.now_sec = lambda: 1.8
        node.scan_points = scan(person(0.9 * math.cos(math.radians(31.0)),
                                       0.9 * math.sin(math.radians(31.0))))
        node.scan_time = 1.8
        node.assist_scan_time = None
        predicted, pr = node.gate._predict(1.8)
        self.assertGreaterEqual(abs(predicted), node.edge_rad)
        self.assertTrue(abs(1.8 - node.scan_time) <= node.scan_max_age)
        assist_candidate = _load().lidar_track(node.scan_points, predicted, pr,
                                               math.atan2(node.assist_dist, max(pr, 0.3)),
                                               node.assist_dist, width_m=(0.05, 0.8))
        self.assertIsNotNone(assist_candidate)
        before = (node.gate.bearing, node.gate.t)
        self.assertIsNone(node.assist_with_lidar())
        self.assertTrue(node.camera_lidar_conflict)
        self.assertEqual((node.gate.bearing, node.gate.t), before)

    def test_camera_lidar_conflict_stops_edge_track_publication(self):
        _, node = make_node()
        camera_bearing = math.radians(30.0)
        self.assertTrue(node.gate.accept(0.0, 0.0, 0.85, (110, 165)))  # lock-on is only within +-15 deg
        node.last_target = (320, 240, 4, 0.85)
        node.last_camera_fix = 0.0
        node.last_camera_bearing = camera_bearing
        node.recent_ranges = [(0.0, 0.85)]
        # The same fresh static cluster is trackable after the camera timeout and maps to the image edge.
        node.scan_points = [(math.radians(b), 1.0) for b in range(44, 57)]  # 1 deg apart: one 0.2 m cluster
        node.scan_time = 0.4
        node.now_sec = lambda: 0.4
        node.gate.accept_lidar(0.1, math.radians(25.0), 1.0)
        node.gate.accept_lidar(0.2, math.radians(35.0), 1.0)
        predicted_bearing, predicted_range = node.gate._predict(0.4)
        self.assertGreaterEqual(abs(predicted_bearing), node.edge_rad)
        self.assertTrue(node.scan_time is not None and abs(0.4 - node.scan_time) <= node.scan_max_age)
        self.assertGreaterEqual(1.0, max(predicted_range, 0.85) - 0.2)
        clusters = _load().lidar_clusters(node.scan_points)
        self.assertTrue(any(0.15 <= width <= 0.8 and abs(b - predicted_bearing) <= math.radians(25.0)
                            and abs(r - predicted_range) <= 0.5
                            for b, r, width in clusters), clusters)
        node.track_with_lidar()
        self.assertTrue(node.published, 'edge-track precondition should publish before the conflict latch')
        self.assertEqual(node.published[-1][0], 0.0)  # +35 deg is clamped to the left image edge
        node.published.clear()
        # Set the latch through the rejected camera path (opposite side of the predicted edge track).
        node.gate.bearing = math.radians(35.0)
        node.gate.range = 1.0
        node.gate.bearing_rate = 0.0
        node.gate.range_rate = 0.0
        node.gate.t = 0.3
        # the target's own scan returns at the box bearing, so the box has a finite range and reaches the gate
        node.scan_points = scan(person(0.8 * math.cos(math.radians(-30.5)), 0.8 * math.sin(math.radians(-30.5))))
        node.scan_time = 0.4
        node.buf_lidar.clear()
        node.buf_lidar.extend([(0.4, [0.8])])
        cx = int(round(self.W / 2.0 - (self.W / 2.0 / math.tan(math.radians(self.HFOV) / 2.0))
                       * math.tan(math.radians(-30.5))))
        node.try_sync_from_yolo(0.4, cx, 240, 4)
        self.assertTrue(node.camera_lidar_conflict)
        node.published.clear()
        node.track_with_lidar()
        self.assertEqual(node.published, [])

    def test_unlocked_rejection_does_not_predict_without_a_gate_time(self):
        for t in (0.0, 6.0):
            _, node = make_node()
            if t:
                node.gate.accept(t - 6.0, 0.0, 0.8)
                node.gate.accept(t - 5.9, 0.0, 0.8)
            node.scan_points = scan(person(1.3, 0.0))
            node.scan_time = t
            node.buf_lidar.clear()
            node.buf_lidar.extend([(t, [1.3])])
            node.try_sync_from_yolo(t, self.W // 2, 240, 4)
            self.assertFalse(node.gate.locked)

    def test_rejection_after_an_unlock_with_a_recent_camera_fix_does_not_raise(self):
        # lidar_track_max_s longer than unlock_after_s: the box memory must not ask an unlocked gate
        _, node = make_node(lidar_track_max_s=8.0)
        node.gate.accept(0.0, 0.0, 0.8)
        node.gate.accept(0.1, 0.0, 0.8)
        node.last_camera_fix = 0.1
        node.scan_points = scan(person(1.3, 0.0))
        node.scan_time = 6.0
        node.buf_lidar.clear()
        node.buf_lidar.extend([(6.0, [1.3])])
        self.assertLessEqual(6.0 - node.last_camera_fix, node.lidar_max)
        node.try_sync_from_yolo(6.0, self.W // 2, 240, 4)  # 1.3 m: outside the lock window, rejected
        self.assertFalse(node.gate.locked)
        self.assertEqual(node.rejected_camera_boxes, [])

    def test_latched_give_way_publishes_nothing(self):
        _, node = make_node()
        node.gate.accept(0.0, 0.0, 0.8)
        node.gate.accept(0.1, 0.0, 0.8)
        node.last_target = (int(round(self.W / 2.0 - (self.W / 2.0 / math.tan(math.radians(35.0)))
                                      * math.tan(math.radians(23.0)))), 240, 1, 1.4)
        node.last_camera_bearing = math.radians(23.0)
        node.gate.bearing = math.radians(35.0)
        node.gate.range = 1.4
        node.gate.bearing_rate = node.gate.range_rate = 0.0
        node.gate.t = 0.9
        node.camera_lidar_conflict = True
        node.scan_points = scan(person(1.0, 0.0), person(1.4 * math.cos(math.radians(35.0)),
                                                          1.4 * math.sin(math.radians(35.0))))
        node.scan_time = 1.0
        node.buf_lidar.clear()
        node.buf_lidar.extend([(1.0, [1.0])])
        node.try_sync_from_yolo(1.0, self.W // 2, 240, 4)
        self.assertEqual(node.published, [])
        self.assertIsNotNone(node.path_block)  # the person in the way is still remembered for after the latch
        self.assertEqual(node.path_block[0], 1.0)

    def test_assist_does_not_refresh_gate_while_conflict_is_latched(self):
        def ready_node():
            # locked, past the 1 s lock-on ambiguity window, last camera fix 0.3 s ago, and a fresh scan with
            # the target's own cluster slightly ahead of the prediction: the assist would move the track
            _, node = make_node(lidar_assist=True)
            self.assertTrue(node.gate.accept(0.0, 0.0, 0.8))
            self.assertTrue(node.gate.accept(1.2, 0.0, 0.8))
            node.last_camera_fix = 1.2
            node.last_camera_bearing = 0.0
            node.last_target = (320, 240, 4, 0.8)
            node.scan_points = scan(person(0.85, 0.05))
            node.scan_time = 1.5
            node.now_sec = lambda: 1.5
            self.assertGreaterEqual(1.5, node.gate.ambiguous_until)
            return node

        free = ready_node()
        before = (free.gate.bearing, free.gate.t)
        self.assertIsNotNone(free.assist_with_lidar())  # precondition: without the latch the assist acts
        self.assertNotEqual((free.gate.bearing, free.gate.t), before)

        latched = ready_node()
        latched.camera_lidar_conflict = True
        before = (latched.gate.bearing, latched.gate.t)
        self.assertIsNone(latched.assist_with_lidar())
        self.assertEqual((latched.gate.bearing, latched.gate.t), before)

    def test_camera_box_inside_image_beyond_edge_latches(self):
        _, node = make_node()
        node.gate.accept(0.0, 0.0, 0.8)
        node.gate.accept(0.1, 0.0, 0.8)
        node.gate.bearing = math.radians(32.0)
        node.gate.range = 1.0
        node.gate.bearing_rate = node.gate.range_rate = 0.0
        node.gate.t = 0.4
        bearing = math.radians(-30.5)
        node.scan_points = scan(person(0.8 * math.cos(bearing), 0.8 * math.sin(bearing)))  # returns at the box
        node.scan_time = 0.5
        node.buf_lidar.clear()
        node.buf_lidar.extend([(0.5, [0.8])])
        cx = int(round(self.W / 2.0 - (self.W / 2.0 / math.tan(math.radians(self.HFOV) / 2.0))
                       * math.tan(bearing)))
        node.try_sync_from_yolo(0.5, cx, 240, 4)
        self.assertGreater(abs(bearing), node.edge_rad)
        self.assertLess(abs(bearing), math.radians(node.camera_hfov_deg / 2.0))
        self.assertTrue(node.camera_lidar_conflict)

    def frame(self, node, t, people):
        """One camera frame: a fresh scan of everyone, then one box per visible person, in list order."""
        node.scan_points = scan(*(person(x, y) for x, y in people))
        node.scan_time = t
        node.buf_lidar.clear()
        node.buf_lidar.append((t, [1.0]))
        f = (self.W / 2.0) / math.tan(math.radians(self.HFOV) / 2.0)
        out = []
        for k, (x, y) in enumerate(people):
            n = len(node.published)
            cx = int(round(self.W / 2.0 - f * math.tan(math.atan2(y, x))))
            node.try_sync_from_yolo(t + 0.001 * k, cx, 240, 4)
            out.append(len(node.published) > n)
        return out

    def lock(self, node, target=(1.0, 0.0), until=2.0):
        t = 0.0
        while t < until:
            self.assertEqual(self.frame(node, t, [target]), [True])
            t += 0.1
        return t

    def test_a_target_covered_from_the_lidar_keeps_its_predicted_range(self):
        # blind_corner: someone the camera does not detect stands between the robot and the target at the
        # target's bearing; the box range was theirs (0.3 m), and the follower stopped as if at the target
        m, node = make_node()
        t = self.lock(node, target=(1.0, 0.0))
        f = (self.W / 2.0) / math.tan(math.radians(self.HFOV) / 2.0)
        node.scan_points = scan(person(1.0, 0.0), person(0.5, 0.02))
        node.scan_time = t
        node.buf_lidar.clear()
        node.buf_lidar.append((t, [1.0]))
        n = len(node.published)
        node.try_sync_from_yolo(t, int(round(self.W / 2.0)), 240, 4)
        self.assertGreater(len(node.published), n)
        self.assertGreater(node.published[-1][2], 0.7)  # the target's range, not the near person's

    def test_a_stranger_stepping_out_beside_the_target_is_not_taken(self):
        """Same clothes, 0.40 m to the right; the stranger's box comes first in the frame."""
        m, node = make_node()
        t = self.lock(node)
        for _ in range(5):
            stranger, target = self.frame(node, t, [(1.05, -0.40), (1.0, 0.0)])
            self.assertFalse(stranger)
            self.assertTrue(target)
            t += 0.1

    def test_a_stranger_is_not_taken_when_the_targets_box_is_missed(self):
        """The camera misses the target in the frame the stranger appears; the scan still has both."""
        m, node = make_node()
        t = self.lock(node)
        node.scan_points = scan(person(1.05, -0.40), person(1.0, 0.0))
        node.scan_time = t
        node.buf_lidar.clear()
        node.buf_lidar.append((t, [1.0]))
        f = (self.W / 2.0) / math.tan(math.radians(self.HFOV) / 2.0)
        n = len(node.published)
        node.try_sync_from_yolo(t, int(round(self.W / 2.0 - f * math.tan(math.atan2(-0.40, 1.05)))), 240, 4)
        self.assertEqual(len(node.published), n)

    def test_the_target_alone_still_gets_the_wider_gate(self):
        """The traced side_step: the target alone steps 0.25 m sideways between two frames at 0.7 m."""
        m, node = make_node()
        t = self.lock(node, target=(0.9, 0.0))
        self.assertEqual(self.frame(node, t, [(0.9, -0.25)]), [True])

    def test_center_camera_conflict_latches_lidar_track_until_accepted_camera_fix(self):
        m, node = make_node()
        t = self.lock(node, target=(0.9, 0.0))
        # LiDAR-only updates pull the locked track onto a static left-side cluster, beyond the image edge.
        cluster_bearing = math.radians(35.0)
        edge_camera_bearing = math.radians(30.0)
        node.gate.bearing = edge_camera_bearing
        node.gate.bearing_rate = 0.0
        node.gate.accept_lidar(t + 0.1, cluster_bearing, 0.9)
        node.gate.accept_lidar(t + 0.2, cluster_bearing, 0.9)
        node.last_camera_fix = t
        node.last_camera_bearing = edge_camera_bearing
        node.now_sec = lambda: t + 0.4
        node.scan_points = [(0.0, 0.9)] + [
            (math.radians(b), 0.9) for b in range(29, 42)]
        node.scan_time = t + 0.4
        predicted_bearing, predicted_range = node.gate._predict(t + 0.4)
        self.assertGreaterEqual(abs(node.last_camera_bearing), node.edge_rad)
        self.assertGreaterEqual(abs(predicted_bearing), node.edge_rad)
        self.assertTrue(abs((t + 0.4) - node.scan_time) <= node.scan_max_age)
        self.assertGreaterEqual(0.9, max(predicted_range, 0.9) - 0.2)
        clusters = m.lidar_clusters(node.scan_points)
        self.assertTrue(any(0.15 <= width <= 0.8 and abs(b - predicted_bearing) <= math.radians(25.0)
                            and abs(r - predicted_range) <= 0.5
                            for b, r, width in clusters), clusters)
        before = len(node.published)
        node.track_with_lidar()
        self.assertGreater(len(node.published), before)
        self.assertEqual(node.published[-1][0], 0.0)  # +35 deg is clamped to the left image edge

        # A centre box is rejected by the gate and must latch the disagreement.
        node.scan_points = [(0.0, 0.9)] + [
            (math.radians(b), 0.9) for b in range(29, 42)]
        node.scan_time = t + 0.5
        node.buf_lidar.clear()
        node.buf_lidar.append((t + 0.5, [0.9]))
        before = len(node.published)
        node.try_sync_from_yolo(t + 0.5, self.W // 2, 240, 4)
        self.assertTrue(node.camera_lidar_conflict)
        node.now_sec = lambda: t + 0.6
        node.scan_time = t + 0.6
        node.track_with_lidar()
        self.assertEqual(len(node.published), before)

        # A box at the tracked bearing is accepted and clears the latch.
        f = (self.W / 2.0) / math.tan(math.radians(self.HFOV) / 2.0)
        cx = int(round(self.W / 2.0 - f * math.tan(cluster_bearing)))
        node.scan_time = t + 0.7
        node.buf_lidar.clear()
        node.buf_lidar.append((t + 0.7, [0.9]))
        node.try_sync_from_yolo(t + 0.7, cx, 240, 4)
        self.assertFalse(node.camera_lidar_conflict)

    def test_the_scan_check_can_be_turned_off(self):
        m, node = make_node(crowd_from_scan=False)
        t = self.lock(node)
        stranger, _ = self.frame(node, t, [(1.05, -0.40), (1.0, 0.0)])
        self.assertTrue(stranger)  # the gap integration found, as it was

    def test_a_post_near_the_target_leaves_the_wider_gate(self):
        """Twin side_step with realism: a post 0.9 m from where the target steps (T15 follow-up run)."""
        m, node = make_node()
        t = self.lock(node, target=(0.9, 0.0))
        node.scan_points = scan(person(0.9, -0.25), person(1.3, 0.75, radius=0.06))
        node.scan_time = t
        node.buf_lidar.clear()
        node.buf_lidar.append((t, [1.0]))
        f = (self.W / 2.0) / math.tan(math.radians(self.HFOV) / 2.0)
        n = len(node.published)
        node.try_sync_from_yolo(t, int(round(self.W / 2.0 - f * math.tan(math.atan2(-0.25, 0.9)))), 240, 4)
        self.assertEqual(len(node.published), n + 1)

    def test_a_false_box_away_from_the_target_leaves_the_wider_gate(self):
        """Twin side_step with realism: a spurious box on a post must not make the target's own returns a crowd."""
        m, node = make_node()
        t = self.lock(node, target=(0.9, 0.0))
        node.scan_points = scan(person(0.9, 0.0), person(1.5, -0.9, radius=0.06))
        node.scan_time = t
        node.buf_lidar.clear()
        node.buf_lidar.append((t, [1.0]))
        f = (self.W / 2.0) / math.tan(math.radians(self.HFOV) / 2.0)
        node.try_sync_from_yolo(t, int(round(self.W / 2.0 - f * math.tan(math.atan2(-0.9, 1.5)))), 240, 4)
        self.assertEqual(self.frame(node, t + 0.1, [(0.9, -0.25)]), [True])

    def test_a_late_box_on_the_target_stepping_aside_is_not_a_crowd(self):
        """Twin realism: the box is 0.15 s behind the scan, so it lags the target's own returns by 0.3 m."""
        m, _ = make_node()
        target_now = person(1.0, -0.30)
        self.assertFalse(m.scan_crowded(scan(target_now), 0.0, 0.8, 0.0, 0.8, 0.5))
        self.assertTrue(m.scan_crowded(scan(target_now, person(1.05, 0.12)), 0.0, 0.8, 0.0, 0.8, 0.5))

    def stale_frame(self, node, t, scan_time, people=((1.05, -0.40), (1.0, 0.0))):
        """One frame with no fresh scan: the scan is old, missing or dated ahead, the sector ranges are current."""
        node.scan_points = scan(*(person(x, y) for x, y in people))
        node.scan_time = scan_time
        node.lidar_angles = [math.atan2(y, x) for x, y in people]
        node.buf_lidar.clear()
        node.buf_lidar.append((t, [math.hypot(x, y) - 0.2 for x, y in people]))
        f = (self.W / 2.0) / math.tan(math.radians(self.HFOV) / 2.0)
        out = []
        for k, (x, y) in enumerate(people):
            n = len(node.published)
            node.try_sync_from_yolo(t + 0.001 * k, int(round(self.W / 2.0 - f * math.tan(math.atan2(y, x)))), 240, 4)
            out.append(len(node.published) > n)
        return out

    def test_without_a_fresh_scan_the_stranger_is_not_taken(self):
        """Codex (T15): stale, missing or future-dated scan; the stranger's box first, sector ranges current."""
        for label, age in (('stale', -0.5), ('missing', None), ('future', 0.5)):
            with self.subTest(scan=label):
                m, node = make_node()
                t = self.lock(node)
                stranger, target = self.stale_frame(node, t, None if age is None else t + age)
                self.assertFalse(stranger)
                self.assertTrue(target)

    def test_without_a_fresh_scan_the_check_off_keeps_the_round_2_behaviour(self):
        m, node = make_node(crowd_from_scan=False)
        t = self.lock(node)
        stranger, _ = self.stale_frame(node, t, t - 0.5)
        self.assertTrue(stranger)

    def test_the_wider_gate_returns_with_a_fresh_scan_of_the_target_alone(self):
        m, node = make_node()
        t = self.lock(node, target=(0.9, 0.0))
        for _ in range(3):  # the LiDAR stalls for a few frames with the target alone
            self.assertEqual(self.stale_frame(node, t, t - 0.5, people=((0.9, 0.0),)), [True])
            t += 0.1
        node.lidar_angles = [0.0]
        t += 1.0  # past ambiguity_window_s
        self.assertEqual(self.frame(node, t, [(0.9, 0.0)]), [True])
        self.assertEqual(self.frame(node, t + 0.1, [(0.9, -0.25)]), [True])  # the side step needs the wider gate

    def test_crowd_changes_are_logged_once_each(self):
        """Robot day E4b reads these lines: on with a reason when the plain gate is forced, off when it ends."""
        m, node = make_node()
        t = self.lock(node)
        t += 1.0  # past the lock-on window
        self.frame(node, t, [(1.0, 0.0)])
        for k in range(3):
            self.frame(node, t + 0.1 * (k + 1), [(1.05, -0.40), (1.0, 0.0)])
        self.frame(node, t + 2.0, [(1.0, 0.0)])
        crowd = [line for line in node.logs if line.startswith('[CROWD]')]
        self.assertEqual([line.split()[1] for line in crowd], ['on', 'off', 'on', 'off'])
        self.assertIn('reason=scan', crowd[2])

    def test_giving_way_holds_at_the_follow_distance_instead_of_backing_off(self):
        # pass_by s0 on 5cfb21b: a worker's box 0.57 m out in the path published the target at 0.17 m and the
        # controller reversed at 0.5 m/s
        m, node = make_node()
        t = self.lock(node, target=(1.0, 0.0))
        t += 1.0
        for k in range(10):
            self.frame(node, t + 0.1 * k, [(1.0 + 0.05 * k, 0.0)])
        t += 1.0
        self.frame(node, t, [(0.57, 0.15), (1.5, 0.0)])
        self.assertGreaterEqual(min(p[2] for p in node.published[-2:]), 0.5)

    def test_without_the_obstacle_stop_the_near_range_holds_the_robot_off(self):
        # T18 re-review (Codex 2026-11-01 07:49, item 2): the occlusion range and the give-way floor rely on the
        # LiDAR stop; with obstacle_stop false they are off and the near person's range is published again
        m, node = make_node(obstacle_stop=False)
        self.assertEqual((node.occl_gap, node.path_floor), (0.0, 0.0))
        t = self.lock(node, target=(1.0, 0.0))
        node.scan_points = scan(person(1.0, 0.0), person(0.5, 0.02))
        node.scan_time = t
        node.buf_lidar.clear()
        node.buf_lidar.append((t, [1.0]))
        node.try_sync_from_yolo(t, int(round(self.W / 2.0)), 240, 4)
        self.assertLess(node.published[-1][2], 0.5)  # the covering person's range, as before the LiDAR stop
        m, node = make_node()
        self.assertEqual((node.occl_gap, node.path_floor), (0.4, 0.5))

    def test_a_crop_row_beside_the_target_does_not_count_as_a_person(self):
        m, _ = make_node()
        # plants 0.1 m apart, 0.45 m right: inside the 0.5 m radius, so only the 1.5 m width rule leaves it out
        row = [p for k in range(40) for p in person(0.1 * k, -0.45, radius=0.05)]
        self.assertFalse(m.scan_crowded(scan(row, person(1.0, 0.0)), 0.0, 0.8, 0.0, 0.8, 0.5))
        self.assertTrue(m.scan_crowded(scan(row, person(1.0, 0.0)), 0.0, 0.8, 0.0, 0.8, 0.5, max_width_m=100.0))
        self.assertTrue(m.scan_crowded(scan(person(1.05, -0.40), person(1.0, 0.0)), 0.0, 0.8, 0.0, 0.8, 0.5))


if __name__ == "__main__":
    unittest.main()


class LidarAssistTest(unittest.TestCase):
    """The target's own LiDAR cluster moves the track between camera frames (twin side_step failures)."""
    W, HFOV = WalkUpTest.W, WalkUpTest.HFOV
    frame, lock = WalkUpTest.frame, WalkUpTest.lock

    def scan_at(self, node, t, people):
        node.scan_points = scan(*(person(x, y) for x, y in people))
        node.scan_time = t
        node.now_sec = lambda: t
        node.on_track_timer()

    def box(self, node, t, x, y):
        f = (self.W / 2.0) / math.tan(math.radians(self.HFOV) / 2.0)
        node.scan_time = t
        node.buf_lidar.clear()
        node.buf_lidar.append((t, [1.0]))
        n = len(node.published)
        node.try_sync_from_yolo(t, int(round(self.W / 2.0 - f * math.tan(math.atan2(y, x)))), 240, 4)
        return len(node.published) > n

    def test_a_nearer_person_at_the_edge_is_not_taken_as_the_target(self):
        # blind_corner s4 on bddf0ba: the target left the image past someone standing nearer; the LiDAR
        # track took that person, the gate followed them and the camera's target was refused for 4 s
        m, node = make_node()
        t = self.lock(node, target=(0.9, 0.0))
        node.scan_points = scan(person(0.9, -0.33))
        self.assertTrue(self.box(node, t, 0.9, -0.33))
        before = len(node.published)
        for k in range(1, 5):  # the target is hidden behind the nearer person
            self.scan_at(node, t + 0.1 * k, [(0.45, -0.25)])
        for k in range(5, 9):  # then comes out beyond them, still out of the image
            self.scan_at(node, t + 0.1 * k, [(0.45, -0.25), (0.55, -0.85)])
        out = node.published[before:]
        self.assertEqual([p for p in out if p[2] < 0.7], [])
        self.assertTrue(any(p[0] == node.image_width - 1 and p[2] > 0.7 for p in out))  # turned towards it

    def test_a_target_that_walks_behind_someone_and_out_of_view_is_followed_with_the_lidar(self):
        # blind_corner s2 on 1ba6ff8: last seen at 11 deg, then covered by the bystander, then out on the far
        # side beyond the image; it was never last seen near the edge, so nothing was published for 6 s
        m, node = make_node()
        t = self.lock(node, target=(1.0, 0.0))
        node.scan_points = scan(person(1.0, 0.2))
        self.assertTrue(self.box(node, t, 1.0, 0.2))
        before = len(node.published)
        for k in range(1, 4):  # covered
            self.scan_at(node, t + 0.1 * k, [(0.6, 0.12), (1.0, 0.2 + 0.03 * k)])
        for k in range(4, 9):  # out beyond the bystander, outside the image; the robot creeping on, the
            # bystander no longer covers the bearing the target was last seen at (blind_corner s3 on a30c90d)
            self.scan_at(node, t + 0.1 * k, [(0.55, 0.12 - 0.08 * k), (0.75, 0.4 + 0.12 * k)])
        out = node.published[before:]
        self.assertTrue(any(p[0] == 0 and p[2] > 0.8 for p in out))  # turned left, at the target's range
        self.assertEqual([p for p in out if p[2] < 0.7], [])

    def test_a_target_walking_away_out_of_view_is_found_again_further_out(self):
        # blind_corner s2 on 1b5dc92: unseen 1 s, the prediction held 0.95 m while the target walked on to 1.4 m,
        # outside the 0.5 m range window, and the LiDAR never found it
        m, node = make_node()
        t = self.lock(node, target=(0.9, 0.0))
        node.scan_points = scan(person(0.9, -0.33))
        self.assertTrue(self.box(node, t, 0.9, -0.33))
        before = len(node.published)
        for k in range(1, 6):  # nothing there for 0.5 s (behind something the scan does not show)
            self.scan_at(node, t + 0.1 * k, [])
        for k in range(6, 15):
            self.scan_at(node, t + 0.1 * k, [(0.7 + 0.1 * k, -1.2)])
        self.assertTrue(any(p[0] > node.image_width / 2 and p[2] > 1.3 for p in node.published[before:]))  # right, further out

    def test_a_covered_target_inside_the_image_is_given_at_its_own_column(self):
        # blind_corner s1 on e80a83d: found by the LiDAR at 6 deg behind the bystander and sent to the image
        # edge, the robot spun at full rate past it
        m, node = make_node()
        t = self.lock(node, target=(1.0, 0.0))
        node.scan_points = scan(person(1.0, 0.2))
        self.assertTrue(self.box(node, t, 1.0, 0.2))
        before = len(node.published)
        for k in range(1, 9):
            self.scan_at(node, t + 0.1 * k, [(0.6, 0.0), (1.0, 0.5)])
        out = node.published[before:]
        self.assertTrue(out)
        self.assertTrue(all(0 < p[0] < node.image_width / 2 for p in out))  # left of centre, not at the edge

    def test_a_box_range_shortened_by_someone_in_front_does_not_lower_the_floor(self):
        # blind_corner s0 on 47109fb: the last box read 0.50 m off the bystander's edge (target 0.78 m), and the
        # LiDAR track then took the bystander at 0.31 m
        m, node = make_node()
        t = self.lock(node, target=(0.9, 0.0))
        node.scan_points = scan(person(0.9, -0.33))
        self.assertTrue(self.box(node, t, 0.9, -0.33))
        node.scan_points = scan(person(0.9, -0.33), person(0.62, -0.42))  # someone stepping in front
        self.box(node, t + 0.05, 0.9, -0.33)
        before = len(node.published)
        for k in range(1, 9):
            self.scan_at(node, t + 0.05 + 0.1 * k, [(0.45, -0.45)])
        self.assertEqual([p for p in node.published[before:] if p[2] < 0.6], [])

    def side_step(self, **params):
        """The traced twin failure: the last box is at 20 deg, then the target steps out of the image."""
        m, node = make_node(**params)
        t = self.lock(node, target=(0.9, 0.0))
        node.scan_points = scan(person(0.9, -0.33))
        self.assertTrue(self.box(node, t, 0.9, -0.33))  # 20 deg: inside the image, not near its edge
        for k in range(1, 9):  # on to 45 deg and beyond, seen only by the LiDAR
            self.scan_at(node, t + 0.1 * k, [(0.9, -0.33 - 0.08 * k)])
        return [p for p in node.published if p[0] == node.image_width - 1]  # turn-right commands at the edge

    def test_a_target_stepping_out_of_view_is_followed_with_the_lidar(self):
        self.assertTrue(self.side_step())

    def test_a_passer_by_covering_the_target_does_not_move_the_track(self):
        # twin crossing run: someone walks between the robot and the target, so the LiDAR sees only them,
        # 0.3 m nearer than the target was 0.1 s before
        m, node = make_node()
        t = self.lock(node, target=(0.95, 0.0))
        before = (node.gate.bearing, node.gate.range)
        self.scan_at(node, t + 0.1, [(0.62, 0.05)])
        self.assertAlmostEqual(node.gate.bearing, before[0], places=6)
        self.assertAlmostEqual(node.gate.range, before[1], places=6)

    def test_no_assist_while_someone_was_just_near_the_target(self):
        # twin crossing s2: the crosser lent their range to the target's box, then walked off sideways; the
        # assist followed their cluster. After a crowd flag the camera decides alone for the window.
        m, node = make_node()
        t = self.lock(node, target=(0.95, 0.0))
        node.gate.note_crowded(t)
        before = (node.gate.bearing, node.gate.range)
        self.scan_at(node, t + 0.1, [(0.95, -0.06)])  # a cluster the assist would otherwise take
        self.assertAlmostEqual(node.gate.bearing, before[0], places=6)
        self.assertAlmostEqual(node.gate.range, before[1], places=6)

    def test_a_stranger_beside_the_target_does_not_move_the_track(self):
        m, node = make_node()
        t = self.lock(node)
        before = (node.gate.bearing, node.gate.range)
        self.scan_at(node, t + 0.1, [(1.0, 0.0), (1.05, -0.40)])
        self.assertAlmostEqual(node.gate.bearing, before[0], places=6)
        self.assertAlmostEqual(node.gate.range, before[1], places=6)

    def test_a_post_away_from_the_prediction_is_not_taken(self):
        m, node = make_node()
        t = self.lock(node)
        before = node.gate.bearing
        self.scan_at(node, t + 0.1, [(1.45, -0.3)])  # the target gone from the scan, a post 0.5 m off
        self.assertAlmostEqual(node.gate.bearing, before, places=6)
