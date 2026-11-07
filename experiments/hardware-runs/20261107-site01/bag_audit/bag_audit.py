import glob, json, os, statistics, sys
import yaml
import rosbag2_py
from rclpy.serialization import deserialize_message
from std_msgs.msg import Float32MultiArray, Int32MultiArray
from geometry_msgs.msg import Twist

ROOT = os.path.expanduser("~/robot_day_recordings")
HFOV = 70.0
TYPES = {"/synced_target": Float32MultiArray, "/yolo_frame": Int32MultiArray, "/cmd_vel": Twist}
KEY = ["/image_raw", "/scan", "/yolo_frame", "/synced_target", "/target_fused_prob", "/cmd_vel", "/lidar_sector_dists"]

def med(v):
    return round(statistics.median(v), 3) if v else None

out = []
for run in sorted(glob.glob(os.path.join(ROOT, "2026*"))):
    rec = os.path.join(run, "recording")
    meta = os.path.join(rec, "metadata.yaml")
    row = {"run": os.path.basename(run)}
    if not os.path.isfile(meta):
        row["status"] = "NO_BAG"
        out.append(row)
        continue
    info = yaml.safe_load(open(meta))["rosbag2_bagfile_information"]
    storage = info.get("storage_identifier", "sqlite3")
    row["storage"] = storage
    row["duration_s"] = round(info["duration"]["nanoseconds"] / 1e9, 2)
    counts = {t["topic_metadata"]["name"]: t["message_count"] for t in info["topics_with_message_count"]}
    row["counts"] = {k: counts.get(k, 0) for k in KEY}
    try:
        r = rosbag2_py.SequentialReader()
        r.open(rosbag2_py.StorageOptions(uri=rec, storage_id=storage),
               rosbag2_py.ConverterOptions("cdr", "cdr"))
        r.set_filter(rosbag2_py.StorageFilter(topics=list(TYPES)))
        dist, cxs, frame_w, cmd_nz, cmd_n, max_v = [], [], None, 0, 0, 0.0
        while r.has_next():
            topic, data, _ = r.read_next()
            m = deserialize_message(data, TYPES[topic])
            if topic == "/synced_target" and len(m.data) >= 3:
                cx, d = m.data[0], m.data[2]
                if d == d and d > 0:
                    dist.append(d)
                cxs.append(cx)
            elif topic == "/yolo_frame" and len(m.data) >= 4 and frame_w is None:
                frame_w = m.data[2]
            elif topic == "/cmd_vel":
                cmd_n += 1
                if abs(m.linear.x) > 1e-3 or abs(m.angular.z) > 1e-3:
                    cmd_nz += 1
                max_v = max(max_v, abs(m.linear.x))
        w = frame_w or 640
        bearings = [(cx - w / 2) / (w / 2) * (HFOV / 2) for cx in cxs]
        row.update({
            "frame_w": frame_w,
            "target_dist_m_median": med(dist),
            "target_dist_m_min": round(min(dist), 3) if dist else None,
            "target_dist_m_max": round(max(dist), 3) if dist else None,
            "image_bearing_deg_median_plus_is_image_right": med(bearings),
            "cmd_vel_n": cmd_n, "cmd_vel_nonzero": cmd_nz, "cmd_vel_max_abs_vx": round(max_v, 3),
            "status": "OK",
        })
    except Exception as e:
        row["status"] = f"READ_ERROR {type(e).__name__}: {e}"
    out.append(row)

json.dump(out, sys.stdout, indent=1)
