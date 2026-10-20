# Offline twin of the following robot: ROS 2 Humble, the same distro as the robot.
# Build from the repository root:
#   docker build -f sim/docker/Dockerfile -t following-robot-twin .
FROM ros:humble-ros-base

# MCAP storage plugin, so bags from ros2_yolo_ws/scripts/record_robot_day.sh replay here.
# Set INSTALL_MCAP=0 when packages.ros.org is not reachable; sqlite3 bags still work.
ARG INSTALL_MCAP=1
RUN if [ "$INSTALL_MCAP" = "1" ]; then \
      apt-get update && apt-get install -y --no-install-recommends ros-humble-rosbag2-storage-mcap \
      && rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /repo
COPY ros2_yolo_ws/scripts ros2_yolo_ws/scripts
COPY sim sim
COPY tests tests
COPY scripts scripts

COPY sim/docker/entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "-m", "sim.twin.run_scenario", "--scenario", "all", "--bridge-mode", "both", "--out", "/repo/sim_runs"]
