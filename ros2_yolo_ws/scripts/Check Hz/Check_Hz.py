#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import math, statistics, time
from collections import deque

import rclpy
from rclpy.node import Node
from rclpy.time import Time

from sensor_msgs.msg import LaserScan
from std_msgs.msg import Int32MultiArray
from message_filters import Subscriber, ApproximateTimeSynchronizer

def to_sec(stamp) -> float:
    return float(stamp.sec) + float(stamp.nanosec) * 1e-9

class RateStat:
    def __init__(self, maxlen=200):
        self.t_last = None
        self.periods = deque(maxlen=maxlen)
        self.latencies = deque(maxlen=maxlen)

    def tick(self, msg_stamp_sec: float, now_sec: float):
        # period for Hz
        if self.t_last is not None:
            self.periods.append(now_sec - self.t_last)
        self.t_last = now_sec
        # latency
        self.latencies.append(now_sec - msg_stamp_sec)

    def hz(self):
        if len(self.periods) < 2: return 0.0
        mean_period = statistics.mean(self.periods)
        return 1.0 / mean_period if mean_period > 1e-6 else 0.0

    def jitter(self):
        return statistics.pstdev(self.periods) if len(self.periods) >= 2 else 0.0

    def latency_mean(self):
        return statistics.mean(self.latencies) if self.latencies else 0.0

    def latency_p95(self):
        if not self.latencies: return 0.0
        arr = sorted(self.latencies)
        k = int(0.95 * (len(arr) - 1))
        return arr[k]

class Monitor(Node):
    def __init__(self):
        super().__init__('rate_sync_monitor')

        # ปรับชื่อท็อปิกให้ตรงระบบของคุณ
        self.sub_scan = self.create_subscription(LaserScan, '/scan', self.on_scan, 10)
        self.sub_cx   = self.create_subscription(Int32MultiArray, '/target_centroid', self.on_cx, 10)

        # สำหรับการซิงก์ (ต้องติดตั้ง message_filters)
        self.ms_yolo = Subscriber(self, Int32MultiArray, '/target_centroid')
        self.ms_scan = Subscriber(self, LaserScan, '/scan')
        self.sync = ApproximateTimeSynchronizer([self.ms_yolo, self.ms_scan],
                                                queue_size=20, slop=0.05)
        self.sync.registerCallback(self.on_sync)

        self.rs_scan = RateStat()
        self.rs_cx   = RateStat()

        self.sync_deltas = deque(maxlen=200)  # Δt ระหว่างคู่เฟรม

        self.timer = self.create_timer(1.0, self.report)

    def now_sec(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def on_scan(self, msg: LaserScan):
        msg_t = to_sec(msg.header.stamp)
        self.rs_scan.tick(msg_t, self.now_sec())

    def on_cx(self, msg: Int32MultiArray):
        # ถ้า message ไม่มี header ก็วัด latency แบบ wall-clock ไม่ได้
        # แนะนำให้ฝั่ง YOLO publisher ใส่ header.stamp ด้วย
        # ที่นี่จะ fallback เป็น 'รับเมื่อไหร่ ก็ตีเป็น now'
        now = self.now_sec()
        msg_t = now
        self.rs_cx.tick(msg_t, now)

    def on_sync(self, msg_cx: Int32MultiArray, msg_scan: LaserScan):
        t_scan = to_sec(msg_scan.header.stamp)
        # ดูเวลา "รับ" ของ message_filters (ใกล้ๆ now)
        t_now  = self.now_sec()
        # ไม่มี header ใน cx → ใช้เวลารับแทน (ถ้า YOLO มี header ให้เปลี่ยนมาใช้)
        t_cx   = t_now
        self.sync_deltas.append(abs(t_scan - t_cx))

    def report(self):
        def fmt(x): return f"{x:.3f}"
        hz_scan = self.rs_scan.hz()
        hz_cx   = self.rs_cx.hz()
        jit_s   = self.rs_scan.jitter()
        jit_c   = self.rs_cx.jitter()
        lat_s_m = self.rs_scan.latency_mean()
        lat_s_p = self.rs_scan.latency_p95()
        lat_c_m = self.rs_cx.latency_mean()
        lat_c_p = self.rs_cx.latency_p95()
        sync_p95 = (sorted(self.sync_deltas)[int(0.95*(len(self.sync_deltas)-1))] 
                    if self.sync_deltas else 0.0)

        self.get_logger().info(
            "---- RATE / LATENCY / SYNC ----\n"
            f" /scan   : {fmt(hz_scan)} Hz | jitter {fmt(jit_s)} s | latency mean {fmt(lat_s_m)} s (p95 {fmt(lat_s_p)})\n"
            f" /target : {fmt(hz_cx)} Hz | jitter {fmt(jit_c)} s | latency mean {fmt(lat_c_m)} s (p95 {fmt(lat_c_p)})\n"
            f" sync Δt : p95 {fmt(sync_p95)} s (ApproxTime sync slop=0.05)\n"
        )

def main():
    rclpy.init()
    node = Monitor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

