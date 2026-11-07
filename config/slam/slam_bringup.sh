#!/usr/bin/env bash
# SLAM bringup for YDLidar TminiPro + ZLAC8015 diff-drive robot
# Run from the robot after:
#   1. start_lidar.sh is running (publishes /scan, frame=laser)
#   2. zlac_joystick_bridge.py is running (publishes /odom, TF odom->base_link)
#
# This script adds:
#   - static TF: base_link -> laser  (assume LiDAR at robot center, facing forward)
#   - slam_toolbox in online async mapping mode

set -e

ROS_SETUP_1=/opt/ros/humble/setup.bash
ROS_SETUP_2=~/ydlidar_ros2_ws/install/setup.bash

source "$ROS_SETUP_1"
source "$ROS_SETUP_2"

PARAMS_FILE=~/slam_params.yaml

echo "[slam_bringup] Starting static TF base_link -> laser ..."
ros2 run tf2_ros static_transform_publisher \
  --frame-id base_link \
  --child-frame-id laser \
  --x 0.0 --y 0.0 --z 0.10 \
  --roll 0 --pitch 0 --yaw 0 &
TF_PID=$!

sleep 1

echo "[slam_bringup] Starting slam_toolbox (online async mapping) ..."
ros2 launch slam_toolbox online_async_launch.py \
  params_file:="$PARAMS_FILE" \
  use_sim_time:=false &
SLAM_PID=$!

echo "[slam_bringup] Running — TF PID=$TF_PID  SLAM PID=$SLAM_PID"
echo "[slam_bringup] Drive the robot around to build the map."
echo "[slam_bringup] Save map when done:"
echo "   ros2 run nav2_map_server map_saver_cli -f ~/map_$(date +%Y%m%dT%H%M%S)"
echo ""
echo "Press Ctrl+C to stop all processes."

wait
