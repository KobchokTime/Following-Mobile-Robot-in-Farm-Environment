"""follow_stop stops when target messages stop, in sector mode too (T22: a latched fusion goes quiet)."""

import unittest

from test_follow_stop_early_turn import _Float32MultiArray, _load_follow_stop

M = _load_follow_stop()


class _T:
    def __init__(self, ns):
        self.nanoseconds = ns

    def __sub__(self, other):
        return _T(self.nanoseconds - other.nanoseconds)


class _SettableClock:
    def __init__(self):
        self.ns = 0

    def now(self):
        return _T(self.ns)


class SectorStaleStopTest(unittest.TestCase):
    def test_sector_mode_publishes_a_stop_once_target_messages_stop(self):
        node = M.FollowStopNode()
        self.assertEqual(node.steer_mode, "sector")
        self.assertGreater(node.target_timeout, 0.0)
        clock = _SettableClock()
        node.get_clock = lambda: clock
        msg = _Float32MultiArray()
        msg.data = [320.0, 240.0, 0.8, 4.0, 0.9, 0.9, 0.9, 10.0]
        node.cb_fused(msg)
        published = len(node.pub.messages)

        clock.ns = int(0.1 * 1e9)  # still fresh: no stop
        node.check_stale()
        self.assertFalse(node.stale_stopped)
        self.assertEqual(len(node.pub.messages), published)

        clock.ns = int((node.target_timeout + 0.1) * 1e9)  # quiet longer than the timeout: explicit zero
        node.check_stale()
        self.assertTrue(node.stale_stopped)
        stop = node.pub.messages[-1]
        self.assertEqual((stop.linear.x, stop.angular.z), (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
