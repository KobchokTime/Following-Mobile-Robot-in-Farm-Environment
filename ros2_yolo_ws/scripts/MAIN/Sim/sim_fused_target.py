#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray
import time
import math

class SimFusedTarget(Node):
    def __init__(self):
        super().__init__('sim_fused_target')
        self.pub = self.create_publisher(Float32MultiArray, '/target_fused_prob', 10)
        self.timer = self.create_timer(0.1, self.timer_cb)  # 10 Hz

        self.t = 0.0
        self.dt = 0.1

        # frame size แบบเดียวกับกล้องจริง
        self.frame_w = 640
        self.frame_h = 480

        # เริ่มที่ sector 4 (กลาง)
        self.current_sector = 4.0
        self.cx = self.frame_w / 2
        self.cy = self.frame_h / 2

        # ระยะเริ่มต้น
        self.dist = 0.8

        self.get_logger().info("SimFusedTarget started ✅ publishing fake /target_fused_prob")

    def scenario(self):
        """
        สคริปต์ง่าย ๆ:
        t 0-5s   : เป้าหมายอยู่กลางภาพ sector 4, ระยะ 0.8 → วิ่งเข้าหาเหลือ 0.5
        t 5-10s  : เดินหน้าคงระยะ 0.5
        t 10-15s : ค่อย ๆ เลื่อนขวา (sector 5,6) → ทดสอบ logic ไม่ให้หมุนทันที
        t 15-20s : เลื่อนใกล้ขอบ (sector 7,8) → ดูว่าหุ่นเริ่มหมุนตามไหม
        """
        t = self.t

        # base confidence สูง
        P_C = 0.9
        P_L = 0.8
        P_fused = 0.85

        # กลางเฟรมเสมอโดยคร่าว ๆ (ให้ logic forward-bias ทำงาน)
        self.cx = self.frame_w / 2

        if t < 5.0:
            # ค่อย ๆ เข้าใกล้จาก 0.8 → 0.5
            self.dist = 0.8 - 0.3 * (t / 5.0)
            self.current_sector = 4.0
        elif t < 10.0:
            # คงที่ราว 0.5
            self.dist = 0.5 + 0.02 * math.sin(t)
            self.current_sector = 4.0
        elif t < 15.0:
            # เลื่อนไปทางขวาเล็กน้อย (sector 5,6) → ไม่ควรหมุนแรง
            self.current_sector = 4.0 + 1.5 * ((t - 10.0) / 5.0)  # 4 → 5.5
        elif t < 20.0:
            # เลื่อนไปเกือบขวาสุด (sector 7–8) → ควรเริ่มหมุน
            self.current_sector = 5.5 + 2.5 * ((t - 15.0) / 5.0)  # 5.5 → 8.0
        else:
            # วนลูป
            self.t = 0.0

        # clamp sector
        self.current_sector = max(0.0, min(8.0, self.current_sector))

        # จำลอง dt_ms (สมมติ 50 ms)
        dt_ms = 50.0

        return self.cx, self.cy, self.dist, self.current_sector, P_C, P_L, P_fused, dt_ms

    def timer_cb(self):
        self.t += self.dt

        cx, cy, dist, sector, P_C, P_L, P_fused, dt_ms = self.scenario()

        msg = Float32MultiArray()
        msg.data = [float(cx), float(cy), float(dist), float(sector),
                    float(P_C), float(P_L), float(P_fused), float(dt_ms)]
        self.pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = SimFusedTarget()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
