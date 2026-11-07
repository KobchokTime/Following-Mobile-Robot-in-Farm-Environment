#!/bin/bash
source /opt/ros/humble/setup.bash
source /home/yakgreen001/ydlidar_ros2_ws/install/setup.bash
export PYTHONPATH=/opt/ros/humble/local/lib/python3.10/dist-packages:/opt/ros/humble/lib/python3.10/site-packages
export QT_QPA_PLATFORM=offscreen
cd /home/yakgreen001/robot-code/ros2_yolo_ws/scripts
exec /home/yakgreen001/openvino_env/bin/python3 ros2_yolo_live.py --ros-args -p model_path:=/home/yakgreen001/yolov8n_openvino_model/
