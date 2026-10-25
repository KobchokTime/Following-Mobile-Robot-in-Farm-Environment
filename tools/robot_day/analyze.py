#!/usr/bin/env python3
"""Turn robot-day recordings into the numbers for experiments E1-E4 (docs/robot_day_protocol.md).

    python3 tools/robot_day/analyze.py ROOT [ROOT ...] [--out report.json]

Each ROOT is a recording folder from `ros2_yolo_ws/scripts/record_robot_day.sh` (a
`recording.json` plus the bag in `recording/`), or a folder holding several of them, or a bare
rosbag2 folder (the label then comes from `--label`). The scenario label says which experiment
a recording belongs to and holds its ground truth:

    e1_b<bearing deg>_d<distance m>   one person on a tape mark, e.g. e1_b-20_d2.0 (left positive)
    e3_d<distance m>_<front|back>     one person facing towards or away from the robot
    e4_<diff|same>_<sun|shade>        two people side by side, A on the left, B on the right
    e4_overlap_<diff|same>_<sun|shade> the same with B partly behind A in the image
    e6_<move>_<n>                     one person walking and the robot following, e.g. e6_turn90_2
    anything else                     used for E2 only

E2 (latency) uses every recording that has `/yolo_frame`. Reading bags needs ROS 2 (rosbag2_py);
the statistics below are plain Python, so they are unit-tested without ROS.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from bisect import bisect_left, bisect_right
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

CAMERA_HFOV_DEG = 70.0
LIDAR_MOUNT_YAW_RAD = math.pi  # the LiDAR faces backwards (lidar_sectorizer_node.py angle_offset 180)
PERSON_RADIUS_M = 0.2

# ------------------------------------------------------------------ labels


def parse_label(label: str) -> dict:
    """Experiment and ground truth from a scenario label (see module docstring)."""
    m = re.fullmatch(r"e1_b(-?\d+(?:\.\d+)?)_d(\d+(?:\.\d+)?)", label)
    if m:
        return {"exp": "e1", "bearing_deg": float(m.group(1)), "distance_m": float(m.group(2))}
    m = re.fullmatch(r"e3_d(\d+(?:\.\d+)?)_(front|back)", label)
    if m:
        return {"exp": "e3", "distance_m": float(m.group(1)), "facing": m.group(2)}
    m = re.fullmatch(r"e6_([a-z0-9]+(?:_[a-z0-9]+)*?)_(\d+)", label)
    if m:
        return {"exp": "e6", "move": m.group(1), "run": int(m.group(2))}
    m = re.fullmatch(r"e4_(overlap_)?(diff|same)_(sun|shade)", label)
    if m:
        return {"exp": "e4", "overlap": bool(m.group(1)), "clothes": m.group(2), "light": m.group(3)}
    return {"exp": "other"}


# ------------------------------------------------------------------ geometry


def camera_bearing_rad(cx: float, width: int, hfov_deg: float = CAMERA_HFOV_DEG) -> float:
    """Same pinhole model as Image/sync_fusion_node.py: left positive."""
    f = (width / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)
    return math.atan2(width / 2.0 - cx, f)


def scan_points(angle_min: float, angle_inc: float, ranges: Sequence[float],
                mount_yaw: float = LIDAR_MOUNT_YAW_RAD) -> List[Tuple[float, float]]:
    """(robot-frame bearing, range) of every finite return, bearing wrapped to [-pi, pi)."""
    out = []
    for i, r in enumerate(ranges):
        if math.isfinite(r) and r > 0.0:
            a = (angle_min + i * angle_inc + mount_yaw + math.pi) % (2.0 * math.pi) - math.pi
            out.append((a, r))
    return out


def nearest_return(points: Sequence[Tuple[float, float]], bearing: float, window_rad: float):
    """Closest return within +-window of a bearing, as (bearing, range), or None."""
    best = None
    for a, r in points:
        d = (a - bearing + math.pi) % (2.0 * math.pi) - math.pi
        if abs(d) <= window_rad and (best is None or r < best[1]):
            best = (a, r)
    return best


# ------------------------------------------------------------------ messages


def parse_frame(data: Sequence[int]) -> dict:
    """A /yolo_frame message: [sec, nsec, width, height, n, (x1, y1, x2, y2, conf_milli, cb, cr) * n]."""
    sec, nsec, width, height, n = data[:5]
    boxes = [tuple(data[5 + 7 * i: 12 + 7 * i]) for i in range(n)]
    return {"stamp": sec + nsec * 1e-9, "width": width, "height": height, "boxes": boxes}


def box_clipped(box: Sequence[int], height: int, margin: int = 2) -> bool:
    """True if the box touches the top or bottom of the image, so the person is cut off."""
    return box[1] <= margin or box[3] >= height - 1 - margin


def percentile(values: Sequence[float], q: float) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


# ------------------------------------------------------------------ experiments


def e1_stats(truth: dict, detections: Sequence[Tuple[float, float]], scans: Sequence[Tuple[float, list]],
             width: int = 640, window_deg: float = 10.0) -> dict:
    """Camera and LiDAR bearing against a tape mark, and how often the LiDAR return is the person.

    detections: (time, cx); scans: (time, points from scan_points), sorted by time.
    """
    true_b = math.radians(truth["bearing_deg"])
    expect_r = truth["distance_m"] - PERSON_RADIUS_M  # tape marks the person's centre
    cam_err, lidar_err, range_err, hits = [], [], [], 0
    times = [t for t, _ in scans]
    for t, cx in detections:
        b = camera_bearing_rad(cx, width)
        cam_err.append(math.degrees(b - true_b))
        if not scans:
            continue
        i = min(range(max(0, bisect_left(times, t) - 1), min(len(scans), bisect_left(times, t) + 1)),
                key=lambda j: abs(times[j] - t))
        ret = nearest_return(scans[i][1], b, math.radians(window_deg))
        if ret is None:
            continue
        lidar_err.append(math.degrees(ret[0] - true_b))
        range_err.append(ret[1] - expect_r)
        hits += abs(ret[1] - expect_r) <= 0.2
    summary = lambda xs: None if not xs else {  # noqa: E731
        "n": len(xs), "bias": round(statistics.fmean(xs), 3),
        "mae": round(statistics.fmean(abs(x) for x in xs), 3)}
    return {"truth": truth, "detections": len(detections), "camera_bearing_err_deg": summary(cam_err),
            "lidar_bearing_err_deg": summary(lidar_err), "lidar_range_err_m": summary(range_err),
            "lidar_hit_share": round(hits / len(detections), 3) if detections else None}


def e2_latency(frames: Sequence[Tuple[float, dict]], cmd_times: Sequence[float], max_plausible_s: float = 5.0) -> dict:
    """Capture -> /yolo_frame (inference), /yolo_frame -> next /cmd_vel (fusion + control), and the
    end-to-end capture -> /cmd_vel delay of each frame.

    frames: (receive time, parsed /yolo_frame); cmd_times: receive times of /cmd_vel, sorted.
    Only frames with at least one person count for the control and end-to-end parts. Receive times
    are the recorder's, so they include its own small delay. A capture stamp of 0, from another
    clock, or later than its receive time makes the capture-based parts meaningless; such frames are
    left out and counted in "bad_stamps". The end-to-end median is taken over frames, not by adding
    the two component medians.
    """
    infer, ctrl, total, bad = [], [], [], 0
    for t, f in frames:
        d = t - f["stamp"]
        ok = 0.0 <= d <= max_plausible_s
        bad += not ok
        if ok:
            infer.append(d)
        if f["boxes"]:
            j = bisect_right(cmd_times, t)
            if j < len(cmd_times):
                ctrl.append(cmd_times[j] - t)
                if ok:
                    total.append(cmd_times[j] - f["stamp"])
    ms = lambda xs, q: None if not xs else round(1000.0 * percentile(xs, q), 1)  # noqa: E731
    return {"frames": len(frames), "bad_stamps": bad,
            "capture_to_detection_ms": {"median": ms(infer, 0.5), "p95": ms(infer, 0.95)},
            "detection_to_cmd_vel_ms": {"median": ms(ctrl, 0.5), "p95": ms(ctrl, 0.95)},
            "capture_to_cmd_vel_ms": {"median": ms(total, 0.5), "p95": ms(total, 0.95), "n": len(total)}}


def e3_stats(truth: dict, frames: Sequence[Tuple[float, dict]]) -> dict:
    """Detection rate, clipping and confidence at one distance."""
    n = len(frames)
    seen = [f for _, f in frames if f["boxes"]]
    # the largest box in each frame is the person on the mark
    largest = [(max(f["boxes"], key=lambda b: (b[2] - b[0]) * (b[3] - b[1])), f["height"]) for f in seen]
    dur = frames[-1][0] - frames[0][0] if n > 1 else 0.0
    return {"truth": truth, "frames": n, "fps": round((n - 1) / dur, 2) if dur > 0 else None,
            "detection_rate": round(len(seen) / n, 3) if n else None,
            "clipped_share": round(sum(box_clipped(b, h) for b, h in largest) / len(largest), 3) if largest else None,
            "mean_conf": round(statistics.fmean(b[4] for b, _ in largest) / 1000.0, 3) if largest else None}


def e4_stats(truth: dict, frames: Sequence[Tuple[float, dict]]) -> dict:
    """Clothing chroma of person A (left box) and B (right box) when both are detected."""
    a, b = [], []
    for _, f in frames:
        if len(f["boxes"]) == 2:
            left, right = sorted(f["boxes"], key=lambda bx: bx[0] + bx[2])
            a.append((left[5], left[6]))
            b.append((right[5], right[6]))
    if len(a) < 2:
        return {"truth": truth, "frames_with_two": len(a)}
    mean = lambda pts: (statistics.fmean(p[0] for p in pts), statistics.fmean(p[1] for p in pts))  # noqa: E731
    ma, mb = mean(a), mean(b)
    dist = lambda p, m: math.hypot(p[0] - m[0], p[1] - m[1])  # noqa: E731
    within = statistics.fmean([dist(p, ma) for p in a] + [dist(p, mb) for p in b])
    between = math.hypot(ma[0] - mb[0], ma[1] - mb[1])
    correct = sum(dist(p, ma) < dist(p, mb) for p in a) + sum(dist(p, mb) < dist(p, ma) for p in b)
    return {"truth": truth, "frames_with_two": len(a),
            "mean_a": [round(v, 1) for v in ma], "mean_b": [round(v, 1) for v in mb],
            "within_person_spread": round(within, 2), "between_person_distance": round(between, 2),
            "separation_ratio": round(between / within, 2) if within > 0 else None,
            "nearest_mean_accuracy": round(correct / (2 * len(a)), 3)}


def e6_stats(truth: dict, fused: Sequence[Tuple[float, float]], cmds: Sequence[Tuple[float, float]],
             set_point: float = 0.5, lost_after: float = 0.5) -> dict:
    """How well the robot followed one person: from /target_fused_prob (time, LiDAR gap) and
    /cmd_vel (time, linear.x).

    "Tracked" means a target message within the last `lost_after` seconds, checked every 0.1 s from
    the first to the last message of the recording.
    """
    if not fused:
        return {"truth": truth, "target_messages": 0}
    times = [t for t, _ in fused]
    gaps = [g for _, g in fused if math.isfinite(g)]
    t0, t1 = times[0], max(times[-1], cmds[-1][0] if cmds else times[-1])
    steps = max(1, int((t1 - t0) / 0.1))
    tracked = 0
    for k in range(steps + 1):
        t = t0 + 0.1 * k
        i = bisect_right(times, t)
        tracked += i > 0 and t - times[i - 1] <= lost_after
    longest = max((b - a for a, b in zip(times, times[1:])), default=0.0)
    return {"truth": truth, "duration_s": round(t1 - t0, 1), "target_messages": len(fused),
            "tracked_share": round(tracked / (steps + 1), 3), "longest_dropout_s": round(longest, 2),
            "median_gap_m": round(statistics.median(gaps), 2) if gaps else None,
            "p95_gap_m": round(percentile(gaps, 0.95), 2) if gaps else None,
            "min_gap_m": round(min(gaps), 2) if gaps else None,
            "median_gap_error_m": round(statistics.median(abs(g - set_point) for g in gaps), 2) if gaps else None,
            "max_forward_cmd": round(max((v for _, v in cmds), default=0.0), 2)}


def e4_overlap_shift(base: dict, overlap: dict) -> Optional[dict]:
    """How far each person's mean chroma moves when B is partly behind A (box-crop contamination)."""
    if "mean_a" not in base or "mean_a" not in overlap:
        return None
    return {"shift_a": round(math.hypot(*(o - b for o, b in zip(overlap["mean_a"], base["mean_a"]))), 2),
            "shift_b": round(math.hypot(*(o - b for o, b in zip(overlap["mean_b"], base["mean_b"]))), 2)}


# ------------------------------------------------------------------ bags (needs ROS 2)


def read_bag(bag_dir: Path, topics: Iterable[str]) -> Dict[str, list]:
    """{topic: [(receive time s, message)]} for the given topics, any storage rosbag2 supports."""
    import rosbag2_py  # noqa: PLC0415  (ROS 2 only)
    from rclpy.serialization import deserialize_message  # noqa: PLC0415
    from rosidl_runtime_py.utilities import get_message  # noqa: PLC0415
    import yaml  # noqa: PLC0415

    meta = yaml.safe_load((bag_dir / "metadata.yaml").read_text())
    storage = meta["rosbag2_bagfile_information"]["storage_identifier"]
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=str(bag_dir), storage_id=storage),
                rosbag2_py.ConverterOptions("", ""))
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    wanted = [t for t in topics if t in types]
    out = {t: [] for t in wanted}
    while reader.has_next():
        topic, raw, t_ns = reader.read_next()
        if topic in out:
            out[topic].append((t_ns * 1e-9, deserialize_message(raw, get_message(types[topic]))))
    return out


def find_recordings(roots: Sequence[Path], label: Optional[str]) -> List[Tuple[str, Path]]:
    found = []
    for root in roots:
        for manifest in sorted(root.rglob("recording.json")):
            found.append((json.loads(manifest.read_text())["scenario"], manifest.parent / "recording"))
        if not found and (root / "metadata.yaml").exists():
            found.append((label or root.name, root))
    return found


def analyse(recordings: Sequence[Tuple[str, Path]]) -> dict:
    report = {"e1": [], "e2": [], "e3": [], "e4": [], "e4_overlap_shift": [], "e6": []}
    e4_by_key = {}
    for label, bag in recordings:
        truth = parse_label(label)
        msgs = read_bag(bag, ["/yolo_frame", "/target_centroid_sector", "/scan", "/cmd_vel", "/target_fused_prob"])
        frames = [(t, parse_frame(m.data)) for t, m in msgs.get("/yolo_frame", [])]
        width = frames[0][1]["width"] if frames else 640
        if frames:
            report["e2"].append({"label": label, **e2_latency(frames, [t for t, _ in msgs.get("/cmd_vel", [])])})
        if truth["exp"] == "e1":
            dets = [(t, m.data[0]) for t, m in msgs.get("/target_centroid_sector", [])]
            scans = [(t, scan_points(m.angle_min, m.angle_increment, list(m.ranges))) for t, m in msgs.get("/scan", [])]
            report["e1"].append({"label": label, **e1_stats(truth, dets, scans, width)})
        elif truth["exp"] == "e6":
            fused = [(t, float(m.data[2])) for t, m in msgs.get("/target_fused_prob", []) if len(m.data) >= 3]
            cmds = [(t, m.linear.x) for t, m in msgs.get("/cmd_vel", [])]
            report["e6"].append({"label": label, **e6_stats(truth, fused, cmds)})
        elif truth["exp"] == "e3":
            report["e3"].append({"label": label, **e3_stats(truth, frames)})
        elif truth["exp"] == "e4":
            r = {"label": label, **e4_stats(truth, frames)}
            report["e4"].append(r)
            e4_by_key[(truth["overlap"], truth["clothes"], truth["light"])] = r
    for (overlap, clothes, light), r in e4_by_key.items():
        base = e4_by_key.get((False, clothes, light))
        if overlap and base:
            report["e4_overlap_shift"].append({"clothes": clothes, "light": light, **(e4_overlap_shift(base, r) or {})})
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roots", nargs="+", type=Path)
    ap.add_argument("--label", help="scenario label for a bare bag folder")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    recordings = find_recordings(args.roots, args.label)
    if not recordings:
        print("no recordings found", file=sys.stderr)
        return 1
    report = analyse(recordings)
    text = json.dumps(report, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
