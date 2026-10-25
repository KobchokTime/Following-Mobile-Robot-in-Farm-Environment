"""Start the whole following pipeline with one command.

    ros2 launch ros2_yolo_ws/launch/follow_bringup.launch.py max_speed_mps:=0.5

Starts, in data-flow order: YOLO (ros2_yolo_live.py), lidar_sectorizer, sync_fusion, fusion_prob,
follow_stop and the ZLAC drive bridge. The camera (/image_raw) and LiDAR (/scan) drivers are not
part of the repository; pass their commands with camera_cmd:=... and lidar_cmd:=..., or start them
yourself first. Run tools/robot_day/preflight.py before driving.

Arguments (default):
    speed_mode (mps)        bridge mapping; "legacy" also sets follow_stop max_decel to 0.0
    max_speed_mps (1.4)     per-wheel cap; start robot days at 0.5
    max_accel_mps2 (1.0)
    wheel_radius_m (0.085)  measured value from config/motor_wheel_calibration.md
    track_width_m (0.40)
    turn_dir (1.0)          -1.0 if turn_check.py shows the robot turning the wrong way
    port (/dev/ttyUSB1)     ZLAC8015D serial port
    model_path (/home/yakgreen001/yolov8n_openvino_model/)
    target_distance (0.5)   follow set-point in metres
    latency_s (0.2)         capture -> /cmd_vel from E2; the braking cap allows for it
    bridge (true)           false = everything but the motors (bench test)
    camera_cmd, lidar_cmd   shell commands for the drivers (empty = not started here)
"""

from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"

DEFAULTS = {
    "speed_mode": "mps",
    "max_speed_mps": "1.4",
    "max_accel_mps2": "1.0",
    "wheel_radius_m": "0.085",
    "track_width_m": "0.40",
    "turn_dir": "1.0",
    "port": "/dev/ttyUSB1",
    "model_path": "/home/yakgreen001/yolov8n_openvino_model/",
    "target_distance": "0.5",
    "latency_s": "0.2",
    "bridge": "true",
    "camera_cmd": "",
    "lidar_cmd": "",
}


def node(name, script, params):
    args = []
    for key, value in params.items():
        args += ["-p", f"{key}:={value}"]
    cmd = ["python3", str(SCRIPTS / script)] + (["--ros-args", *args] if args else [])
    return ExecuteProcess(cmd=cmd, cwd=str(SCRIPTS), name=name, output="screen")


def actions(a):
    """Build the processes from the launch arguments `a` (all strings)."""
    out = []
    for name in ("camera_cmd", "lidar_cmd"):
        if a[name].strip():
            out.append(ExecuteProcess(cmd=[a[name]], shell=True, name=name[:-4], output="screen"))
    out += [
        node("yolo", "ros2_yolo_live.py", {"model_path": a["model_path"]}),
        node("lidar_sectorizer", "Lidar/lidar_sectorizer_node.py", {}),
        node("sync_fusion", "Image/sync_fusion_node.py", {}),
        node("fusion_prob", "Image/fusion_prob_node.py", {}),
        # max_decel is in m/s^2, which only means something on the "mps" bridge
        node("follow_stop", "MAIN/Control/follow_stop_node.py",
             {"target_distance": a["target_distance"], "latency_s": a["latency_s"],
              "bridge_accel_mps2": a["max_accel_mps2"],  # wheel-speed estimate for the braking cap
              "max_decel": "0.0" if a["speed_mode"] == "legacy" else "0.8"}),
    ]
    if a["bridge"].lower() in ("true", "1", "yes"):
        out.append(node("zlac_bridge", "MAIN/Control/zlac_joystick_bridge.py",
                        {k: a[k] for k in ("speed_mode", "max_speed_mps", "max_accel_mps2", "wheel_radius_m",
                                           "track_width_m", "turn_dir", "port")}))
    return out


FLOATS = ("max_speed_mps", "max_accel_mps2", "wheel_radius_m", "track_width_m", "turn_dir", "target_distance", "latency_s")


def launch_setup(context):
    a = {k: context.launch_configurations.get(k, v) for k, v in DEFAULTS.items()}
    for k in FLOATS:  # ROS rejects turn_dir:=-1 for a float parameter, so always pass -1.0
        a[k] = str(float(a[k]))
    return actions(a)


def generate_launch_description():
    return LaunchDescription([DeclareLaunchArgument(k, default_value=v) for k, v in DEFAULTS.items()]
                             + [OpaqueFunction(function=launch_setup)])
