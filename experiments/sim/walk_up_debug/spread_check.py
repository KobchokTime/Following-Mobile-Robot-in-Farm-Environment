# Run from the repo root: PYTHONPATH=. python3 experiments/sim/walk_up_debug/spread_check.py
"""Offline: old rule (returns far from the box) vs spread rule (returns near the prediction wider than one person)."""
import math, sys
sys.path.insert(0, 'tests')
from test_target_gate import _load
from sim.twin.scenarios import build
from sim.twin.world import Realism
m = _load()

def spread(points, pb, pr, radius, max_width=1.5):
    px, py = pr * math.cos(pb), pr * math.sin(pb)
    near = []
    pts = sorted(points); start = 0
    for i in range(1, len(pts) + 1):
        if i < len(pts) and abs(pts[i][1] - pts[i-1][1]) <= 0.15 and pts[i][0] - pts[i-1][0] <= math.radians(3.0):
            continue
        c = pts[start:i]; start = i
        (b0, r0), (b1, r1) = c[0], c[-1]
        if math.hypot(r1*math.cos(b1)-r0*math.cos(b0), r1*math.sin(b1)-r0*math.sin(b0)) > max_width: continue
        for b, r in c:
            x, y = r*math.cos(b), r*math.sin(b)
            if math.hypot(x-px, y-py) <= radius: near.append((x, y))
    return max((math.hypot(a[0]-b[0], a[1]-b[1]) for a in near for b in near), default=0.0)

for name, who, t_end in (('side_step', 'target', 9.0), ('walk_up_same', 'stranger', 11.0)):
    for seed in (3, 4):
        w = build(name, seed=seed, realism=Realism())
        last, old, sp = None, [], []
        while w.t < t_end:
            for _ in range(5): w.step(0.02)
            s = w.sensors
            pts = [((-math.pi + i*2*math.pi/s.lidar_rays + 2*math.pi) % (2*math.pi) - math.pi, r) for i, r in enumerate(w.scan()) if math.isfinite(r)]
            for d in w.detections():
                b = m.camera_bearing_rad(d.cx, s.image_width, s.camera_hfov_deg)
                rng = m.box_range(pts, b)
                if rng is None or last is None:
                    if d.person == 'target' and rng is not None: last = (b, rng)
                    continue
                if d.person == who or (who == 'stranger' and d.person == 'target'):
                    bx, by = rng*math.cos(b), rng*math.sin(b); px, py = last[1]*math.cos(last[0]), last[1]*math.sin(last[0])
                    near_box = math.hypot(bx-px, by-py) <= 0.5
                    if near_box and m.scan_crowded(pts, b, rng, last[0], last[1], 0.5): old.append(round(w.t, 1))
                    if near_box and spread(pts, last[0], last[1], 0.5) >= 0.55: sp.append(round(w.t, 1))
                if d.person == 'target': last = (b, rng)
        print(name, seed, 'old rule fired', sorted(set(old))[:12], '| spread rule fired', sorted(set(sp))[:12])
