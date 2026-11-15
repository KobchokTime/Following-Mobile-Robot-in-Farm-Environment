"""Offline: track the fused target through a bag, and count LiDAR clusters on the person per scan.

    python walk_shape.py RUN_DIR [--offset 6.2] [--sign -1]

Uses the pure-Python rosbags reader (no ROS needed). For each /scan, the person is taken at the latest
/synced_target bearing (from cx, HFOV 70) and range; returns within 0.4 m sideways of that bearing and
within 0.45 m of that range are split into clusters with sync_fusion's box_range rule (range jump > 0.15 m or
angular gap > 3 deg). One cluster = one target; two or more = split (e.g. two legs).
"""

import argparse
import math
import statistics
from pathlib import Path

from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore

HFOV = 70.0
LATERAL_M = 0.4  # returns within this sideways distance of the target bearing belong to the person


def cam_bearing(cx, w=640):
    f = (w / 2.0) / math.tan(math.radians(HFOV) / 2.0)
    return math.atan2(w / 2.0 - cx, f)


def split(points):
    pts = sorted(points)
    out, cur = [], []
    for p in pts:
        if cur and (abs(p[1] - cur[-1][1]) > 0.15 or p[0] - cur[-1][0] > math.radians(3.0)):
            out.append(cur)
            cur = []
        cur.append(p)
    if cur:
        out.append(cur)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--offset", type=float, default=6.2)
    ap.add_argument("--sign", type=float, default=-1.0)
    a = ap.parse_args()
    ts = get_typestore(Stores.ROS2_HUMBLE)
    off = math.radians(a.offset)
    target, rows, track = None, [], []
    with AnyReader([a.run_dir / "recording"], default_typestore=ts) as r:
        conns = [c for c in r.connections if c.topic in ("/scan", "/synced_target")]
        t0 = None
        for c, t, raw in r.messages(connections=conns):
            m = r.deserialize(raw, c.msgtype)
            t0 = t0 or t
            ts_ = (t - t0) * 1e-9
            if c.topic == "/synced_target":
                target = (ts_, cam_bearing(float(m.data[0])), float(m.data[2]))
                track.append((ts_, float(m.data[2]), math.degrees(target[1])))
                continue
            if target is None or ts_ - target[0] > 0.3:
                continue
            _, tb, tr = target
            pts = []
            for i, rr in enumerate(m.ranges):
                if math.isfinite(rr) and rr > 0:
                    b = (a.sign * (m.angle_min + i * m.angle_increment) + off + math.pi) % (2 * math.pi) - math.pi
                    if abs(rr * math.sin(b - tb)) <= LATERAL_M and abs(rr - tr) <= 0.45:
                        pts.append((b, float(rr)))
            cl = [c_ for c_ in split(pts) if len(c_) >= 2]
            widths = [2 * statistics.median(p[1] for p in c_) * math.sin((c_[-1][0] - c_[0][0]) / 2) for c_ in cl]
            rows.append((ts_, tr, len(cl), widths))

    print(f"synced_target msgs: {len(track)}")
    for k in range(0, len(track), max(1, len(track) // 15)):
        t, d, b = track[k]
        print(f"  t={t:5.1f}s  dist={d:5.2f} m  bearing={b:+5.1f} deg")
    print(f"scans with a fresh target: {len(rows)}")
    for lo, hi in ((0.0, 1.2), (1.2, 2.2), (2.2, 3.2), (3.2, 5.0)):
        sel = [x for x in rows if lo <= x[1] < hi]
        if not sel:
            continue
        one = sum(1 for x in sel if x[2] == 1)
        two = sum(1 for x in sel if x[2] >= 2)
        none = sum(1 for x in sel if x[2] == 0)
        w = [x[3][0] for x in sel if x[2] == 1]
        print(f"  range {lo:.1f}-{hi:.1f} m: scans={len(sel)}  one cluster={one}  split(2+)={two}  none={none}"
              + (f"  single-cluster width median={statistics.median(w):.2f} m" if w else ""))


if __name__ == "__main__":
    main()
