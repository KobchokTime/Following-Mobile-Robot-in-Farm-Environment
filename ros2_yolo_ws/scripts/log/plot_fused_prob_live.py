#!/usr/bin/env python3
import rclpy, time, collections
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray
import matplotlib.pyplot as plt

class ProbPlot(Node):
    def __init__(self):
        super().__init__('prob_plot')
        self.sub = self.create_subscription(Float32MultiArray, '/target_fused_prob', self.cb, 10)
        self.t = collections.deque(maxlen=200)
        self.PC, self.PL, self.PF = collections.deque(maxlen=200), collections.deque(maxlen=200), collections.deque(maxlen=200)
        plt.ion()
        self.fig, self.ax = plt.subplots()
        self.ax.set_ylim(0, 1)
        self.ax.set_xlabel('time')
        self.ax.set_ylabel('Probability')

    def cb(self, msg):
        d = msg.data
        if len(d) < 8: return
        stamp = time.time()
        self.t.append(stamp)
        self.PC.append(d[4]); self.PL.append(d[5]); self.PF.append(d[6])
        self.ax.clear()
        self.ax.plot(self.t, self.PC, label='P_C (Camera)')
        self.ax.plot(self.t, self.PL, label='P_L (LiDAR)')
        self.ax.plot(self.t, self.PF, label='P_fused', linewidth=2)
        self.ax.legend(loc='lower right')
        self.ax.set_ylim(0, 1)
        plt.pause(0.001)

def main():
    rclpy.init(); node = ProbPlot()
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.05)
            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    node.destroy_node(); rclpy.shutdown()

if __name__ == '__main__':
    main()
