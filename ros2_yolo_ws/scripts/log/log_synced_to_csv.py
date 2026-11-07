# ~/ros2_yolo_ws/scripts/log_synced_to_csv.py
#!/usr/bin/env python3
import rclpy, csv, time
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray

class Logger(Node):
    def __init__(self):
        super().__init__('synced_logger')
        self.sub = self.create_subscription(Float32MultiArray, '/synced_target', self.cb, 10)
        ts = time.strftime('%Y%m%d_%H%M%S')
        self.f = open(f'/ros2_yolo_ws/scripts/log/synced_{ts}.csv', 'w', newline='')
        self.w = csv.writer(self.f)
        self.w.writerow(['cx','cy','dist_m','sector','dt_ms','stamp'])
        self.get_logger().info('Logging to /tmp/… started')

    def cb(self, msg):
        d = msg.data
        if len(d) >= 6:
            self.w.writerow(d)
    def destroy_node(self):
        self.f.close()
        return super().destroy_node()

def main():
    rclpy.init(); n=Logger()
    try: rclpy.spin(n)
    except KeyboardInterrupt: pass
    n.destroy_node(); rclpy.shutdown()
if __name__ == '__main__': main()
