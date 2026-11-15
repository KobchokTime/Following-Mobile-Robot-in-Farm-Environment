#!/bin/bash
# usage: start_follow.sh off|on   (off = no drive bridge; on = bridge with the 2026-11-07 tested limits)
source /opt/ros/humble/setup.bash
source ~/ydlidar_ros2_ws/install/setup.bash
source ~/openvino_env/bin/activate
cd ~/robot-follow-clean-20261107 || exit 1
CAM="/opt/ros/humble/lib/v4l2_camera/v4l2_camera_node --ros-args -p video_device:=/dev/video0"
LID="ros2 launch ydlidar_ros2_driver x3_ydlidar_launch.py params_file:=/home/yakgreen001/ydlidar_tmini.yaml"
L=ros2_yolo_ws/launch/follow_bringup.launch.py
# LiDAR remounted at 0.70-0.73 m on 2026-11-15; camera vs LiDAR person bearing differed by 6.2 deg at 1.6 m and 3.8 m
LIDAR_TF="lidar_angle_offset_deg:=6.2 lidar_angle_sign:=-1.0"
case "$1" in
  off) exec ros2 launch $L bridge:=false $LIDAR_TF camera_cmd:="$CAM" lidar_cmd:="$LID" ;;
  on)  exec ros2 launch $L max_speed_mps:=0.5 wheel_radius_m:=0.085 forward_dir:=-1.0 turn_dir:=1.0 $LIDAR_TF \
            camera_cmd:="$CAM" lidar_cmd:="$LID" ;;
  *)   echo "usage: $0 off|on"; exit 2 ;;
esac
