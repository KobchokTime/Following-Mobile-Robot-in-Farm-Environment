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

    def test_a_crop_row_beside_the_target_does_not_count_as_a_person(self):
        m, _ = make_node()
        # plants 0.1 m apart, 0.45 m right: inside the 0.5 m radius, so only the 1.5 m width rule leaves it out
        row = [p for k in range(40) for p in person(0.1 * k, -0.45, radius=0.05)]
        self.assertFalse(m.scan_crowded(scan(row, person(1.0, 0.0)), 0.0, 0.8, 0.0, 0.8, 0.5))
        self.assertTrue(m.scan_crowded(scan(row, person(1.0, 0.0)), 0.0, 0.8, 0.0, 0.8, 0.5, max_width_m=100.0))
        self.assertTrue(m.scan_crowded(scan(person(1.05, -0.40), person(1.0, 0.0)), 0.0, 0.8, 0.0, 0.8, 0.5))


if __name__ == "__main__":
    unittest.main()
