#!/usr/bin/env python3
# FollowStopLogger.py
# ROS2 Humble | rclpy
import rclpy, math, time, csv, os
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Point
from std_msgs.msg import Int32, Int32MultiArray, Float32MultiArray

SCAN_TOPIC = '/scan'
CENTROID_TOPIC = '/target_centroid'

class FollowStopLogger(Node):
    def __init__(self):
        super().__init__('follow_stop_logger')

        # ---------- Parameters ----------
        self.declare_parameter('stop_dist',       0.5)
        self.declare_parameter('slow_dist',       1.2)
        self.declare_parameter('resume_margin',   0.05)
        self.declare_parameter('v_max',           0.4)
        self.declare_parameter('w_max',           1.0)
        self.declare_parameter('kx',              0.0015)
        self.declare_parameter('vx_gain',         0.6)
        self.declare_parameter('front_span_deg',  12.0)
        self.declare_parameter('target_timeout',  1.8)
        self.declare_parameter('init_dist',       1.0)
        self.declare_parameter('confirm_needed',  5)
        self.declare_parameter('alpha_cx',        0.3)
        self.declare_parameter('cx_deadband',     12.0)
        self.declare_parameter('lidar_min_valid', 0.05)

        # ---------- State ----------
        self.front_min = None
        self.cx = None
        self.cx_filt = None
        self.last_seen = 0.0
        self.target_locked = False
        self.confirm_count = 0

        # ---------- Subscribers ----------
        self.sub_scan = self.create_subscription(
            LaserScan, SCAN_TOPIC, self.cb_scan, qos_profile_sensor_data
        )
        self.centroid_sub = None
        self.ensure_centroid_sub()
        self.create_timer(1.0, self.ensure_centroid_sub)

        # ---------- Logger CSV ----------
        log_file = "follow_log.csv"
        self.log_path = os.path.join(os.getcwd(), log_file)
        self.csv_file = open(self.log_path, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(
            ["time", "front_min", "cx", "cx_filt", "locked", "v", "w", "reason"]
        )

        # ---------- Main loop ----------
        self.create_timer(0.2, self.loop)
        self.get_logger().info(f'Logger started → {self.log_path}')

    def ensure_centroid_sub(self):
        if self.centroid_sub: return
        self.centroid_sub = self.create_subscription(
            Float32MultiArray, CENTROID_TOPIC, self.cb_arr, 10
        )

    def cb_scan(self, msg: LaserScan):
        half = math.radians(self.get_parameter('front_span_deg').value)
        lidar_min_valid = float(self.get_parameter('lidar_min_valid').value)
        ang_min, inc, n = msg.angle_min, msg.angle_increment, len(msg.ranges)
        center = round((0.0 - ang_min)/inc)
        span = round(half/inc)
        i0, i1 = max(0, center - span), min(n - 1, center + span)
        vals = [r for r in msg.ranges[i0:i1+1] if math.isfinite(r) and r > lidar_min_valid]
        self.front_min = min(vals) if vals else None

    def cb_arr(self, msg: Float32MultiArray):
        if msg.data:
            self._mark_seen_x_from_left(msg.data[0])

    def _mark_seen_x_from_left(self, x_from_left):
        a = float(self.get_parameter('alpha_cx').value)
        self.cx = float(x_from_left)
        self.cx_filt = self.cx if self.cx_filt is None else (1-a)*self.cx_filt + a*self.cx
        self.last_seen = time.time()

        init_dist = float(self.get_parameter('init_dist').value)
        need = int(self.get_parameter('confirm_needed').value)
        if self.front_min is not None and self.front_min >= init_dist:
            self.confirm_count += 1
            if (not self.target_locked) and (self.confirm_count >= need):
                self.target_locked = True
                self.get_logger().info(
                    f'Target locked at cx={self.cx:.1f}, dist≈{self.front_min:.2f} m'
                )
        else:
            self.confirm_count = 0

    def loop(self):
        now = time.time()
        stop_dist   = float(self.get_parameter('stop_dist').value)
        slow_dist   = float(self.get_parameter('slow_dist').value)
        resume_mg   = float(self.get_parameter('resume_margin').value)
        v_max       = float(self.get_parameter('v_max').value)
        w_max       = float(self.get_parameter('w_max').value)
        kx          = float(self.get_parameter('kx').value)
        vx_gain     = float(self.get_parameter('vx_gain').value)
        timeout     = float(self.get_parameter('target_timeout').value)
        cx_deadband = float(self.get_parameter('cx_deadband').value)

        # reset lock ถ้า YOLO หายไปนาน
        if self.target_locked and (now - self.last_seen) > timeout:
            self.target_locked = False
            self.confirm_count = 0

        v, w = 0.0, 0.0
        reason = "OK"

        if self.front_min is None:
            reason = "No LiDAR"
        elif (now - self.last_seen) > timeout:
            reason = "Target timeout"
        elif not self.target_locked:
            reason = f"Waiting init"
        elif self.front_min <= stop_dist:
            reason = f"Too close ({self.front_min:.2f} m)"
        elif self.front_min < stop_dist + resume_mg:
            v = 0.02; w = 0.0
            reason = "Resuming"
        else:
            if self.front_min < slow_dist:
                v = vx_gain * (self.front_min - stop_dist) / max(1e-3, (slow_dist - stop_dist)) * v_max
            else:
                v = v_max
            v = max(0.0, min(v, v_max))
            if self.cx_filt is not None:
                if abs(self.cx_filt) < cx_deadband:
                    w = 0.0
                else:
                    w = -kx * self.cx_filt
                w = max(-w_max, min(w, w_max))

        # --- write CSV ---
        self.csv_writer.writerow([
            f"{now:.2f}", 
            f"{self.front_min:.3f}" if self.front_min else "",
            f"{self.cx:.1f}" if self.cx is not None else "",
            f"{self.cx_filt:.1f}" if self.cx_filt is not None else "",
            self.target_locked,
            f"{v:.2f}", f"{w:.2f}", reason
        ])
        self.csv_file.flush()

def main():
    rclpy.init()
    node = FollowStopLogger()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.csv_file.close()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

