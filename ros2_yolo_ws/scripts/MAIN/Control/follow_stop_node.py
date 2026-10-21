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

        # motion
        self.declare_parameter('linear_gain', 0.55)
        self.declare_parameter('max_linear_speed', 3.5)

        # init dist
        self.declare_parameter('init_dist_min', 0.5)
        self.declare_parameter('init_dist_max', 1.0)

        # angular / sector logic
        self.declare_parameter('center_sector', 4)        # sector กลาง
        self.declare_parameter('front_band_radius', 1)    # 4±1 = [3,5] = กลาง
        self.declare_parameter('wide_front_radius', 1)    # 4±1 = [3,5]; sector 2/6 starts a turn
        self.declare_parameter('angular_gain', 0.10)
        self.declare_parameter('angular_limit', 0.25)
        self.declare_parameter('edge_consistency', 1)     # หมุนเมื่อเป้าหมายเริ่มออกจากแถบกลาง

        # ---------- Load ----------
        self.target_distance   = float(self.get_parameter('target_distance').value)
        self.tolerance         = float(self.get_parameter('tolerance').value)
        self.p_fused_threshold = float(self.get_parameter('p_fused_threshold').value)
        self.linear_gain       = float(self.get_parameter('linear_gain').value)
        self.max_linear_speed  = float(self.get_parameter('max_linear_speed').value)
        self.init_dist_min     = float(self.get_parameter('init_dist_min').value)
        self.init_dist_max     = float(self.get_parameter('init_dist_max').value)

        self.center_sector     = int(self.get_parameter('center_sector').value)
        self.front_band_radius = int(self.get_parameter('front_band_radius').value)
        self.wide_front_radius = int(self.get_parameter('wide_front_radius').value)
        self.angular_gain      = float(self.get_parameter('angular_gain').value)
        self.angular_limit     = float(self.get_parameter('angular_limit').value)
        self.edge_consistency  = int(self.get_parameter('edge_consistency').value)

        # ---------- State ----------
        self.initialized   = False
        self.last_good_cmd = Twist()
        self.last_good_time = self.get_clock().now()
        self.p_buffer      = []

        # Bayesian sector prior
        self.prev_sector   = None
        self.edge_counter  = 0   # นับเฟรมที่อยู่นอก wide-front ติดกัน

        # ---------- ROS ----------
        self.sub = self.create_subscription(Float32MultiArray, '/target_fused_prob', self.cb_fused, 10)
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)

        self.get_logger().info(
            f"FollowStopNode ✅ started | Target={self.target_distance:.2f} m "
            f"(init {self.init_dist_min}-{self.init_dist_max} m)"
        )

    # ==================================================
    def cb_fused(self, msg: Float32MultiArray):
        if len(msg.data) < 8:
            return
        cx, cy, dist, sector, P_C, P_L, P_fused, dt_ms = msg.data
        sector = int(sector)

        # ---------- Initial distance check ----------
        if not self.initialized:
            if not (self.init_dist_min <= dist <= self.init_dist_max):
                self.publish_stop()
                self.get_logger().info(
                    f"[WAIT] dist={dist:.2f} m outside init range ({self.init_dist_min}-{self.init_dist_max} m)"
                )
                return
            else:
                self.initialized = True
                self.prev_sector = sector
                self.get_logger().info(f"[INIT ✅] Target locked at {dist:.2f} m — starting follow mode")

        # ---------- Smooth confidence ----------
        self.p_buffer.append(P_fused)
        if len(self.p_buffer) > 5:
            self.p_buffer.pop(0)
        P_fused_smooth = sum(self.p_buffer) / len(self.p_buffer)

        # ---------- Confidence check ----------
        now = self.get_clock().now()
        if P_fused_smooth < self.p_fused_threshold or not isfinite(dist):
            if (now - self.last_good_time).nanoseconds / 1e9 < 1.0:
                self.pub.publish(self.last_good_cmd)
                self.get_logger().info(f"[HOLD] Low conf {P_fused_smooth:.2f} → keep last cmd")
            else:
                self.publish_stop()
                self.get_logger().info(f"[STOP] P_fused={P_fused_smooth:.2f} (low confidence)")
            return

        # ---------- Distance control ----------
        error_dist = dist - self.target_distance
        if abs(error_dist) <= self.tolerance:
            linear_x = 0.0
        else:
            dynamic_gain = self.linear_gain * max(
                0.3, min(1.0, abs(error_dist) / self.target_distance)
            )
            linear_x = dynamic_gain * error_dist
            linear_x = max(min(linear_x, self.max_linear_speed), -self.max_linear_speed)

        # ---------- Angular control (Bayesian / previous sector) ----------
        center = self.center_sector
        front_min = center - self.front_band_radius
        front_max = center + self.front_band_radius
        wide_min  = center - self.wide_front_radius
        wide_max  = center + self.wide_front_radius

        angular_z = 0.0  # ค่าเริ่มต้น: ไม่หมุน

        # 1) ถ้าเฟรมก่อนหน้าอยู่แถวกลาง (3–5) → ถือว่าคนอยู่ด้านหน้า
        if self.prev_sector is not None and (front_min <= self.prev_sector <= front_max):
            # เฟรมใหม่อยู่ใน wide-front (2–6) → ยังไม่ต้องหมุน
            if wide_min <= sector <= wide_max:
                angular_z = 0.0  # ✅ ตามที่เจ้าว่า: 4 → 2,3,5,6 ไม่หมุน
                self.edge_counter = 0
            else:
                # หลุดออกจาก wide-front แล้ว → เริ่มนับ edge
                self.edge_counter += 1
        else:
            # 2) เฟรมก่อนหน้าอยู่ปลาย ๆ แล้ว (เช่น 7–8)
            if sector < wide_min or sector > wide_max:
                self.edge_counter += 1
            else:
                self.edge_counter = 0

        # 3) ถ้าอยู่ edge หลายเฟรมติด → หมุนจริง
        if self.edge_counter >= self.edge_consistency:
            error_sector = sector - center
            angular_z = -self.angular_gain * error_sector
            angular_z = max(min(angular_z, self.angular_limit), -self.angular_limit)
        # else: angular_z = 0 (ยังถือว่า noise / ขยับตัวเล็กน้อย)

        # update prior
        self.prev_sector = sector

        # ---------- Publish ----------
        twist = Twist()
        twist.linear.x = linear_x
        twist.angular.z = angular_z
        self.pub.publish(twist)

        self.last_good_cmd = twist
        self.last_good_time = now

        self.get_logger().info(
            f"[MOVE] dist={dist:.2f}m (err={error_dist:+.2f}) "
            f"sec_prev={self.prev_sector} sec_now={sector} "
            f"P={P_fused_smooth:.2f} edge_cnt={self.edge_counter} "
            f"→ v=({linear_x:.2f}, {angular_z:.2f})"
        )

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
