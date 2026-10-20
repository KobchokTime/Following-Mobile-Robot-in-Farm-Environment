#!/usr/bin/env python3
import rclpy, math, time
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Int32, Int32MultiArray, Float32MultiArray
from geometry_msgs.msg import Point

CENTROID_TOPIC = '/target_centroid'
SCAN_TOPIC = '/scan'

class FollowStop(Node):
    def __init__(self):
        super().__init__('follow_stop_node')

        # ---- params ----
        self.declare_parameter('stop_dist', 1.2)
        self.declare_parameter('slow_dist', 2.5)
        self.declare_parameter('v_max', 0.6)
        self.declare_parameter('w_max', 1.2)
        self.declare_parameter('kx', 0.0018)           # ปรับตามสเกล cx
        self.declare_parameter('vx_gain', 0.6)
        self.declare_parameter('front_span_deg', 12.0)
        self.declare_parameter('target_timeout', 0.8)

        # ---- state ----
        self.front_min = None
        self.last_target_t = 0.0
        self.cx = None

        # ---- pubs/subs ----
        self.pub_cmd = self.create_publisher(Twist, '/cmd_vel', 10)

        # ใช้ QoS แบบ sensor data เพื่อให้เข้ากับไดรเวอร์ LiDAR (BEST_EFFORT)
        self.sub_scan = self.create_subscription(
            LaserScan, SCAN_TOPIC, self.cb_scan, qos_profile_sensor_data
        )

        # สมัครเฉพาะชนิดเดียวที่ตรงกับ publisher ของ /target_centroid
        self._subscribe_centroid_autotype()

        self.timer = self.create_timer(0.05, self.control_loop)  # 20 Hz
        self.get_logger().info('FollowStop started: /scan + /target_centroid -> /cmd_vel')

    # ---------- auto-detect subscriber ----------
    def _subscribe_centroid_autotype(self, wait_sec: float = 5.0):
        end = time.time() + wait_sec
        chosen = None
        while time.time() < end and rclpy.ok():
            for name, types in self.get_topic_names_and_types():
                if name == CENTROID_TOPIC and types:
                    chosen = types[0]
                    break
            if chosen:
                break
            time.sleep(0.1)

        if not chosen:
            # ถ้ายังไม่พบ topic ตอนเริ่ม ให้เดาส่งเป็น Float32MultiArray ไปก่อน
            self.get_logger().warn(f'{CENTROID_TOPIC} not found yet, default to std_msgs/msg/Float32MultiArray')
            self.sub_centroid = self.create_subscription(Float32MultiArray, CENTROID_TOPIC, self.cb_centroid_arr, 10)
            return

        self.get_logger().info(f'{CENTROID_TOPIC} type detected: {chosen}')
        if 'std_msgs/msg/Int32' in chosen:
            self.sub_centroid = self.create_subscription(Int32, CENTROID_TOPIC, self.cb_centroid_int, 10)
        elif 'std_msgs/msg/Int32MultiArray' in chosen:
            self.sub_centroid = self.create_subscription(Int32MultiArray, CENTROID_TOPIC, self.cb_centroid_iarr, 10)
        elif 'geometry_msgs/msg/Point' in chosen:
            self.sub_centroid = self.create_subscription(Point, CENTROID_TOPIC, self.cb_centroid_pt, 10)
        else:
            # รวมถึง std_msgs/msg/Float32MultiArray
            self.sub_centroid = self.create_subscription(Float32MultiArray, CENTROID_TOPIC, self.cb_centroid_arr, 10)

    # ---------- callbacks ----------
    def cb_scan(self, msg: LaserScan):
        half = math.radians(self.get_parameter('front_span_deg').value)
        ang_min, inc, n = msg.angle_min, msg.angle_increment, len(msg.ranges)
        center = round((0.0 - ang_min)/inc)
        span = round(half/inc)
        i0, i1 = max(0, center - span), min(n - 1, center + span)
        vals = [r for r in msg.ranges[i0:i1+1] if math.isfinite(r)]
        self.front_min = min(vals) if vals else None

    def _mark_target_seen(self, x):
        self.cx = float(x)
        self.last_target_t = time.time()

    def cb_centroid_int(self, msg: Int32):
        self._mark_target_seen(msg.data)

    def cb_centroid_iarr(self, msg: Int32MultiArray):
        if len(msg.data) >= 1:
            self._mark_target_seen(msg.data[0])

    def cb_centroid_arr(self, msg: Float32MultiArray):
        if len(msg.data) >= 1:
            self._mark_target_seen(msg.data[0])

    def cb_centroid_pt(self, msg: Point):
        self._mark_target_seen(msg.x)

    # ---------- control ----------
    def control_loop(self):
        now = time.time()
        stop_dist = self.get_parameter('stop_dist').value
        slow_dist = self.get_parameter('slow_dist').value
        v_max = self.get_parameter('v_max').value
        w_max = self.get_parameter('w_max').value
        kx = self.get_parameter('kx').value
        vx_gain = self.get_parameter('vx_gain').value
        timeout = self.get_parameter('target_timeout').value

        cmd = Twist()

        if self.front_min is None or (now - self.last_target_t) > timeout:
            self.pub_cmd.publish(cmd)
            return

        if self.front_min <= stop_dist:
            self.pub_cmd.publish(cmd)
            return

        # linear speed (proportional + slow zone)
        if self.front_min < slow_dist:
            v = vx_gain * (self.front_min - stop_dist) / max(1e-3, (slow_dist - stop_dist)) * v_max
        else:
            v = v_max
        v = max(0.0, min(v, v_max))

        # angular speed from centroid x offset
        w = -kx * (self.cx if self.cx is not None else 0.0)
        w = max(-w_max, min(w, w_max))

        cmd.linear.x = v
        cmd.angular.z = w
        self.pub_cmd.publish(cmd)

def main():
    rclpy.init()
    node = FollowStop()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

