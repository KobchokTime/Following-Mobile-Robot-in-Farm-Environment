"""Early-turn controller test, from Codex's Arena 1 entry (52edffb). The LiDAR index-order test
was dropped because this version matches sectors by bearing instead of reversing the order."""
import importlib.util
import math
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SECTORIZER = ROOT / "ros2_yolo_ws" / "scripts" / "Lidar" / "lidar_sectorizer_node.py"
FOLLOW_STOP = ROOT / "ros2_yolo_ws" / "scripts" / "MAIN" / "Control" / "follow_stop_node.py"


class _Parameter:
    def __init__(self, value):
        self.value = value


class _Publisher:
    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


class _Logger:
    def info(self, _message):
        pass


class _Time:
    nanoseconds = 0

    def __sub__(self, _other):
        return _Time()


class _Clock:
    def now(self):
        return _Time()


class _Node:
    def __init__(self, _name):
        self.parameters = {}
        self.publishers = {}

    def declare_parameter(self, name, default):
        self.parameters[name] = default

    def get_parameter(self, name):
        return _Parameter(self.parameters[name])

    def create_subscription(self, *_args):
        return object()

    def create_publisher(self, _message_type, topic, _qos):
        publisher = _Publisher()
        self.publishers[topic] = publisher
        return publisher

    def get_logger(self):
        return _Logger()

    def get_clock(self):
        return _Clock()


class _LaserScan:
    def __init__(self, ranges):
        self.angle_min = -math.pi
        self.angle_max = math.pi
        self.range_min = 0.05
        self.range_max = 12.0
        self.ranges = ranges


class _Float32MultiArray:
    def __init__(self):
        self.data = []


class _Vector:
    def __init__(self):
        self.x = self.y = self.z = 0.0


class _Twist:
    def __init__(self):
        self.linear = _Vector()
        self.angular = _Vector()


def _ros_stubs(include_twist=False):
    rclpy = types.ModuleType("rclpy")
    rclpy_node = types.ModuleType("rclpy.node")
    rclpy_node.Node = _Node
    rclpy.node = rclpy_node
    rclpy_qos = types.ModuleType("rclpy.qos")
    rclpy_qos.qos_profile_sensor_data = object()
    sensor_msgs = types.ModuleType("sensor_msgs")
    sensor_msgs_msg = types.ModuleType("sensor_msgs.msg")
    sensor_msgs_msg.LaserScan = _LaserScan
    sensor_msgs.msg = sensor_msgs_msg
    std_msgs = types.ModuleType("std_msgs")
    std_msgs_msg = types.ModuleType("std_msgs.msg")
    std_msgs_msg.Float32MultiArray = _Float32MultiArray
    std_msgs.msg = std_msgs_msg
    modules = {
        "rclpy": rclpy,
        "rclpy.node": rclpy_node,
        "rclpy.qos": rclpy_qos,
        "sensor_msgs": sensor_msgs,
        "sensor_msgs.msg": sensor_msgs_msg,
        "std_msgs": std_msgs,
        "std_msgs.msg": std_msgs_msg,
    }
    if include_twist:
        geometry_msgs = types.ModuleType("geometry_msgs")
        geometry_msgs_msg = types.ModuleType("geometry_msgs.msg")
        geometry_msgs_msg.Twist = _Twist
        geometry_msgs.msg = geometry_msgs_msg
        modules["geometry_msgs"] = geometry_msgs
        modules["geometry_msgs.msg"] = geometry_msgs_msg
    return modules


def _load_node(path, module_name, include_twist=False):
    modules = _ros_stubs(include_twist)
    previous = {name: sys.modules.get(name) for name in modules}
    sys.modules.update(modules)
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, old in previous.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


def _load_sectorizer():
    return _load_node(SECTORIZER, "arena_lidar_sectorizer")


def _load_follow_stop():
    return _load_node(FOLLOW_STOP, "arena_follow_stop", include_twist=True)


class FollowStopEarlyTurnTests(unittest.TestCase):
    def test_controller_turns_before_edge_confidence_drops(self):
        node = _load_follow_stop().FollowStopNode()
        publisher = node.pub

        def send(sector):
            message = _Float32MultiArray()
            message.data = [320.0, 240.0, 0.8, float(sector), 0.9, 0.9, 0.9, 10.0]
            node.cb_fused(message)
            return publisher.messages[-1]

        node.cb_scan(_LaserScan([math.inf] * 360))  # a fresh, empty scan: turning in place is allowed
        send(4)
        node.cb_scan(_LaserScan([math.inf] * 360))
        self.assertGreater(send(2).angular.z, 0.0)


if __name__ == "__main__":
    unittest.main()
