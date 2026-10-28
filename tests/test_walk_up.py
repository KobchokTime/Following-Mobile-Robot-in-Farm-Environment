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
        return types.SimpleNamespace(info=lambda *a: None, debug=lambda *a: None)

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

    def test_a_crop_row_beside_the_target_does_not_count_as_a_person(self):
        m, _ = make_node()
        row = [p for k in range(40) for p in person(0.1 * k, -0.6, radius=0.05)]  # plants 0.1 m apart, 0.6 m right
        self.assertFalse(m.scan_crowded(scan(row, person(1.0, 0.0)), 0.0, 0.8, 0.0, 0.8, 1.0))
        self.assertTrue(m.scan_crowded(scan(person(1.05, -0.40), person(1.0, 0.0)), 0.0, 0.8, 0.0, 0.8, 1.0))


if __name__ == "__main__":
    unittest.main()
