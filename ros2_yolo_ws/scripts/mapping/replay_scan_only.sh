#!/usr/bin/env bash
# Offline check of scan-only SLAM tracking: replay ONLY /scan (and /odom as a reference
# topic; slam_toolbox ignores it) from a recorded bag through the mapping-only setup, and log
# the SLAM pose (map->base_link) next to the bag's wheel /odom.
#
# No LiDAR, no motors, no drive bridge. The bag's /tf is NOT replayed: odom->base_link is
# the mapping-only static identity, so the pose can only come from scan matching.
# It runs in its own ROS domain (default 87) so it cannot reach the robot's live graph.
#
# Usage: replay_scan_only.sh BAG_DIR OUT_PREFIX [RATE]
set -u
BAG="$1"; OUT="$2"; RATE="${3:-1.0}"
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PARAMS="${SLAM_PARAMS:-$HERE/slam_params_mapping_only.yaml}"
TF_BIN=/opt/ros/humble/lib/tf2_ros/static_transform_publisher
export ROS_DOMAIN_ID="${REPLAY_DOMAIN_ID:-87}"

if [ "$(ps -o pgid= -p $$ | tr -d ' ')" != "$$" ]; then exec setsid "$0" "$@"; fi
set +u; source /opt/ros/humble/setup.bash; set -u
trap 'trap "" INT TERM; kill -INT -- -$$ 2>/dev/null; sleep 3; kill -TERM -- -$$ 2>/dev/null' EXIT

"$TF_BIN" --frame-id odom --child-frame-id base_link --ros-args -r __node:=replay_odom_tf &
"$TF_BIN" --frame-id base_link --child-frame-id laser --z 0.715 --roll 3.14159265 --yaw 0.10821 \
  --ros-args -r __node:=replay_laser_tf &
ros2 launch slam_toolbox online_async_launch.py slam_params_file:="$PARAMS" use_sim_time:=true \
  > "${OUT}_slam.log" 2>&1 &
sleep 5
python3 "$HERE/slam_pose_logger.py" "$OUT" --ros-args -p use_sim_time:=true &
LOGGER=$!
sleep 2
echo "[replay] domain $ROS_DOMAIN_ID, bag $BAG, rate $RATE"
ros2 bag play "$BAG" --topics /scan /odom --clock 50 --rate "$RATE"
echo "[replay] bag finished; waiting for logger"
wait "$LOGGER"
grep -c "range readings" "${OUT}_slam.log" | sed 's/^/[replay] scans dropped for beam count: /'
