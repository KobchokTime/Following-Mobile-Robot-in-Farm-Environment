#!/usr/bin/env python3
"""Check the robot is ready before a run: files, ports, disk, and (with --live) every topic's rate.

    python3 tools/robot_day/preflight.py                  # static checks only, no ROS needed
    python3 tools/robot_day/preflight.py --live           # also listen to the running pipeline for 5 s and
                                                          # read back the running obstacle parameters

Start the pipeline first for --live (ros2 launch ros2_yolo_ws/launch/follow_bringup.launch.py).
Each line is PASS, WARN or FAIL; the exit code is 1 if anything failed.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = "/home/yakgreen001/yolov8n_openvino_model/"
DEFAULT_PORT = "/dev/ttyUSB1"
DEFAULT_OUTPUT = os.environ.get("ROBOT_DAY_OUTPUT", str(Path.home() / "robot_day_recordings"))

# topic: (lowest acceptable rate in Hz, lower rate that only warns). None = must merely exist.
TOPIC_RATES = {
    "/image_raw": (5.0, 10.0),
    "/scan": (4.0, 7.0),
    "/yolo_frame": (1.0, 3.0),          # one per processed frame, with or without a person
    "/lidar_sector_dists": (4.0, 7.0),
}
MIN_FREE_GB = 5.0
MEASURED_RE = re.compile(r"wheel_radius_m\s*=\s*([0-9.]+)\s*\(measured")


def result(level, what, detail=""):
    return (level, what, detail)


def check_model(path):
    p = Path(path)
    if not p.exists():
        return result("FAIL", "YOLO model", f"{path} not found (pass --model or model_path:=)")
    if p.is_dir() and not list(p.glob("*.xml")):
        return result("FAIL", "YOLO model", f"no OpenVINO .xml in {path}")
    return result("PASS", "YOLO model", str(path))


def check_port(port):
    if not os.path.exists(port):
        return result("FAIL", "ZLAC serial port", f"{port} missing (is the USB-RS485 adapter plugged in?)")
    if not os.access(port, os.R_OK | os.W_OK):
        return result("FAIL", "ZLAC serial port", f"{port} not writable (add the user to the dialout group)")
    return result("PASS", "ZLAC serial port", port)


def check_disk(path, min_gb=MIN_FREE_GB):
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    free = shutil.disk_usage(str(p)).free / 1e9
    level = "PASS" if free >= min_gb else "WARN"
    return result(level, "disk for recordings", f"{free:.1f} GB free at {p} (want {min_gb:.0f} GB)")


def check_speed_params(speed_mode, wheel_radius, max_speed, max_accel):
    """The same limits the bridge enforces, plus the robot-day advice to start slow."""
    if speed_mode not in ("mps", "legacy"):
        return result("FAIL", "bridge parameters", f"speed_mode {speed_mode!r} is not 'mps' or 'legacy'")
    if not 0.03 <= wheel_radius <= 0.3:
        return result("FAIL", "bridge parameters", f"wheel_radius_m {wheel_radius} is not a wheel")
    if max_speed <= 0 or max_accel <= 0:
        return result("FAIL", "bridge parameters", "max_speed_mps and max_accel_mps2 must be positive")
    if max_speed > 0.5:
        return result("WARN", "bridge parameters",
                      f"max_speed_mps {max_speed}: the protocol starts at 0.5 until speed_check.py has passed")
    return result("PASS", "bridge parameters", f"{speed_mode}, r={wheel_radius} m, {max_speed} m/s")


def check_obstacle_params(obstacle_stop, avoid_trail, trail_hold_s):
    """The obstacle settings robot day needs (T18 re-review, Codex 2026-11-01 09:52, items 3-4).

    The LiDAR stop must be on: sync_fusion's occlusion range and give-way floor leave the near person to it.
    The trail drives on dead reckoning, so it stays off until checked against the wheels, and never drives
    without target messages.
    """
    if not obstacle_stop:
        return result("FAIL", "obstacle parameters", "obstacle_stop must be true on the robot")
    if trail_hold_s > 0.0:
        return result("FAIL", "obstacle parameters", f"trail_hold_s {trail_hold_s} > 0 drives without target messages")
    if avoid_trail:
        return result("WARN", "obstacle parameters", "avoid_trail on: only after the trail is checked on the wheels")
    return result("PASS", "obstacle parameters", "obstacle_stop on, avoid_trail off, no target-free driving")


# the running nodes' parameters --live reads back (T18, Codex 2026-11-01 12:49): the flags above describe what the
# operator meant; these are what the nodes actually run with
LIVE_PARAMS = (("/follow_stop_node", "obstacle_stop"), ("/sync_fusion_node", "obstacle_stop"),
               ("/follow_stop_node", "avoid_trail"), ("/follow_stop_node", "trail_hold_s"))
PARAM_VALUE_RE = re.compile(r"value is:\s*(\S+)")


def param_value(text):
    """The value from `ros2 param get` output ("Boolean value is: True"), as bool, float or str; None if absent."""
    m = PARAM_VALUE_RE.search(text or "")
    if not m:
        return None
    v = m.group(1)
    if v in ("True", "False"):
        return v == "True"
    try:
        return float(v)
    except ValueError:
        return v


def check_live_params(get):
    """FAIL unless every running node reports the robot-day obstacle settings. get(node, name) -> value or None."""
    vals = {(n, k): get(n, k) for n, k in LIVE_PARAMS}
    missing = [f"{n} {k}" for (n, k), v in vals.items() if v is None]
    if missing:
        return result("FAIL", "running parameters", "not readable: " + ", ".join(missing))
    if vals[("/follow_stop_node", "obstacle_stop")] is not True or vals[("/sync_fusion_node", "obstacle_stop")] is not True:
        return result("FAIL", "running parameters", "obstacle_stop must be true on follow_stop_node and sync_fusion_node")
    hold = vals[("/follow_stop_node", "trail_hold_s")]
    if not isinstance(hold, float) or hold > 0.0:  # not a number is a FAIL too, not a crash
        return result("FAIL", "running parameters", "trail_hold_s > 0 drives without target messages")
    if vals[("/follow_stop_node", "avoid_trail")] is not False:
        return result("WARN", "running parameters", "avoid_trail on: only after the trail is checked on the wheels")
    return result("PASS", "running parameters", "obstacle_stop on (both nodes), avoid_trail off, trail_hold_s 0")


def ros2_param_get(node, name, timeout=10.0):
    try:
        out = subprocess.run(["ros2", "param", "get", node, name], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return param_value(out.stdout) if out.returncode == 0 else None


def check_calibration(path=ROOT / "config" / "motor_wheel_calibration.md"):
    """Looks for a line like `wheel_radius_m = 0.083 (measured 2026-11-02)`."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    m = MEASURED_RE.search(text)
    if m:
        return result("PASS", "wheel radius", f"measured {m.group(1)} m; pass it as wheel_radius_m:=")
    return result("WARN", "wheel radius", "not measured yet; run speed_check.py before following above 0.5 m/s")


def check_git():
    try:
        sha = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return result("WARN", "code version", "not a git checkout")
    if dirty:
        return result("WARN", "code version", f"{sha} with uncommitted changes; recordings will not match a commit")
    return result("PASS", "code version", sha)


def rate_verdict(topic, count, seconds, limits=None):
    """PASS/WARN/FAIL for `count` messages in `seconds` on `topic`."""
    fail_hz, warn_hz = limits or TOPIC_RATES[topic]
    hz = count / seconds if seconds > 0 else 0.0
    level = "FAIL" if hz < fail_hz else "WARN" if hz < warn_hz else "PASS"
    return result(level, f"rate {topic}", f"{hz:.1f} Hz (want {warn_hz:g})")


def scan_verdict(ranges, range_max):
    """Warn when most rays return nothing, e.g. a covered or unplugged LiDAR."""
    if not ranges:
        return result("FAIL", "scan content", "no scan received")
    good = sum(1 for r in ranges if r == r and 0.0 < r < range_max) / len(ranges)
    level = "PASS" if good >= 0.2 else "WARN"
    return result(level, "scan content", f"{good:.0%} of rays return a range")


def live_checks(seconds):
    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from rosidl_runtime_py.utilities import get_message

    rclpy.init()
    node = rclpy.create_node("preflight")
    out = []
    try:
        end = time.monotonic() + 1.5  # let discovery finish
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.1)
        types = dict(node.get_topic_names_and_types())
        counts = {t: 0 for t in TOPIC_RATES}
        last_scan = {}

        def counter(topic):
            def cb(msg):
                counts[topic] += 1
                if topic == "/scan":
                    last_scan["ranges"], last_scan["max"] = list(msg.ranges), msg.range_max
            return cb

        for topic in TOPIC_RATES:
            if topic in types:
                node.create_subscription(get_message(types[topic][0]), topic, counter(topic), qos_profile_sensor_data)
        start = time.monotonic()
        while time.monotonic() - start < seconds:
            rclpy.spin_once(node, timeout_sec=0.05)
        elapsed = time.monotonic() - start
        for topic in TOPIC_RATES:
            if topic not in types:
                out.append(result("FAIL", f"rate {topic}", "nobody publishes it"))
            else:
                out.append(rate_verdict(topic, counts[topic], elapsed))
        if "/scan" in types:
            out.append(scan_verdict(last_scan.get("ranges", []), last_scan.get("max", 0.0)))
        subs = node.count_subscribers("/cmd_vel")
        pubs = node.count_publishers("/cmd_vel")
        out.append(result("PASS" if subs else "FAIL", "drive bridge", f"{subs} subscriber(s) on /cmd_vel"))
        out.append(result("PASS" if pubs else "FAIL", "follow_stop", f"{pubs} publisher(s) on /cmd_vel"))
    finally:
        node.destroy_node()
        rclpy.shutdown()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true", help="also check the running pipeline's topics")
    ap.add_argument("--seconds", type=float, default=5.0, help="how long to listen with --live")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--port", default=DEFAULT_PORT)
    ap.add_argument("--output-root", default=DEFAULT_OUTPUT)
    ap.add_argument("--speed-mode", default="mps")
    ap.add_argument("--wheel-radius", type=float, default=0.085)
    ap.add_argument("--max-speed", type=float, default=1.4)
    ap.add_argument("--max-accel", type=float, default=1.0)
    ap.add_argument("--obstacle-stop", default="true", help="as passed to the launch file (obstacle_stop:=...)")
    ap.add_argument("--avoid-trail", default="false", help="as passed to the launch file (avoid_trail:=...)")
    ap.add_argument("--trail-hold", type=float, default=0.0, help="follow_stop trail_hold_s, if set")
    args = ap.parse_args(argv)

    checks = [check_git(), check_model(args.model), check_port(args.port), check_disk(args.output_root),
              check_speed_params(args.speed_mode, args.wheel_radius, args.max_speed, args.max_accel),
              check_obstacle_params(args.obstacle_stop.lower() in ("true", "1", "yes"),
                                    args.avoid_trail.lower() in ("true", "1", "yes"), args.trail_hold),
              check_calibration()]
    if args.live:
        checks += live_checks(args.seconds)
        checks.append(check_live_params(ros2_param_get))
    for level, what, detail in checks:
        print(f"[{level}] {what}: {detail}")
    failed = sum(1 for c in checks if c[0] == "FAIL")
    print("ready" if not failed else f"{failed} check(s) failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
