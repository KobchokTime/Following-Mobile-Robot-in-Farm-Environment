#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from contextlib import suppress
import minimalmodbus
import time

# ================= CONFIG =================
PORT = "/dev/ttyUSB1"
BAUD = 115200
SLAVE_ID = 1

# mapping จาก /cmd_vel.linear.x → speed command
SPEED_GAIN = 40.0      # lin=0.5 → ~20
MAX_CMD    = 40.0      # กันไม่ให้ส่งแรงเกินไป

# ถ้าเดินหน้ากลายเป็นถอยหลัง สลับเป็น -1.0 ได้
FORWARD_DIR = 1.0

TIMEOUT = 1.0  # วินาที: ถ้าไม่ได้ cmd_vel ใหม่เกินนี้ → set vel = 0

# ============== ZLAC DRIVER ===============
class ZLAC8015D:
    def __init__(self, port, sid, baud):
        self.inst = minimalmodbus.Instrument(port, sid)
        self.inst.serial.baudrate = baud
        self.inst.serial.bytesize = 8
        self.inst.serial.parity   = minimalmodbus.serial.PARITY_NONE
        self.inst.serial.stopbits = 1
        self.inst.serial.timeout  = 0.5
        self.inst.mode = minimalmodbus.MODE_RTU
        self.inst.close_port_after_each_call = True

    def enable_velocity(self):
        # เหมือนสคริปต์จอยที่วิ่งได้
        self.inst.write_register(0x200D, 3, 0, functioncode=6)
        time.sleep(0.05)
        with suppress(Exception):
            self.inst.write_register(0x200E, 7, 0, functioncode=6)
        time.sleep(0.05)
        self.inst.write_register(0x200E, 8, 0, functioncode=6)
        print("[Drive] Velocity mode enabled")

    def set_velocity(self, left, right):
        # ✅ สำคัญ: ต้องใส่ signed=True เหมือนโค้ดจอย
        self.inst.write_register(0x2088, int(left), 0, functioncode=6, signed=True)
        self.inst.write_register(0x2089, int(right), 0, functioncode=6, signed=True)
        print(f"[Drive] set_velocity L={left} R={right}")

    def stop_soft(self):
        """หยุดแบบนิ่ม: แค่ตั้ง velocity = 0"""
        with suppress(Exception):
            self.inst.write_register(0x2088, 0, 0, functioncode=6, signed=True)
            self.inst.write_register(0x2089, 0, 0, functioncode=6, signed=True)
        print("[Drive] Soft stop (vel=0)")

    def stop_hard(self):
        """หยุดจริงจัง: ปิด enable (ใช้ตอนปิดโปรแกรม)"""
        with suppress(Exception):
            self.inst.write_register(0x200E, 7, 0, functioncode=6)
        print("[Drive] Hard stop (0x200E=7)")

# ============== MAIN NODE =================
class DriveBridge(Node):
    def __init__(self):
        super().__init__('zlac_drive_bridge')
        self.zlac = ZLAC8015D(PORT, SLAVE_ID, BAUD)
        self.zlac.enable_velocity()

        self.last_cmd_time = time.time()
        self.left = 0.0
        self.right = 0.0

        self.sub = self.create_subscription(Twist, '/cmd_vel', self.cmd_callback, 10)
        self.timer = self.create_timer(0.1, self.update_loop)

        self.get_logger().info("✅ ZLAC Drive Bridge started (listening to /cmd_vel)")

    def cmd_callback(self, msg: Twist):
        linear = msg.linear.x
        # ยังไม่ใช้ angular.z เอาให้วิ่งตรงก่อน
        cmd = FORWARD_DIR * linear * SPEED_GAIN

        # clamp ค่า
        cmd = max(min(cmd, MAX_CMD), -MAX_CMD)

        # ให้ behavior ตรงกับตอนใช้จอย:
        # เดินหน้า → ล้อซ้ายติดลบ / ล้อขวาติดบวก
        self.left  = -cmd
        self.right =  cmd

        self.last_cmd_time = time.time()

        self.get_logger().info(
            f"[CMD] lin={linear:.2f} → L={self.left:.2f} R={self.right:.2f}"
        )

    def update_loop(self):
        # ถ้าเกิน TIMEOUT ไม่มี cmd_vel ใหม่ → set velocity = 0
        if time.time() - self.last_cmd_time > TIMEOUT:
            if self.left != 0.0 or self.right != 0.0:
                self.get_logger().info("[STATE] Timeout → zero velocity")
            self.left = 0.0
            self.right = 0.0

        # ส่งค่าปัจจุบันเข้าไดรฟ์ทุก 0.1 วินาที
        self.zlac.set_velocity(self.left, self.right)

    def destroy_node(self):
        # ตอนปิดโปรแกรม ค่อย soft stop + hard stop
        self.zlac.stop_soft()
        self.zlac.stop_hard()
        super().destroy_node()

def main():
    rclpy.init()
    node = DriveBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
