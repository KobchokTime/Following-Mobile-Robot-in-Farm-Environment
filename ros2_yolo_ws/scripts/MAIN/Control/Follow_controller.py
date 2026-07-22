#!/usr/bin/env python3
import time
import math

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from std_msgs.msg import Float32


class FollowController(Node):
    def __init__(self):
        super().__init__('follow_controller')

        # ========== PARAMS ปรับได้ ==========
        # ระยะที่อยากให้ตาม (เมตร)
        self.declare_parameter('dist_min', 0.5)
        self.declare_parameter('dist_max', 1.0)
        self.declare_parameter('k_linear', 0.8)      # gain linear
        self.declare_parameter('k_angular', 1.2)     # gain angular

        self.declare_parameter('max_linear', 0.6)    # m/s
        self.declare_parameter('max_angular', 1.2)   # rad/s

        # confidence threshold
        self.declare_parameter('conf_stop', 0.3)     # ต่ำกว่านี้ = STOP
        self.declare_parameter('conf_hold', 0.6)     # ระหว่าง stop–hold = HOLD

        # timeout ถ้าไม่มีข้อมูลใหม่
        self.declare_parameter('timeout_sec', 0.5)

        # อ่านค่า param
        self.dist_min     = self.get_parameter('dist_min').get_parameter_value().double_value
        self.dist_max     = self.get_parameter('dist_max').get_parameter_value().double_value
        self.k_linear     = self.get_parameter('k_linear').get_parameter_value().double_value
        self.k_angular    = self.get_parameter('k_angular').get_parameter_value().double_value
        self.max_linear   = self.get_parameter('max_linear').get_parameter_value().double_value
        self.max_angular  = self.get_parameter('max_angular').get_parameter_value().double_value
        self.conf_stop    = self.get_parameter('conf_stop').get_parameter_value().double_value
        self.conf_hold    = self.get_parameter('conf_hold').get_parameter_value().double_value
        self.timeout_sec  = self.get_parameter('timeout_sec').get_parameter_value().double_value

        # ========== STATE ==========
        self.target_dist = None       # m
        self.target_offs = None       # หน่วยแล้วแต่ fused node (สมมติเป็น rad หรือนอร์มัลไลซ์ -1..1)
        self.target_conf = 0.0

        self.last_update_time = 0.0
        self.last_cmd = Twist()

        # state: 'STOP', 'HOLD', 'FOLLOW'
        self.mode = 'STOP'

        # ========== SUB / PUB ==========
        # *** ตรงนี้ถ้าชื่อ topic จริงของเจ้าต่างไป ให้แก้เอาเองนะ ***
        self.sub_dist = self.create_subscription(
            Float32, '/target_distance', self.cb_distance, 10)

        self.sub_offs = self.create_subscription(
            Float32, '/target_offset', self.cb_offset, 10)

        self.sub_conf = self.create_subscription(
            Float32, '/target_confidence', self.cb_confidence, 10)

        self.pub_cmd = self.create_publisher(
            Twist, '/cmd_vel', 10)

        # timer คอยเช็คและส่งคำสั่งทุก 50 ms
        self.timer = self.create_timer(0.05, self.update_control)

        self.get_logger().info("✅ FollowController started (sub: /target_distance, /target_offset, /target_confidence → pub: /cmd_vel)")

    # ---------- Callbacks ----------
    def cb_distance(self, msg: Float32):
        self.target_dist = float(msg.data)
        self.last_update_time = time.time()

    def cb_offset(self, msg: Float32):
        self.target_offs = float(msg.data)
        self.last_update_time = time.time()

    def cb_confidence(self, msg: Float32):
        self.target_conf = float(msg.data)
        self.last_update_time = time.time()

    # ---------- Main control ----------
    def update_control(self):
        now = time.time()

        # ถ้าไม่มีข้อมูลนานเกิน timeout → STOP
        if now - self.last_update_time > self.timeout_sec:
            if self.mode != 'STOP':
                self.mode = 'STOP'
                self.get_logger().warn("[MODE] Timeout → STOP")
            self.publish_stop()
            return

        # ยังไม่มีข้อมูลระยะหรือ offset เลย → STOP ไว้ก่อน
        if self.target_dist is None or self.target_offs is None:
            if self.mode != 'STOP':
                self.mode = 'STOP'
                self.get_logger().warn("[MODE] No target data → STOP")
            self.publish_stop()
            return

        # ตัดสินใจโหมดจาก confidence
        if self.target_conf < self.conf_stop:
            # STOP mode
            if self.mode != 'STOP':
                self.mode = 'STOP'
                self.get_logger().info(f"[MODE] conf={self.target_conf:.2f} < {self.conf_stop:.2f} → STOP")
            self.publish_stop()
            return

        elif self.target_conf < self.conf_hold:
            # HOLD mode: ค่อยๆเบรค ไม่หมุนเพิ่ม
            if self.mode != 'HOLD':
                self.mode = 'HOLD'
                self.get_logger().info(f"[MODE] conf={self.target_conf:.2f} in HOLD range ({self.conf_stop:.2f}–{self.conf_hold:.2f}) → HOLD")
            self.publish_hold()
            return

        else:
            # FOLLOW mode
            if self.mode != 'FOLLOW':
                self.mode = 'FOLLOW'
                self.get_logger().info(f"[MODE] conf={self.target_conf:.2f} ≥ {self.conf_hold:.2f} → FOLLOW")
            self.publish_follow()

    # ---------- Mode behaviours ----------
    def publish_stop(self):
        cmd = Twist()
        cmd.linear.x = 0.0
        cmd.angular.z = 0.0
        self.last_cmd = cmd
        self.pub_cmd.publish(cmd)

    def publish_hold(self):
        """
        HOLD: ค่อยๆลดความเร็วจากคำสั่งล่าสุด (เหมือน inertia นิดหน่อย)
        """
        cmd = Twist()
        cmd.linear.x = self.last_cmd.linear.x * 0.5
        cmd.angular.z = self.last_cmd.angular.z * 0.5

        # ถ้าช้ามากแล้วก็หยุดเลย
        if abs(cmd.linear.x) < 0.02 and abs(cmd.angular.z) < 0.02:
            cmd.linear.x = 0.0
            cmd.angular.z = 0.0

        self.last_cmd = cmd
        self.pub_cmd.publish(cmd)

    def publish_follow(self):
        """
        FOLLOW: ใช้ระยะ + offset คำนวณ linear / angular
        """
        d = self.target_dist
        offs = self.target_offs

        cmd = Twist()

        # ----- Linear control จากระยะ -----
        # ถ้าอยู่ในช่วง [dist_min, dist_max] → ไม่ต้องขยับ
        if d < self.dist_min:
            # ใกล้เกินไป → ถอยเบาๆ
            error = d - self.dist_min   # จะติดลบ
            v = self.k_linear * error   # error ลบ → v ลบ (ถอย)
        elif d > self.dist_max:
            # ไกลเกินไป → เดินหน้า
            error = d - self.dist_max   # บวก
            v = self.k_linear * error
        else:
            v = 0.0

        # clamp linear
        v = max(-self.max_linear, min(self.max_linear, v))

        # ----- Angular control จาก offset -----
        # สมมติ offset = (ซ้าย - / ขวา +) หรือเป็น rad กลาง = 0
        # อยากให้หันเข้ากลาง → หมุนกลับทิศ offset
        w = - self.k_angular * offs
        w = max(-self.max_angular, min(self.max_angular, w))

        cmd.linear.x = v
        cmd.angular.z = w

        self.last_cmd = cmd
        self.pub_cmd.publish(cmd)

        self.get_logger().debug(
            f"[FOLLOW] d={d:.2f}m offs={offs:.3f} conf={self.target_conf:.2f} → lin={v:.2f} ang={w:.2f}"
        )


def main(args=None):
    rclpy.init(args=args)
    node = FollowController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.publish_stop()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
