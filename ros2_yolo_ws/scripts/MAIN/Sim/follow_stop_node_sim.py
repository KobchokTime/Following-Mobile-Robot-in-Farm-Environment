#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray
from geometry_msgs.msg import Twist
from math import isfinite

class FollowStopNode(Node):
    def __init__(self):
        super().__init__('follow_stop_node')

        # ---------- Parameters ----------
        self.declare_parameter('target_distance', 0.5)
        self.declare_parameter('tolerance', 0.1)
        self.declare_parameter('p_fused_threshold', 0.6)

        # ระยะ
        self.declare_parameter('linear_gain', 0.55)
        self.declare_parameter('max_linear_speed', 0.35)

        # หมุน (ใช้ sector จากภาพ)
        self.declare_parameter('angular_gain', 0.18)
        self.declare_parameter('angular_limit', 0.5)

        # เงื่อนไขเริ่ม follow
        self.declare_parameter('init_dist_min', 0.5)
        self.declare_parameter('init_dist_max', 1.0)

        # ขนาดภาพ / การแบ่ง sector บนภาพ
        self.declare_parameter('img_width', 640.0)   # ถ้า YOLO เป็น 640x480 อยู่แล้วใช้ค่านี้ได้
        self.declare_parameter('num_sectors', 9)     # S0..S8
        self.declare_parameter('front_sectors', [3,4,5,6])

        # hysteresis บน sector จากภาพ
        self.declare_parameter('max_sector_jump', 1)   # กระโดดเกินเท่าไหร่ถึงถือว่าแปลก
        self.declare_parameter('max_edge_cnt', 2)      # ต้องเจอเฟรม "แปลก" ติดกันกี่ครั้งถึงยอมเปลี่ยน

        # ---------- Load ----------
        p = self.get_parameter
        self.target_distance   = float(p('target_distance').value)
        self.tolerance         = float(p('tolerance').value)
        self.p_fused_threshold = float(p('p_fused_threshold').value)
        self.linear_gain       = float(p('linear_gain').value)
        self.max_linear_speed  = float(p('max_linear_speed').value)
        self.angular_gain      = float(p('angular_gain').value)
        self.angular_limit     = float(p('angular_limit').value)
        self.init_dist_min     = float(p('init_dist_min').value)
        self.init_dist_max     = float(p('init_dist_max').value)
        self.img_width         = float(p('img_width').value)
        self.num_sectors       = int(p('num_sectors').value)
        self.front_sectors     = set(p('front_sectors').value)
        self.max_sector_jump   = int(p('max_sector_jump').value)
        self.max_edge_cnt      = int(p('max_edge_cnt').value)

        self.sector_width = self.img_width / self.num_sectors

        # ---------- State ----------
        self.initialized = False
        self.last_good_cmd = Twist()
        self.last_good_time = self.get_clock().now()
        self.p_buffer = []

        self.sec_img_prev = None   # sector จากภาพที่เราเชื่อก่อนหน้า
        self.edge_cnt = 0          # นับเฟรมที่ sector กระโดดเยอะ

        # ---------- ROS ----------
        self.sub = self.create_subscription(
            Float32MultiArray, '/target_fused_prob', self.cb_fused, 10
        )
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)

        self.get_logger().info(
            f"FollowStopNode ✅ started | Target={self.target_distance:.2f} m "
            f"(init {self.init_dist_min}-{self.init_dist_max} m)"
        )

    # ==================================================
    def cb_fused(self, msg: Float32MultiArray):
        if len(msg.data) < 8:
            return

        # msg: [cx, cy, dist, sector_fused, P_C, P_L, P_fused, dt_ms]
        cx, cy, dist, sector_fused, P_C, P_L, P_fused, dt_ms = msg.data

        # ---------- Initial distance check ----------
        if not self.initialized:
            if not (self.init_dist_min <= dist <= self.init_dist_max):
                self.publish_stop()
                self.get_logger().info(
                    f"[WAIT] dist={dist:.2f} m outside init range "
                    f"({self.init_dist_min}-{self.init_dist_max} m)"
                )
                return
            else:
                self.initialized = True
                # sector จากภาพในเฟรมแรก
                self.sec_img_prev = self.cx_to_sector(cx)
                self.get_logger().info(
                    f"[INIT ✅] Target locked at {dist:.2f} m — starting follow mode"
                )

        # ---------- Smooth confidence ----------
        self.p_buffer.append(P_fused)
        if len(self.p_buffer) > 5:
            self.p_buffer.pop(0)
        P_smooth = sum(self.p_buffer) / len(self.p_buffer)

        now = self.get_clock().now()

        # ---------- Confidence check ----------
        if P_smooth < self.p_fused_threshold or not isfinite(dist):
            if (now - self.last_good_time).nanoseconds / 1e9 < 1.0:
                self.pub.publish(self.last_good_cmd)
                self.get_logger().info(
                    f"[HOLD] Low conf {P_smooth:.2f} → keep last cmd"
                )
            else:
                self.publish_stop()
                self.get_logger().info(
                    f"[STOP] P_fused={P_smooth:.2f} (low confidence)"
                )
            return

        # ---------- Sector from IMAGE (ไม่ใช้ LiDAR แล้วสำหรับทิศ) ----------
        sec_img_now = self.cx_to_sector(cx)

        if self.sec_img_prev is None:
            sec_used = sec_img_now
            self.sec_img_prev = sec_img_now
            self.edge_cnt = 0
        else:
            if abs(sec_img_now - self.sec_img_prev) <= self.max_sector_jump:
                # เปลี่ยนไม่เยอะ → เชื่อค่าปัจจุบัน
                sec_used = sec_img_now
                self.sec_img_prev = sec_used
                self.edge_cnt = 0
            else:
                # กระโดดเยอะ → ให้นับก่อนว่าเจอหลายเฟรมหรือยัง
                self.edge_cnt += 1
                if self.edge_cnt >= self.max_edge_cnt:
                    # เจอซ้ำหลายเฟรม → ยอมเชื่อค่าใหม่
                    sec_used = sec_img_now
                    self.sec_img_prev = sec_used
                    self.edge_cnt = 0
                else:
                    # ใช้ sector เดิมไปก่อน
                    sec_used = self.sec_img_prev

        # ---------- Distance control ----------
        error_dist = dist - self.target_distance
        if abs(error_dist) <= self.tolerance:
            linear_x = 0.0
        else:
            dyn_gain = self.linear_gain * max(
                0.3, min(1.0, abs(error_dist) / self.target_distance)
            )
            linear_x = dyn_gain * error_dist
            linear_x = max(min(linear_x, self.max_linear_speed),
                           -self.max_linear_speed)

        # ---------- Angular control ----------
        if sec_used in self.front_sectors:
            # ยังถือว่าอยู่ด้านหน้า → ไม่ต้องหมุน
            angular_z = 0.0
        else:
            err_sector = sec_used - 4  # 4 = กลาง
            angular_z = -self.angular_gain * err_sector
            angular_z = max(min(angular_z, self.angular_limit),
                            -self.angular_limit)

        # ---------- Publish ----------
        twist = Twist()
        twist.linear.x = linear_x
        twist.angular.z = angular_z
        self.pub.publish(twist)

        self.last_good_cmd = twist
        self.last_good_time = now

        self.get_logger().info(
            f"[MOVE] dist={dist:.2f}m (err={error_dist:+.2f}) "
            f"sec_fused={sector_fused:.2f} sec_img_now={sec_img_now} "
            f"sec_used={sec_used} sec_prev={self.sec_img_prev} "
            f"edge_cnt={self.edge_cnt} P={P_smooth:.2f} "
            f"→ v=({linear_x:.2f}, {angular_z:.2f})"
        )

    # ---------- helper: map cx → sector ----------
    def cx_to_sector(self, cx: float) -> int:
        s = int(cx // self.sector_width)
        if s < 0:
            s = 0
        if s >= self.num_sectors:
            s = self.num_sectors - 1
        return s

    # ==================================================
    def publish_stop(self):
        twist = Twist()
        self.pub.publish(twist)

def main():
    rclpy.init()
    node = FollowStopNode()
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
