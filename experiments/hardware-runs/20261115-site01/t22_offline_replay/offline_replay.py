#!/usr/bin/env python3
"""Offline replay of a rosbag2 through the real robot nodes, without ROS.

The four node scripts (lidar_sectorizer, sync_fusion, fusion_prob, follow_stop) are loaded with stub
rclpy / message modules. One simulated clock is shared by all nodes; it is set to each bag message's
receive time, and node timers fire at their periods between messages. Publishing is delivered
synchronously to subscribers. Inputs are the same as sim/replay/replay_bag.py: /scan and the YOLO
centroid topics. The camera reference for the e6_check rule is /yolo_frame from the bag.

    python offline_replay.py BAG --code SCRIPTS_DIR --preset e6 --out result.json
"""

import argparse
import importlib.util
import json
import math
import sys
import types
from collections import defaultdict
from pathlib import Path

from rosbags.rosbag2 import Reader
from rosbags.typesys import Stores, get_typestore

# ---------------------------------------------------------------- stubs
CLOCK = {"ns": 0}


class Time:
    def __init__(self, ns):
        self.nanoseconds = int(ns)

    def __sub__(self, other):
        return Time(self.nanoseconds - other.nanoseconds)


class Clock:
    def now(self):
        return Time(CLOCK["ns"])


class Logger:
    def __init__(self, sink):
        self.sink = sink

    def _log(self, *a, **k):
        self.sink.append((CLOCK["ns"], " ".join(str(x) for x in a)))

    info = warn = warning = error = debug = fatal = _log


class Bus:
    def __init__(self):
        self.subs = defaultdict(list)
        self.out = defaultdict(list)
        self.timers = []

    def deliver(self, topic, msg):
        self.out[topic].append((CLOCK["ns"], snapshot(msg)))
        for cb in list(self.subs[topic]):
            cb(msg)


BUS = Bus()
OVERRIDES = {}
CURRENT = {"node": None}
META = {}
NODES_LIVE = {}


def snapshot(msg):
    if hasattr(msg, "linear"):
        return (float(msg.linear.x), float(msg.angular.z))
    if hasattr(msg, "data"):
        return [float(x) for x in msg.data]
    return None


class Publisher:
    def __init__(self, topic):
        self.topic = topic

    def publish(self, msg):
        BUS.deliver(self.topic, msg)


class FakeNode:
    def __init__(self, name, *a, **k):
        self._name = name
        self._params = {}
        self._logs = []
        self._over = OVERRIDES.get(CURRENT["node"], {})

    def declare_parameter(self, name, default=None, *a, **k):
        v = self._over.get(name, default)
        if isinstance(default, bool) and isinstance(v, str):
            v = v.lower() in ("true", "1", "yes")
        elif isinstance(default, float) and not isinstance(v, bool):
            v = float(v)
        elif isinstance(default, int) and not isinstance(default, bool) and not isinstance(v, bool):
            v = int(v)
        self._params[name] = v
        return types.SimpleNamespace(value=v)

    def get_parameter(self, name):
        return types.SimpleNamespace(value=self._params[name])

    def has_parameter(self, name):
        return name in self._params

    def create_subscription(self, _type, topic, cb, *a, **k):
        BUS.subs[topic].append(cb)
        return object()

    def create_publisher(self, _type, topic, *a, **k):
        return Publisher(topic)

    def create_timer(self, period, cb, *a, **k):
        BUS.timers.append([int(period * 1e9), None, cb])
        return object()

    def get_logger(self):
        return Logger(self._logs)

    def get_clock(self):
        return Clock()

    def get_name(self):
        return self._name


class Vec:
    def __init__(self):
        self.x = self.y = self.z = 0.0


class Twist:
    def __init__(self):
        self.linear = Vec()
        self.angular = Vec()


class Arr:
    def __init__(self, data=None):
        self.data = list(data or [])


def stub_modules():
    def mod(name, **attrs):
        m = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(m, k, v)
        return m

    ns = types.SimpleNamespace
    qos = mod("rclpy.qos", QoSProfile=lambda *a, **k: None, qos_profile_sensor_data=None,
              QoSReliabilityPolicy=ns(BEST_EFFORT=1, RELIABLE=2), QoSHistoryPolicy=ns(KEEP_LAST=1, KEEP_ALL=2),
              QoSDurabilityPolicy=ns(VOLATILE=1, TRANSIENT_LOCAL=2))
    node = mod("rclpy.node", Node=FakeNode)
    rclpy = mod("rclpy", node=node, qos=qos, init=lambda *a, **k: None, spin=lambda *a, **k: None,
                shutdown=lambda *a, **k: None, ok=lambda: True)
    std = mod("std_msgs.msg", Float32MultiArray=Arr, Int32MultiArray=Arr)
    sen = mod("sensor_msgs.msg", LaserScan=object)
    geo = mod("geometry_msgs.msg", Twist=Twist)
    return {"rclpy": rclpy, "rclpy.node": node, "rclpy.qos": qos,
            "std_msgs": mod("std_msgs", msg=std), "std_msgs.msg": std,
            "sensor_msgs": mod("sensor_msgs", msg=sen), "sensor_msgs.msg": sen,
            "geometry_msgs": mod("geometry_msgs", msg=geo), "geometry_msgs.msg": geo}


def load(path, modname):
    sys.modules.update(stub_modules())
    spec = importlib.util.spec_from_file_location(modname, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------------------------------------------------------- run config (start_follow.sh + launch)
LIDAR = {"offset": 6.2, "sign": -1.0}


def presets(name):
    o, s = LIDAR["offset"], LIDAR["sign"]
    fs = {"target_distance": 0.5, "latency_s": 0.2, "bridge_accel_mps2": 1.0, "steer_mode": "sector",
          "lidar_angle_offset_deg": o, "lidar_angle_sign": s, "obstacle_stop": True, "avoid_trail": False,
          "max_decel": 0.8}
    if name == "e6":
        fs.update(target_distance=1.0, front_band_radius=2, wide_front_radius=2)
    elif name != "first":
        raise SystemExit(f"unknown preset {name}")
    return {
        "lidar_sectorizer": {"angle_offset_deg": o, "angle_sign": s},
        "sync_fusion": {"obstacle_stop": True, "lidar_angle_offset_deg": o, "lidar_angle_sign": s},
        "fusion_prob": {},
        "follow_stop": fs,
    }


NODES = [  # (launch name, script, class)
    ("lidar_sectorizer", "Lidar/lidar_sectorizer_node.py", "LidarSectorizer"),
    ("sync_fusion", "Image/sync_fusion_node.py", "SyncFusionNode"),
    ("fusion_prob", "Image/fusion_prob_node.py", "FusionProbNode"),
    ("follow_stop", "MAIN/Control/follow_stop_node.py", "FollowStopNode"),
]
INPUTS = ["/scan", "/target_centroid_sector", "/target_centroid"]
REF = ["/yolo_frame", "/synced_target", "/cmd_vel"]


# ---------------------------------------------------------------- e6_check rule (same constants)
W, HFOV, MIN_RANGE, TURN_EPS, SIDE_DEG = 640, 70.0, 0.9, 0.05, 7.8


def bearing_deg(cx):
    f = (W / 2) / math.tan(math.radians(HFOV / 2))
    return math.degrees(math.atan2(W / 2 - cx, f))


def e6_rule(cmds, synced, boxes):
    wrong = []
    for s, vx, wz in cmds:
        if abs(wz) <= TURN_EPS:
            continue
        near = [x for x in synced if abs(x[0] - s) <= 0.3]
        seen = [x for x in boxes if abs(x[0] - s) <= 0.3]
        if not near or not seen:
            continue
        rng = min(near, key=lambda x: abs(x[0] - s))[2]
        cx = min(seen, key=lambda x: abs(x[0] - s))[1]
        b = bearing_deg(cx)
        if rng >= MIN_RANGE and abs(b) > SIDE_DEG and (b > 0) != (wz > 0):
            wrong.append({"t": round(s, 2), "bearing": round(b, 1), "range": round(rng, 2),
                          "vx": round(vx, 3), "wz": round(wz, 3)})
    return wrong


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bag", type=Path)
    ap.add_argument("--code", type=Path, required=True, help="ros2_yolo_ws/scripts of the code under test")
    ap.add_argument("--preset", default="e6", choices=["e6", "first"])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--yolo-delay-ms", type=float, default=0.0)
    ap.add_argument("--timer-phase-ms", type=float, default=0.0)
    ap.add_argument("--trace", type=Path, help="CSV of per-cmd_vel rows (t, vx, wz, synced cx/range, box bearing)")
    args = ap.parse_args()

    OVERRIDES.update(presets(args.preset))
    nodes = {}
    for name, script, cls in NODES:
        m = load(args.code / script, f"replay_{name}")
        CURRENT["node"] = name
        nodes[name] = getattr(m, cls)()
        unused = set(OVERRIDES[name]) - set(nodes[name]._params)
        if unused:
            raise SystemExit(f"{name}: parameters not declared by this code: {sorted(unused)}")

    ts = get_typestore(Stores.ROS2_HUMBLE)
    t0 = None
    ref = defaultdict(list)
    stats = {"delivered": 0}
    events = []
    with Reader(args.bag) as reader:
        conns = [c for c in reader.connections if c.topic in INPUTS + REF]
        for conn, t_ns, raw in reader.messages(connections=conns):
            if conn.topic in REF and t0 is None:
                t0 = t_ns
            msg = ts.deserialize_cdr(raw, conn.msgtype)
            if conn.topic in REF:
                ref[conn.topic].append((t_ns, msg))
                continue
            if conn.topic == "/scan":
                msg.ranges = [float(r) for r in msg.ranges]
            else:
                msg.data = [int(x) for x in msg.data]
                t_ns += int(args.yolo_delay_ms * 1e6)
            events.append((t_ns, len(events), conn.topic, msg))
    events.sort(key=lambda e: (e[0], e[1]))
    META["t0"] = t0
    NODES_LIVE.update(nodes)
    for tm in BUS.timers:
        tm[1] = events[0][0] + int(args.timer_phase_ms * 1e6) + tm[0]
    for t_ns, _, topic, msg in events:
        while BUS.timers:
            due = min(BUS.timers, key=lambda x: x[1])
            if due[1] > t_ns:
                break
            CLOCK["ns"] = due[1]
            due[2]()
            due[1] += due[0]
        CLOCK["ns"] = t_ns
        for cb in list(BUS.subs[topic]):
            cb(msg)
        stats["delivered"] += 1

    rel = lambda t: (t - t0) * 1e-9
    boxes = []
    for t, m in ref["/yolo_frame"]:
        d = list(m.data)
        if d[4] > 0:
            bx = max((d[5 + 7 * i: 12 + 7 * i] for i in range(d[4])), key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
            boxes.append((rel(t), (bx[0] + bx[2]) / 2.0))
    rec_synced = [(rel(t), float(m.data[0]), float(m.data[2])) for t, m in ref["/synced_target"]]
    rec_cmds = [(rel(t), float(m.linear.x), float(m.angular.z)) for t, m in ref["/cmd_vel"]]
    new_synced = [(rel(t), d[0], d[2]) for t, d in BUS.out["/synced_target"]]
    new_cmds = [(rel(t), d[0], d[1]) for t, d in BUS.out["/cmd_vel"]]

    def summ(cmds, synced):
        turns = [c for c in cmds if abs(c[2]) > TURN_EPS]
        return {"cmd_vel": len(cmds), "synced": len(synced),
                "max_abs_wz": round(max((abs(c[2]) for c in cmds), default=0.0), 3),
                "max_vx": round(max((c[1] for c in cmds), default=0.0), 3),
                "min_vx": round(min((c[1] for c in cmds), default=0.0), 3),
                "turn_msgs": len(turns),
                "wrong_direction": e6_rule(cmds, synced, boxes)}

    result = {"bag": args.bag.name, "code": str(args.code), "preset": args.preset, "yolo_delay_ms": args.yolo_delay_ms, "timer_phase_ms": args.timer_phase_ms,
              "params": OVERRIDES, "inputs_delivered": stats["delivered"], "yolo_frames_with_person": len(boxes),
              "recorded": summ(rec_cmds, rec_synced), "replayed": summ(new_cmds, new_synced),
              "sync_fusion_log_tail": [l for _, l in nodes["sync_fusion"]._logs[-15:]]}
    txt = json.dumps(result, indent=1, default=str)
    if args.out:
        args.out.write_text(txt, encoding="utf-8")
    if args.trace:
        with args.trace.open("w", encoding="utf-8") as f:
            f.write("src,t,vx,wz,synced_cx,synced_range,box_bearing\n")
            for src, cmds, syn in (("recorded", rec_cmds, rec_synced), ("replayed", new_cmds, new_synced)):
                for s, vx, wz in cmds:
                    ns = min(syn, key=lambda x: abs(x[0] - s), default=None)
                    nb = min(boxes, key=lambda x: abs(x[0] - s), default=None)
                    ok_s = ns is not None and abs(ns[0] - s) <= 0.3
                    ok_b = nb is not None and abs(nb[0] - s) <= 0.3
                    f.write(f"{src},{s:.3f},{vx:.3f},{wz:.3f},"
                            f"{ns[1] if ok_s else ''},{ns[2] if ok_s else ''},"
                            f"{round(bearing_deg(nb[1]), 1) if ok_b else ''}\n")
    print(json.dumps({k: result[k] for k in ("bag", "preset", "recorded", "replayed")}, indent=1))


def _takes_name(cls):
    import inspect
    try:
        return len(inspect.signature(cls.__init__).parameters) > 1
    except (TypeError, ValueError):
        return False


if __name__ == "__main__":
    main()
