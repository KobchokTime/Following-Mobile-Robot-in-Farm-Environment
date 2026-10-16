#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Float32MultiArray
from rclpy.qos import qos_profile_sensor_data
import numpy as np
import math


class LidarSectorizer(Node):
    def __init__(self):
        super().__init__('lidar_sectorizer')

        # ----------------------------
        # Parameters
        # ----------------------------
        self.declare_parameter('num_sectors', 9)
        self.declare_parameter('fov_min_deg', -15.0)
        self.declare_parameter('fov_max_deg', 15.0)
        self.declare_parameter('angle_offset_deg', 180.0)  # ใช้ 180° ถ้าติด LiDAR กลับด้าน

        self.N = int(self.get_parameter('num_sectors').value)
        self.fov_min = float(self.get_parameter('fov_min_deg').value)
        self.fov_max = float(self.get_parameter('fov_max_deg').value)
        self.angle_offset = math.radians(float(self.get_parameter('angle_offset_deg').value))

        # ----------------------------
        # Subscriptions & Publishers
        # ----------------------------
        self.sub = self.create_subscription(
            LaserScan, '/scan', self.cb, qos_profile_sensor_data
        )

        self.pub_dist = self.create_publisher(Float32MultiArray, '/lidar_sector_dists', 10)
        self.pub_var = self.create_publisher(Float32MultiArray, '/lidar_sector_vars', 10)
        self.pub_angle = self.create_publisher(Float32MultiArray, '/lidar_sector_angles', 10)

        self.frame_count = 0
        self.get_logger().info(
            f'LidarSectorizer started ✅ — {self.N} sectors, FOV={self.fov_min}° to {self.fov_max}°, offset={math.degrees(self.angle_offset):.1f}°'
        )

    def cb(self, msg: LaserScan):
        """แบ่งข้อมูล LiDAR เฉพาะช่วง ±FOV (พร้อมชดเชยมุมติดตั้ง)"""
        self.frame_count += 1

        total_pts = len(msg.ranges)
        if total_pts == 0:
            return

        # แปลงองศาเริ่มต้น–สิ้นสุด + ชดเชยมุมติดตั้ง
        angles = np.linspace(msg.angle_min, msg.angle_max, total_pts)
        angles = angles + self.angle_offset
        angles = (angles + math.pi) % (2 * math.pi) - math.pi  # normalize ให้อยู่ในช่วง -π ถึง π

        selected_ranges = np.array(msg.ranges)

        # เลือกเฉพาะช่วง -FOV ถึง +FOV
        min_a = math.radians(self.fov_min)
        max_a = math.radians(self.fov_max)
        mask = (angles >= min_a) & (angles <= max_a)

        selected_ranges = selected_ranges[mask]
        selected_angles = angles[mask]

        if selected_ranges.size == 0:
            return

        # แบ่ง sector
        sector_edges = np.linspace(min_a, max_a, self.N + 1)
        dists, vars_, mids = [], [], []

        for i in range(self.N):
            a1, a2 = sector_edges[i], sector_edges[i + 1]
            mid = (a1 + a2) / 2.0
            mids.append(mid)
            mask_sector = (selected_angles >= a1) & (selected_angles < a2)
            sector_data = selected_ranges[mask_sector]
            sector_data = sector_data[np.isfinite(sector_data)]
            sector_data = sector_data[
                (sector_data > msg.range_min) & (sector_data < msg.range_max)
            ]

            if sector_data.size == 0:
                dists.append(float('inf'))
                vars_.append(0.0)
            else:
                dists.append(float(np.median(sector_data)))
                vars_.append(float(np.var(sector_data)))

        # Publish
        msg_d = Float32MultiArray()
        msg_v = Float32MultiArray()
        msg_a = Float32MultiArray()
        msg_d.data = dists
        msg_v.data = vars_
        msg_a.data = mids

        self.pub_dist.publish(msg_d)
        self.pub_var.publish(msg_v)
        self.pub_angle.publish(msg_a)

        # Log เฉพาะ sector กลาง (มุมตรงหน้า)
        if self.frame_count % 30 == 0:
            mid_id = self.N // 2
            self.get_logger().info(
                f'#{self.frame_count}: dist[mid]={dists[mid_id]:.2f} m, '
                f'var[mid]={vars_[mid_id]:.4f}, '
                f'angle[mid]={math.degrees(mids[mid_id]):.1f}°'
            )


def main():
    rclpy.init()
    node = LidarSectorizer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
