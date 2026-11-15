# ~/ros2_yolo_ws/scripts/plot_synced_live.py
#!/usr/bin/env python3
import rclpy, collections, time
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray
import matplotlib.pyplot as plt

class Plot(Node):
    def __init__(self):
        super().__init__('synced_plot')
        self.sub = self.create_subscription(Float32MultiArray, '/synced_target', self.cb, 10)
        self.t = collections.deque(maxlen=200)
        self.dt = collections.deque(maxlen=200)
        self.dist = collections.deque(maxlen=200)
        plt.ion(); self.f1 = plt.figure(); self.ax1 = self.f1.add_subplot(111)
        self.f2 = plt.figure(); self.ax2 = self.f2.add_subplot(111)

    def cb(self, msg):
        d = msg.data
        if len(d) < 6: return
        stamp = d[5]; self.t.append(stamp); self.dt.append(d[4]); self.dist.append(d[2])
        # dt plot
        self.ax1.clear(); self.ax1.plot(list(self.t), list(self.dt)); self.ax1.set_title('dt (ms)')
        # dist plot
        self.ax2.clear(); self.ax2.plot(list(self.t), list(self.dist)); self.ax2.set_title('dist (m)')
        plt.pause(0.001)

def main():
    rclpy.init(); n=Plot()
    try:
        while rclpy.ok():
            rclpy.spin_once(n, timeout_sec=0.01)
            time.sleep(0.01)
    except KeyboardInterrupt: pass
    n.destroy_node(); rclpy.shutdown()
if __name__ == '__main__': main()
