import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Int32MultiArray
from cv_bridge import CvBridge
import cv2
from ultralytics import YOLO

class YoloROSNode(Node):
    def __init__(self):
        super().__init__('yolo_ros_node')

        # ----- Params -----
        self.declare_parameter('num_sectors', 9)   # ปรับจำนวน sector ได้จาก ROS param
        self.num_sectors = int(self.get_parameter('num_sectors').value)

        # ----- IO -----
        self.subscription = self.create_subscription(Image, '/image_raw',
                                                     self.listener_callback, 10)
        self.bridge = CvBridge()
        self.model = YOLO('/home/yakgreen001/yolov8n_openvino_model/')

        # Pub เดิม (compat)
        self.centroid_pub = self.create_publisher(Int32MultiArray, '/target_centroid', 10)
        # Pub ใหม่: [cx, cy, sector_id]
        self.centroid_sector_pub = self.create_publisher(Int32MultiArray, '/target_centroid_sector', 10)

        self.get_logger().info('YOLO Node Started')

    # ----- Utils -----
    def compute_sector_id(self, cx: int, width: int) -> int:
        N = max(1, self.num_sectors)
        # ป้องกัน div-by-zero และออกนอกภาพ
        sid = (cx * N) // max(1, width)
        return max(0, min(N - 1, sid))

    def draw_sectors(self, img):
        H, W = img.shape[:2]
        N = self.num_sectors
        sw = W // N
        for i in range(1, N):
            x = i * sw
            # เส้นแบ่งแนวตั้ง
            cv2.line(img, (x, 0), (x, H), (0, 255, 255), 1)
        # วาง label S0..S(N-1)
        for i in range(N):
            x_text = int((i + 0.5) * sw)
            cv2.putText(img, f"S{i}", (max(0, x_text - 12), 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    # ----- Callback -----
    def listener_callback(self, msg):
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        results = self.model(frame)[0]

        person_boxes = results.boxes
        if person_boxes is not None:
            person_boxes = person_boxes[person_boxes.cls == 0]

            frame_copy = frame.copy()
            H, W = frame_copy.shape[:2]

            # วาดเส้นแบ่ง sector ก่อน
            self.draw_sectors(frame_copy)

            for box in person_boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                label = f'target {conf:.2f}'

                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)

                # sector_id จาก cx
                sector_id = self.compute_sector_id(cx, W)

                # ---- Publish: centroid (เดิม) ----
                centroid_msg = Int32MultiArray()
                centroid_msg.data = [cx, cy]
                self.centroid_pub.publish(centroid_msg)

                # ---- Publish: centroid + sector ----
                centroid_sector_msg = Int32MultiArray()
                centroid_sector_msg.data = [cx, cy, sector_id]
                self.centroid_sector_pub.publish(centroid_sector_msg)

                # ---- Draw ----
                cv2.rectangle(frame_copy, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame_copy, f'{label}  S{sector_id}', (x1, max(0, y1 - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                cv2.circle(frame_copy, (cx, cy), 5, (0, 0, 255), -1)

                self.get_logger().info(f'Target centroid=({cx},{cy}) sector={sector_id}')

            cv2.namedWindow("YOLOv8 Person Detection", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("YOLOv8 Person Detection", 1280, 720)
            cv2.imshow("YOLOv8 Person Detection", frame_copy)
            cv2.waitKey(1)

def main(args=None):
    rclpy.init(args=args)
    node = YoloROSNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
