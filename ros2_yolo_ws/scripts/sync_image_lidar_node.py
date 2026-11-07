import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from sensor_msgs.msg import Image, LaserScan
from cv_bridge import CvBridge
import message_filters
import cv2
import numpy as np

class ImageLidarSyncNode(Node):
    def __init__(self):
        super().__init__('image_lidar_sync_node')
        self.bridge = CvBridge()

        # ✅ Subscribe with proper QoS for sensors
        self.image_sub = message_filters.Subscriber(self, Image, '/image_raw', qos_profile=qos_profile_sensor_data)
        self.lidar_sub = message_filters.Subscriber(self, LaserScan, '/scan', qos_profile=qos_profile_sensor_data)

        # ✅ Use ApproximateTimeSynchronizer to tolerate small time differences
        self.ts = message_filters.ApproximateTimeSynchronizer(
            [self.image_sub, self.lidar_sub],
            queue_size=10,
            slop=0.1  # seconds
        )
        self.ts.registerCallback(self.sync_callback)

        self.get_logger().info('Image + LiDAR Sync Node Started')

    def sync_callback(self, image_msg, lidar_msg):
        # ✅ Convert ROS Image message to OpenCV image
        frame = self.bridge.imgmsg_to_cv2(image_msg, desired_encoding='bgr8')

        # ✅ Basic debug: print image and lidar info
        self.get_logger().info(
            f'Synced: Image [{image_msg.header.stamp.sec}.{image_msg.header.stamp.nanosec}] '
            f'+ LiDAR [{lidar_msg.header.stamp.sec}.{lidar_msg.header.stamp.nanosec}]'
        )

        # ✅ Show image (optional)
        cv2.namedWindow("Synced Image", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Synced Image", 640, 480)
        cv2.imshow("Synced Image", frame)
        cv2.waitKey(1)


def main(args=None):
    rclpy.init(args=args)
    node = ImageLidarSyncNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()

