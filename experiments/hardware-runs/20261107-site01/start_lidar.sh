#!/bin/bash
exec > /home/yakgreen001/lidar_startup.log 2>&1
source /opt/ros/humble/setup.bash
source /home/yakgreen001/ydlidar_ros2_ws/install/setup.bash
exec ros2 launch ydlidar_ros2_driver x3_ydlidar_launch.py params_file:=/home/yakgreen001/ydlidar_tmini.yaml
