#!/usr/bin/env bash
# Mapping-only SLAM bringup. It never actuates the wheels.
#
# Starts only: the YDLidar driver (reused if already running), static TF odom->base_link
# (identity), static TF base_link->laser (2026-11-15 mount), and slam_toolbox
# (online async, slam_params_mapping_only.yaml). It does NOT start the ZLAC drive bridge,
# joystick, teleop or any node that opens the motor serial port, and it refuses to start if
# one of those is already running.
#
# Odometry: there is none. odom->base_link is a fixed identity, so slam_toolbox tracks the
# robot from scan matching alone. Move the robot slowly (carried or pushed, < 0.3 m/s and
# < 30 deg/s), and only with the operator's OK; the params process scans by time, not by
# odometry travel.
#
# Usage (on the robot):  ~/slam_mapping_only/slam_mapping_only.sh        # Ctrl-C stops all
#                        ~/slam_mapping_only/slam_mapping_only.sh stop   # stop a detached run
# Watch from the PC:     py -3 ros2_yolo_ws/scripts/mapping/live_slam_viewer.py
# Save on the robot:     ros2 run nav2_map_server map_saver_cli -f ~/map_$(date +%Y%m%dT%H%M%S)
set -u

HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PARAMS="${SLAM_PARAMS:-$HERE/slam_params_mapping_only.yaml}"
LIDAR_PARAMS="${LIDAR_PARAMS:-$HOME/ydlidar_tmini.yaml}"
PIDFILE="$HOME/.slam_mapping_only.pgid"
TF_BIN=/opt/ros/humble/lib/tf2_ros/static_transform_publisher
# Processes that may command the wheels. Their presence aborts this script.
MOTOR_PATTERN='zlac|drive_bridge|joystick_bridge|teleop_node|teleop_twist|joy_node|Follow_stop_node|start_bridge|start_follow|slam_map_1115|slam_bringup'

if [ "${1:-}" = "stop" ]; then
  if [ -f "$PIDFILE" ]; then
    pg="$(cat "$PIDFILE")"; echo "[mapping-only] stopping process group $pg"
    kill -INT -- "-$pg" 2>/dev/null; sleep 4; kill -TERM -- "-$pg" 2>/dev/null; rm -f "$PIDFILE"
  else
    echo "[mapping-only] no detached run recorded"
  fi
  exit 0
fi

# Own process group, so one signal stops every child (and "stop" can find them).
if [ "$(ps -o pgid= -p $$ | tr -d ' ')" != "$$" ]; then exec setsid "$0" "$@"; fi

set +u   # ROS setup scripts read unset variables
source /opt/ros/humble/setup.bash
source "$HOME/ydlidar_ros2_ws/install/setup.bash"
set -u

# Skip this script's own ancestors (e.g. an ssh "bash -c" line that merely mentions a pattern).
ancestors=" $$ "; p=$$
while [ "${p:-1}" -gt 1 ]; do p=$(ps -o ppid= -p "$p" | tr -d ' '); ancestors="$ancestors${p:-1} "; done
motor=$(pgrep -af "$MOTOR_PATTERN" | while read -r pid rest; do
  case "$ancestors" in *" $pid "*) ;; *) echo "$pid $rest" ;; esac; done)
if [ -n "$motor" ]; then
  echo "[mapping-only] REFUSED: a process that can drive the wheels is running:"; echo "$motor"
  exit 2
fi
if pgrep -f "slam_toolbox|async_slam_toolbox_node" >/dev/null; then
  echo "[mapping-only] REFUSED: slam_toolbox is already running"; exit 2
fi
[ -f "$PARAMS" ] || { echo "[mapping-only] missing params $PARAMS"; exit 2; }

echo $$ > "$PIDFILE"
cleanup() {
  local code="$1"
  trap '' INT TERM; trap - EXIT   # ignore our own group signal while stopping the children
  echo "[mapping-only] stopping"
  kill -INT -- "-$$" 2>/dev/null; sleep 3; kill -TERM -- "-$$" 2>/dev/null
  rm -f "$PIDFILE"; exit "$code"
}
trap 'cleanup 0' INT TERM
trap 'cleanup $?' EXIT

if pgrep -f ydlidar_ros2_driver_node >/dev/null; then
  echo "[mapping-only] LiDAR driver already running; reusing it"
else
  echo "[mapping-only] starting LiDAR driver ($LIDAR_PARAMS)"
  ros2 launch ydlidar_ros2_driver x3_ydlidar_launch.py params_file:="$LIDAR_PARAMS" &
  sleep 4
fi

if [ -f "$HERE/lidar_health.py" ]; then
  python3 "$HERE/lidar_health.py" || {
    echo "[mapping-only] LiDAR degraded: stop, restart the LiDAR driver, and run again"; exit 1; }
fi

# No odometry source: fixed identity. Nothing else may publish odom->base_link.
"$TF_BIN" --frame-id odom --child-frame-id base_link --ros-args -r __node:=mapping_only_odom_tf &
# 2026-11-15 mount: z 0.715 m, roll pi (mirrored scan), yaw +6.2 deg (bearing = -raw + 6.2 deg).
"$TF_BIN" --frame-id base_link --child-frame-id laser --z 0.715 --roll 3.14159265 --yaw 0.10821 \
  --ros-args -r __node:=mapping_only_laser_tf &
sleep 2

# Humble online_async_launch.py takes slam_params_file:= (params_file:= is silently ignored).
ros2 launch slam_toolbox online_async_launch.py slam_params_file:="$PARAMS" use_sim_time:=false &

echo "[mapping-only] running (pgid $$). No drive bridge. Ctrl-C or '$0 stop' to end."
wait
