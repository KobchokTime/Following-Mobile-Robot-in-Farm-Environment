#!/usr/bin/env bash
# Joystick SLAM mapping, 2026-11-15 LiDAR mount (0.70-0.73 m, mirrored scan, yaw +6.2 deg).
# Starts: LiDAR driver, old robot-code bridge (publishes /odom + odom->base_link, capped 0.5 m/s),
# joy + teleop (hold button 4 to drive), static TF base_link->laser, slam_toolbox. Ctrl-C stops all.
source /opt/ros/humble/setup.bash
source ~/ydlidar_ros2_ws/install/setup.bash
trap 'echo "[slam_map] stopping"; kill -INT 0; wait; exit 0' INT TERM

ros2 launch ydlidar_ros2_driver x3_ydlidar_launch.py params_file:=/home/yakgreen001/ydlidar_tmini.yaml &
sleep 3
python3 ~/robot-code/ros2_yolo_ws/scripts/MAIN/Control/zlac_joystick_bridge.py --ros-args \
  -p max_speed_mps:=0.5 -p speed_mode:=mps -p port:=/dev/ttyUSB1 &
ros2 run joy joy_node &
ros2 run teleop_twist_joy teleop_node --ros-args --params-file /home/yakgreen001/joy_teleop.yaml &
# laser angle a -> robot bearing -a + 6.2 deg: roll pi mirrors, then yaw +0.1082 rad
ros2 run tf2_ros static_transform_publisher --frame-id base_link --child-frame-id laser \
  --x 0.0 --y 0.0 --z 0.715 --roll 3.14159265 --pitch 0 --yaw 0.10821 &
sleep 2
ros2 launch slam_toolbox online_async_launch.py slam_params_file:=/home/yakgreen001/slam_params_1115.yaml use_sim_time:=false &
echo "[slam_map] running. Hold joystick button 4 to drive. Save with:"
echo "  ros2 run nav2_map_server map_saver_cli -f ~/map_\$(date +%Y%m%dT%H%M%S)"
wait
