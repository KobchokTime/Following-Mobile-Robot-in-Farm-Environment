import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "ros2_yolo_ws" / "scripts" / "MAIN" / "Sim" / "follow_stop_node_sim.py"


class _Duration:
    def __init__(self, nanoseconds):
        self.nanoseconds = nanoseconds


class _Time:
    def __init__(self, seconds=0.0):
        self.nanoseconds = int(seconds * 1e9)

    def __sub__(self, other):
        return _Duration(self.nanoseconds - other.nanoseconds)


class _Clock:
    def __init__(self):
        self.seconds = 0.0

    def now(self):
        return _Time(self.seconds)


class _Publisher:
    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


class _Logger:
    def info(self, _message):
        pass


class _Parameter:
    def __init__(self, value):
        self.value = value


class _Node:
    def __init__(self, _name):
        self._parameters = {}
        self._clock = _Clock()
        self._publisher = _Publisher()

    def declare_parameter(self, name, default):
        self._parameters[name] = default

    def get_parameter(self, name):
        return _Parameter(self._parameters[name])

    def create_subscription(self, *_args):
        return object()

    def create_publisher(self, *_args):
        return self._publisher

    def get_clock(self):
        return self._clock

    def get_logger(self):
        return _Logger()


class _Vector:
    def __init__(self):
        self.x = self.y = self.z = 0.0


class _Twist:
    def __init__(self):
        self.linear = _Vector()
        self.angular = _Vector()


class _Float32MultiArray:
    def __init__(self, data=None):
        self.data = list(data or [])


def _load_controller():
    rclpy = types.ModuleType("rclpy")
    rclpy_node = types.ModuleType("rclpy.node")
    rclpy_node.Node = _Node
    rclpy.node = rclpy_node
    geometry_msgs = types.ModuleType("geometry_msgs")
    geometry_msgs_msg = types.ModuleType("geometry_msgs.msg")
    geometry_msgs_msg.Twist = _Twist
    geometry_msgs.msg = geometry_msgs_msg
    std_msgs = types.ModuleType("std_msgs")
    std_msgs_msg = types.ModuleType("std_msgs.msg")
    std_msgs_msg.Float32MultiArray = _Float32MultiArray
    std_msgs.msg = std_msgs_msg
    modules = {
        "rclpy": rclpy,
        "rclpy.node": rclpy_node,
        "geometry_msgs": geometry_msgs,
        "geometry_msgs.msg": geometry_msgs_msg,
        "std_msgs": std_msgs,
        "std_msgs.msg": std_msgs_msg,
    }
    previous = {name: sys.modules.get(name) for name in modules}
    sys.modules.update(modules)
    try:
        spec = importlib.util.spec_from_file_location("recovered_follow_controller", CONTROLLER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, old in previous.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


class ControllerSimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_controller()

    def setUp(self):
        self.node = self.module.FollowStopNode()

    def send(self, cx, distance, confidence):
        message = _Float32MultiArray(
            [cx, 240.0, distance, 4.0, 0.9, 0.9, confidence, 20.0]
        )
        self.node.cb_fused(message)
        return self.node.pub.messages[-1]

    def test_waits_and_stops_when_initial_target_is_too_far(self):
        command = self.send(320.0, 1.5, 0.9)
        self.assertFalse(self.node.initialized)
        self.assertEqual(command.linear.x, 0.0)
        self.assertEqual(command.angular.z, 0.0)

    def test_moves_forward_for_confident_centered_target(self):
        command = self.send(320.0, 0.8, 0.9)
        self.assertTrue(self.node.initialized)
        self.assertGreater(command.linear.x, 0.0)
        self.assertEqual(command.angular.z, 0.0)
        self.assertLessEqual(command.linear.x, self.node.max_linear_speed)

    def test_turns_toward_off_center_target(self):
        self.send(320.0, 0.8, 0.9)
        self.send(40.0, 0.8, 0.9)
        command = self.send(40.0, 0.8, 0.9)
        self.assertNotEqual(command.angular.z, 0.0)
        self.assertLessEqual(abs(command.angular.z), self.node.angular_limit)


if __name__ == "__main__":
    unittest.main()
