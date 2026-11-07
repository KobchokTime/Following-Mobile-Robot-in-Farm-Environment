#!/usr/bin/env python3
# follow_stop_print.py
# ROS2 Humble | rclpy
import rclpy, math, time
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Point
from std_msgs.msg import Int32, Int32MultiArray, Float32MultiArray

SCAN_TOPIC = '/scan'
CENTROID_TOPIC = '/target_centroid'

class FollowStopPrint(Node):
    def __init__(self):
        super().__init__('follow_stop_print')

        # ---------- Parameters (ปรับได้ตอนรัน) ----------
        self.declare_parameter('stop_dist',         0.5)    # m: ระยะหยุด
        self.declare_parameter('slow_dist',         1.2)    # m: เริ่มชะลอ
        self.declare_parameter('resume_margin',     0.05)   # m: ฮิสเทอรีซิสหลังหยุด
        self.declare_parameter('v_max',             0.4)    # m/s (พิมพ์โชว์เท่านั้น)
        self.declare_parameter('w_max',             1.0)    # rad/s
        self.declare_parameter('kx',                0.0015) # rad/s ต่อ pixel (ใช้กับ cx_filt)
        self.declare_parameter('vx_gain',           0.6)    # scale v ในโซนชะลอ
        self.declare_parameter('front_span_deg',    12.0)   # ช่วงมุมหน้าที่ใช้หา min
        self.declare_parameter('target_timeout',    1.8)    # s: YOLO หายเกินนี้ให้ปลดล็อก
        self.declare_parameter('init_dist',         1.0)    # m: ต้องไกลกว่านี้ก่อนล็อกเป้า
        self.declare_parameter('confirm_needed',    5)      # เฟรมที่ต้องเห็นติดกันเพื่อ lock
        self.declare_parameter('alpha_cx',          0.3)    # EMA ของ cx (0..1)
        self.declare_parameter('cx_deadband',       12.0)   # px: เล็กๆ ไม่ต้องหมุน
        self.declare_parameter('lidar_min_valid',   0.05)   # m: ค่าน้อยกว่านี้ถือว่า invalid

        # ---------- State ----------
        self.front_min = None             # m
        self.cx = None                    # raw pixel (จากซ้าย/offset แล้วแต่ต้นทาง)
        self.cx_filt = None               # EMA
        self.last_seen = 0.0              # time of last centroid
        self.target_locked = False
        self.confirm_count = 0
        self.centroid_type = None         # type ของ topic ปัจจุบัน
        self.reason_cnt = {}              # นับสถิติเหตุผล

        # ---------- Subscribers ----------
        self.sub_scan = self.create_subscription(
            LaserScan, SCAN_TOPIC, self.cb_scan, qos_profile_sensor_data
        )
        self.centroid_sub = None
        self.ensure_centroid_sub()
        self.create_timer(1.0, self.ensure_centroid_sub)

        # ---------- Loop ----------
        self.create_timer(0.2, self.loop)  # print ทุก ~0.2s
        self.get_logger().info('FollowStopPrint started (print-only, no robot control)')

    # --------- Auto subscribe centroid by detected type ---------
    def ensure_centroid_sub(self):
        detected = None
        for name, types in self.get_topic_names_and_types():
            if name == CENTROID_TOPIC and types:
                detected = types[0]
                break

        if detected == self.centroid_type:
            return

        if self.centroid_sub is not None:
            self.destroy_subscription(self.centroid_sub)
            self.centroid_sub = None

        if detected is None:
            # ยังไม่พบ publisher -> สมัครชั่วคราวเป็น Float32MultiArray
            self.centroid_type = 'std_msgs/msg/Float32MultiArray'
            self.centroid_sub = self.create_subscription(Float32MultiArray, CENTROID_TOPIC, self.cb_arr, 10)
            self.get_logger().warn(f'{CENTROID_TOPIC} not found; temp subscribe Float32MultiArray')
        else:
            self.centroid_type = detected
            if 'std_msgs/msg/Int32MultiArray' in detected:
                self.centroid_sub = self.create_subscription(Int32MultiArray, CENTROID_TOPIC, self.cb_iarr, 10)
            elif 'std_msgs/msg/Int32' in detected:
                self.centroid_sub = self.create_subscription(Int32, CENTROID_TOPIC, self.cb_int, 10)
            elif 'geometry_msgs/msg/Point' in detected:
                self.centroid_sub = self.create_subscription(Point, CENTROID_TOPIC, self.cb_pt, 10)
            else:
                self.centroid_sub = self.create_subscription(Float32MultiArray, CENTROID_TOPIC, self.cb_arr, 10)
            self.get_logger().info(f'{CENTROID_TOPIC} type → {self.centroid_type} (subscribed)')

    # --------- Callbacks ----------
    def cb_scan(self, msg: LaserScan):
        # หา min ระยะในช่วง ±front_span_deg รอบแกนหน้า (0 rad) และกรองค่าผิดปกติ
        half = math.radians(self.get_parameter('front_span_deg').value)
        lidar_min_valid = float(self.get_parameter('lidar_min_valid').value)
        ang_min, inc, n = msg.angle_min, msg.angle_increment, len(msg.ranges)
        center = round((0.0 - ang_min)/inc)
        span = round(half/inc)
        i0, i1 = max(0, center - span), min(n - 1, center + span)
        vals = []
        for r in msg.ranges[i0:i1+1]:
            if math.isfinite(r) and r > lidar_min_valid:
                vals.append(r)
        self.front_min = min(vals) if vals else None

    # NOTE: ปรับ callback ให้ตีความ "data[0]" เป็นตำแหน่ง x (ตาม publisher ของคุณ)
    def _mark_seen_x_from_left(self, x_from_left):
        # ถ้า YOLO ของคุณส่ง offset จากกึ่งกลางอยู่แล้ว → ตั้ง self.cx = float(x_from_left)
        self.cx = float(x_from_left)
        # EMA
        a = float(self.get_parameter('alpha_cx').value)
        self.cx_filt = self.cx if self.cx_filt is None else (1 - a) * self.cx_filt + a * self.cx

        self.last_seen = time.time()

        # เงื่อนไข lock: ระยะต้อง >= init_dist และต้องเห็นครบ confirm_needed เฟรมติด
        init_dist = float(self.get_parameter('init_dist').value)
        need = int(self.get_parameter('confirm_needed').value)
        if self.front_min is not None and self.front_min >= init_dist:
            self.confirm_count += 1
            if (not self.target_locked) and (self.confirm_count >= need):
                self.target_locked = True
                self.get_logger().info(f'Target locked at cx={self.cx:.1f}, dist≈{self.front_min:.2f} m')
        else:
            self.confirm_count = 0  # ระยะไม่ถึง → reset การยืนยัน

    def cb_int(self, msg: Int32):
        self._mark_seen_x_from_left(msg.data)

    def cb_iarr(self, msg: Int32MultiArray):
        if msg.data:
            self._mark_seen_x_from_left(msg.data[0])

    def cb_arr(self, msg: Float32MultiArray):
        if msg.data:
            self._mark_seen_x_from_left(msg.data[0])

    def cb_pt(self, msg: Point):
        self._mark_seen_x_from_left(msg.x)

    # --------- Main loop (print-only) ----------
    def loop(self):
        now         = time.time()
        stop_dist   = float(self.get_parameter('stop_dist').value)
        slow_dist   = float(self.get_parameter('slow_dist').value)
        resume_mg   = float(self.get_parameter('resume_margin').value)
        v_max       = float(self.get_parameter('v_max').value)
        w_max       = float(self.get_parameter('w_max').value)
        kx          = float(self.get_parameter('kx').value)
        vx_gain     = float(self.get_parameter('vx_gain').value)
        timeout     = float(self.get_parameter('target_timeout').value)
        cx_deadband = float(self.get_parameter('cx_deadband').value)
        init_dist   = float(self.get_parameter('init_dist').value)
        need        = int(self.get_parameter('confirm_needed').value)

        # ปลดล็อกถ้า YOLO หายไปนาน
        if self.target_locked and (now - self.last_seen) > timeout:
            self.target_locked = False
            self.confirm_count = 0

        v = 0.0
        w = 0.0
        reason = 'OK'

        if self.front_min is None:
            reason = 'No LiDAR'
        elif (now - self.last_seen) > timeout:
            reason = 'Target timeout'
        elif not self.target_locked:
            reason = f'Waiting initial target (≥{init_dist:.1f} m, {need} frames)'
        elif self.front_min <= stop_dist:
            reason = f'Too close ({self.front_min:.2f} m)'
        elif self.front_min < stop_dist + resume_mg:
            # ฮิสเทอรีซิส: เพิ่งพ้นจุดหยุด ยังคลานช้าๆ
            v = 0.02
            w = 0.0
            reason = 'Resuming (hysteresis)'
        else:
            # Linear speed: โซนชะลอ
            if self.front_min < slow_dist:
                v = vx_gain * (self.front_min - stop_dist) / max(1e-3, (slow_dist - stop_dist)) * v_max
            else:
                v = v_max
            v = max(0.0, min(v, v_max))

            # Angular speed: ตาม cx_filt + เดดแบนด์
            if self.cx_filt is not None:
                if abs(self.cx_filt) < cx_deadband:
                    w = 0.0
                else:
                    w = -kx * self.cx_filt
                w = max(-w_max, min(w, w_max))

        # เก็บสถิติเหตุผลทุกเฟรม
        self.reason_cnt[reason] = self.reason_cnt.get(reason, 0) + 1
        # พิมพ์สถิติทุก ~10 วินาที
        if int(now) % 10 == 0:
            self.get_logger().info(f'[STATS] {self.reason_cnt}')

        print(f'[PRINT] front_min={self.front_min}  cx={self.cx}  '
              f'cx_filt={self.cx_filt}  locked={self.target_locked}  '
              f'v={v:.2f}  w={w:.2f}  reason={reason}')

def main():
    rclpy.init()
    node = FollowStopPrint()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

