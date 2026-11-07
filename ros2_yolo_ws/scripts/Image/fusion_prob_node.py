#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FusionProbNode v3.0 — weighted confidence with time smoothing (not a Bayesian filter)
----------------------------------------------------
รวมข้อมูล YOLO–LiDAR แบบ weighted + temporal fusion
รองรับความถี่ไม่เท่ากัน (dt_ms) และทำ smoothing จากเฟรมก่อนหน้า

P_C (how near the image centre) and P_L (how near the robot) are heuristic scores, not likelihoods;
P_fused is their weighted mean, smoothed by an exponential moving average whose weight falls with
the gap between messages. There is no prior, likelihood or Bayes' rule. follow_stop uses P_fused
only as a confidence threshold (hold or stop below it).

Sub:
  /synced_target : std_msgs/msg/Float32MultiArray
      [cx, cy, dist, sector, dt_ms, stamp]

Pub:
  /target_fused_prob : std_msgs/msg/Float32MultiArray
      [cx, cy, dist, sector, P_C, P_L, P_fused, dt_ms]

Parameters:
  dist_max        : ระยะสูงสุดที่เชื่อว่า LiDAR ยังตรวจจับได้ (m)
  camera_weight   : น้ำหนักกล้อง (0–1)
  lidar_weight    : น้ำหนัก LiDAR (0–1)
  alpha_base      : ค่าพื้นฐานสำหรับ temporal smoothing (0–1)
  dt_ref          : เวลามาตรฐาน (s) ใช้ normalize ความถี่
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray
import math
import numpy as np


class FusionProbNode(Node):
    def __init__(self):
        super().__init__('fusion_prob_node')

        # ---------- Parameters ----------
        self.declare_parameter('dist_max', 2.0)
        self.declare_parameter('camera_weight', 0.7)
        self.declare_parameter('lidar_weight', 0.3)
        self.declare_parameter('alpha_base', 0.7)
        self.declare_parameter('dt_ref', 0.33)  # ประมาณ 3 Hz (กล้อง)
        # How much an off-centre target lowers camera confidence: P_C = exp(-k * dx^2).
        # 0 = none. The previous fixed k=3 dropped P_fused below the controller's threshold
        # exactly when the target was far enough off-centre for the controller to turn, so the
        # follower could never turn toward it.
        self.declare_parameter('center_penalty', 0.0)

        self.dist_max = float(self.get_parameter('dist_max').value)
        self.w_c = float(self.get_parameter('camera_weight').value)
        self.w_l = float(self.get_parameter('lidar_weight').value)
        self.alpha_base = float(self.get_parameter('alpha_base').value)
        self.dt_ref = float(self.get_parameter('dt_ref').value)
        self.center_penalty = float(self.get_parameter('center_penalty').value)

        # ---------- Memory ----------
        self.prev_p_fused = 0.5
        self.prev_stamp = None
        self.lidar_buffer = []  # [(stamp, P_L)]

        # ---------- ROS I/O ----------
        self.sub_sync = self.create_subscription(
            Float32MultiArray, '/synced_target', self.cb_sync, 10)
        self.pub_prob = self.create_publisher(
            Float32MultiArray, '/target_fused_prob', 10)

        self.get_logger().info(
            f"FusionProbNode v3.0 started 🧠 | weights C={self.w_c}, L={self.w_l}, α={self.alpha_base}"
        )

    # ---------- Callback ----------
    def cb_sync(self, msg: Float32MultiArray):
        data = msg.data
        if len(data) < 6:
            return

        cx, cy, dist, sector, dt_ms, stamp = data
        stamp = float(stamp)

        # ----------------------------------------------------
        # 1. Camera confidence (P_C)
        # ----------------------------------------------------
        frame_w = 640.0
        dx = abs(cx - frame_w / 2) / (frame_w / 2)
        P_C = math.exp(-self.center_penalty * dx ** 2)

        # ----------------------------------------------------
        # 2. LiDAR confidence (P_L)
        # ----------------------------------------------------
        if not math.isfinite(dist) or dist > self.dist_max:
            P_L = 0.0
        else:
            P_L = max(0.0, 1.0 - (dist / self.dist_max))

        # บันทึกค่า LiDAR ใน buffer (กัน jitter)
        self.lidar_buffer.append((stamp, P_L))
        self.lidar_buffer = [(t, p) for (t, p) in self.lidar_buffer if stamp - t < 1.0]
        P_L_avg = float(np.mean([p for (_, p) in self.lidar_buffer])) if self.lidar_buffer else P_L

        # ----------------------------------------------------
        # 3. Weighted fusion ภายในเฟรม
        # ----------------------------------------------------
        if P_C == 0 and P_L_avg == 0:
            P_obs = 0.0
        else:
            P_obs = (self.w_c * P_C + self.w_l * P_L_avg) / (self.w_c + self.w_l)

        # ----------------------------------------------------
        # 4. Temporal smoothing (เฟรมก่อนหน้า)
        # ----------------------------------------------------
        now = self.get_clock().now().nanoseconds / 1e9
        if self.prev_stamp is not None:
            dt = now - self.prev_stamp
        else:
            dt = self.dt_ref
        self.prev_stamp = now

        # ปรับ alpha ตาม dt (เฟรมช้าลง → alpha ลด)
        alpha = self.alpha_base * math.exp(-dt / (2 * self.dt_ref))
        P_fused = alpha * P_obs + (1 - alpha) * self.prev_p_fused
        self.prev_p_fused = P_fused

        # ----------------------------------------------------
        # 5. Publish & Log
        # ----------------------------------------------------
        out = Float32MultiArray()
        out.data = [cx, cy, dist, sector, P_C, P_L_avg, P_fused, dt_ms]
        self.pub_prob.publish(out)

        self.get_logger().info(
            f"dt={dt:.2f}s | Sec={int(sector)} D={dist:.2f}m | "
            f"P_C={P_C:.2f} P_L(avg)={P_L_avg:.2f} "
            f"P_prev={self.prev_p_fused:.2f} → P_fused={P_fused:.2f}"
        )


def main():
    rclpy.init()
    node = FusionProbNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
