#!/usr/bin/env python3
"""Independent pose reference for a bag replay, from scan geometry alone (no ROS needed).

Reads /scan straight from a rosbag2 sqlite file (read-only) and estimates the robot's pose
change between the first scan and the stationary end of the bag in two ways:
  1. a direct brute-force alignment of the last scans onto the first scan;
  2. chained 0.5 s scan-to-scan alignments over the moving part.
Then compares the final SLAM pose from slam_pose_logger.py CSVs (and the bag's wheel /odom)
against it. Uses the 2026-11-15 mount: bearing = -raw + 6.2 deg.

    py -3 scan_pose_reference.py BAG.db3 --moving-s 20 --still-after-s 60 r1.csv r2.csv
Needs numpy.
"""

import argparse
import csv
import math
import sqlite3
import struct

import numpy as np

OFFSET = math.radians(6.2)


def scan_points(blob):
    b = blob[4:]
    o = 8
    n = struct.unpack_from("<I", b, o)[0]
    o = (o + 4 + n + 3) & ~3
    amin, _amax, inc, _ti, _st, rmin, rmax = struct.unpack_from("<7f", b, o)
    o += 28
    cnt = struct.unpack_from("<I", b, o)[0]
    r = np.frombuffer(b, dtype="<f4", count=cnt, offset=o + 4)
    a = amin + inc * np.arange(cnt)
    ok = np.isfinite(r) & (r >= max(rmin, 0.1)) & (r <= rmax)
    bearing = -a[ok] + OFFSET
    return np.c_[r[ok] * np.cos(bearing), r[ok] * np.sin(bearing)]


def odom_pose(blob):
    b = blob[4:]
    o = 8
    for _ in range(2):
        n = struct.unpack_from("<I", b, o)[0]
        o = (o + 4 + n + 3) & ~3
    o = (o + 7) & ~7
    x, y, _z, qx, qy, qz, qw = struct.unpack_from("<7d", b, o)
    return x, y, math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


class Grid:
    def __init__(self, pts, res=0.03, ext=8.0):
        self.res, self.ext, self.n = res, ext, int(2 * ext / res)
        g = np.zeros((self.n, self.n), bool)
        ij = self._cells(pts)
        g[ij[:, 1], ij[:, 0]] = True
        h = g.copy()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                h |= np.roll(np.roll(g, dx, 1), dy, 0)
        self.g = h

    def _cells(self, pts):
        ij = ((pts + self.ext) / self.res).astype(int)
        return ij[(ij >= 0).all(1) & (ij < self.n).all(1)]

    def score(self, pts, yaw, tx, ty):
        c, s = math.cos(yaw), math.sin(yaw)
        q = pts @ np.array([[c, s], [-s, c]]) + [tx, ty]
        ij = self._cells(q)
        return self.g[ij[:, 1], ij[:, 0]].sum() / len(pts)


def align(ref, mov, yaws_deg, txs, tys):
    grid = Grid(ref)
    return max((grid.score(mov, math.radians(y), tx, ty), y, tx, ty) for y in yaws_deg for tx in txs for ty in tys)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bag")
    ap.add_argument("csv", nargs="*")
    ap.add_argument("--moving-s", type=float, default=20.0)
    ap.add_argument("--still-after-s", type=float, default=60.0)
    args = ap.parse_args()
    con = sqlite3.connect(f"file:{args.bag}?mode=ro", uri=True)
    tid = {n: i for i, n in con.execute("select id,name from topics")}
    scans = con.execute("select timestamp,data from messages where topic_id=? order by timestamp",
                        (tid["/scan"],)).fetchall()
    t0 = scans[0][0]
    first = scan_points(scans[0][1])
    last = np.vstack([scan_points(d) for t, d in scans if (t - t0) / 1e9 > args.still_after_s][:10])

    sc, y, tx, ty = align(first, last, range(-360, 1, 2), np.arange(-1.5, 1.51, 0.05), np.arange(-1.5, 1.51, 0.05))
    sc, y, tx, ty = align(first, last, np.arange(y - 3, y + 3.01, 0.5),
                          np.arange(tx - 0.06, tx + 0.061, 0.01), np.arange(ty - 0.06, ty + 0.061, 0.01))
    direct = (tx, ty, math.radians(y))
    print(f"direct alignment: overlap {sc:.0%}, pose ({tx:.2f}, {ty:.2f}, {y:.1f} deg)")

    times = [(t - t0) / 1e9 for t, _ in scans]
    idx = [min(range(len(times)), key=lambda i: abs(times[i] - k * 0.5))
           for k in range(int(args.moving_s / 0.5) + 1)]
    pos, hd = np.zeros(2), 0.0
    for a, b in zip(idx, idx[1:]):
        _, dy, dx_, dy_ = align(scan_points(scans[a][1]), scan_points(scans[b][1]),
                                np.arange(-40, 40.1, 1), np.arange(-0.25, 0.26, 0.03), np.arange(-0.25, 0.26, 0.03))
        c, s = math.cos(hd), math.sin(hd)
        pos += [c * dx_ - s * dy_, s * dx_ + c * dy_]
        hd += math.radians(dy)
    print(f"chained 0.5 s alignment: pose ({pos[0]:.2f}, {pos[1]:.2f}, {math.degrees(hd):.1f} deg)")
    ref = ((direct[0] + pos[0]) / 2, (direct[1] + pos[1]) / 2, (direct[2] + hd) / 2)
    print(f"reference (mean): ({ref[0]:.2f}, {ref[1]:.2f}, {math.degrees(ref[2]):.1f} deg)")

    odom = [odom_pose(d) for _, d in con.execute(
        "select timestamp,data from messages where topic_id=? order by timestamp", (tid["/odom"],))]
    (x0, y0, h0), (x1, y1, _) = odom[0], odom[-1]
    c, s = math.cos(-h0), math.sin(-h0)
    turn = sum(wrap(b[2] - a[2]) for a, b in zip(odom, odom[1:]))
    ox, oy = c * (x1 - x0) - s * (y1 - y0), s * (x1 - x0) + c * (y1 - y0)
    print(f"wheel /odom (commanded): ({ox:.2f}, {oy:.2f}, {math.degrees(turn):.1f} deg) | "
          f"pos err {math.dist((ox, oy), ref[:2]):.2f} m, yaw err {math.degrees(turn - ref[2]):.1f} deg")
    for path in args.csv:
        rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(open(path))]
        turn = sum(wrap(b["slam_yaw"] - a["slam_yaw"]) for a, b in zip(rows, rows[1:]))
        f = rows[-1]
        print(f"SLAM {path}: ({f['slam_x']:.2f}, {f['slam_y']:.2f}, {math.degrees(turn):.1f} deg) | "
              f"pos err {math.dist((f['slam_x'], f['slam_y']), ref[:2]):.2f} m, "
              f"yaw err {math.degrees(turn - ref[2]):.1f} deg")


if __name__ == "__main__":
    main()
