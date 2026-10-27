"""Reproduce T14 review checks without ROS or hardware (synthetic observations).

Run from the repository root:
  python experiments/reviews/t14_gate_review.py --out experiments/reviews/2026-10-28_t14_review.json

The Fisher calculation checks the reported totals, not the missing trial records.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
from test_sector_association import _load_sync_module, SectorAssociationTest, sectorizer_mids

M = _load_sync_module()
D = math.radians
HIST = [0.0] * 48
HIST[34] = 1.0
CHROMA = (139, 125)


def visible_scan(*groups):
    beams = {}
    for points in groups:
        for b, r in points:
            beams[b] = min(r, beams.get(b, math.inf))
    return sorted(beams.items())


def sector_median(points, bearing):
    """Use the real sectorizer's median, not the minimum used in the existing unit test."""
    i = M.nearest_sector(bearing, sectorizer_mids())
    low, high = D(-35 + i * 70 / 9), D(-35 + (i + 1) * 70 / 9)
    values = [r for b, r in points if low <= b < high]
    return statistics.median(values) if values else math.inf


def initial_gate():
    g = M.TargetGate()
    for i in range(5):
        assert g.accept(0.1 * i, D(2), 0.8 + 0.05 * i, CHROMA, HIST)
    return g


def borrowed_range(points):
    g = initial_gate()
    t, b = 1.6, D(18)
    old, own = sector_median(points, b), M.box_range(points, b)
    separation = math.hypot(own * math.cos(b) - g.range * math.cos(g.bearing),
                            own * math.sin(b) - g.range * math.sin(g.bearing))
    before = copy.deepcopy(g.__dict__)
    on = g.accept(t, b, own, CHROMA, HIST)
    off_gate = initial_gate()
    off = off_gate.accept(t, b, old, CHROMA, HIST)
    return dict(old_sector_median_m=old, box_range_m=own, unseen_s=t - before["t"],
                reach_m=min(g.reacquire_dist_max, g.reacquire_dist + g.reacquire_speed * (t-before["t"])),
                separation_m=separation, old_accepted=off, new_accepted=on,
                rejected_track_unchanged=g.__dict__ == before)


def leg_cases():
    person = SectorAssociationTest._person
    results = []
    for half_stance in (0.10, 0.15):
        for distance in (0.5, 0.75, 1.0, 1.5, 2.0, 3.0):
            legs = visible_scan(person(distance, half_stance, radius=0.06),
                                person(distance, -half_stance, radius=0.06))
            results.append(dict(distance_m=distance, leg_centre_separation_m=2*half_stance,
                                leg_radius_m=0.06, box_range_m=M.box_range(legs, 0.0)))
    target = visible_scan(person(1.0, 0.15, radius=0.06), person(1.0, -0.15, radius=0.06))
    neighbour = person(0.8*math.cos(D(6)), 0.8*math.sin(D(6)), radius=0.04)
    ambiguity = dict(target_only_m=M.box_range(target, 0.0),
                     with_neighbour_leg_m=M.box_range(visible_scan(target, neighbour), 0.0),
                     neighbour_centre_bearing_deg=6, neighbour_centre_range_m=0.8)
    return results, ambiguity


def frame_cases():
    outputs = []
    for start, increment in ((-210, 30), (-150, -30)):
        scan = SimpleNamespace(angle_min=D(start), angle_increment=D(increment),
                               ranges=[1.0]*3, range_min=0.05, range_max=12.0)
        node = SimpleNamespace(lidar_offset=math.pi, now_sec=lambda: 10.0)
        M.SyncFusionNode.cb_scan(node, scan)
        outputs.append(dict(increment_deg=increment,
                            robot_bearings_deg=[round(math.degrees(b), 8) for b, _ in node.scan_points]))
    return dict(scan_cases=outputs, camera_roundtrip_deg={str(b):math.degrees(
        M.camera_bearing_rad(M.bearing_to_cx(D(b), 640, 70), 640, 70)) for b in (-30, 0, 30)})


def skip_cases():
    results = []
    for name, enabled, scan_time in (("fresh_no_cluster", True, 10.0),
                                     ("disabled_sector_fallback", False, 10.0),
                                     ("stale_scan_sector_fallback", True, 9.6)):
        calls, published = [], []
        node = object.__new__(M.SyncFusionNode)
        node.buf_lidar = [(10.0, [0.8]*9)]
        node.lidar_angles = sectorizer_mids()
        node.max_dt, node.image_width, node.camera_hfov_deg = 0.1, 640, 70.0
        node.box_range_from_scan, node.scan_time, node.scan_max_age = enabled, scan_time, 0.3
        node.scan_points, node.use_gate = [], True
        node.gate = SimpleNamespace(accept=lambda *args: calls.append(args) or False)
        node.last_target, node.path_half_width, node.path_min_gap = (320, 240, 4, 2.0), 0.7, 0.2
        node.path_block, node.path_margin = None, 0.4
        node.get_logger = lambda: SimpleNamespace(debug=lambda *args: None)
        node.publish_synced = lambda *args: published.append(args)
        node.try_sync_from_yolo(10.0, 320, 240, 4, CHROMA, HIST)
        results.append(dict(case=name, gate_calls=len(calls), publications=len(published),
                            give_way_range_m=published[0][2] if published else None))
    return results


def fisher_two_sided(a=15, b=13, c=18, d=10):
    total, successes, sample = a+b+c+d, a+c, a+b
    lo, hi = max(0, sample-(total-successes)), min(sample, successes)
    probability = lambda k: math.comb(successes, k)*math.comb(total-successes, sample-k)/math.comb(total, sample)
    observed = probability(a)
    return sum(probability(k) for k in range(lo, hi+1) if probability(k) <= observed+1e-12)


def sidestep_case():
    g = initial_gate()
    g.t, g.bearing, g.range = 10.0, D(6.5), 0.66
    g.bearing_rate, g.range_rate = D(1)/0.3, 0.0
    rows = []
    for rng in (0.66, 0.72):
        trial = copy.deepcopy(g)
        cost = trial.cost(10.3, D(27.5), rng, CHROMA, HIST)
        rows.append(dict(measured_range_m=rng, total_cost=cost,
                         accepted=trial.accept(10.3, D(27.5), rng, CHROMA, HIST)))
    return dict(predicted_bearing_deg=math.degrees(g._predict(10.3)[0]),
                last_bearing_deg=6.5, lidar_edge_threshold_deg=27,
                lateral_step_angle_deg=math.degrees(math.atan2(0.25, 0.7)), costs=rows,
                fisher_p_if_reported_totals_correct=fisher_two_sided(),
                reported_pass_rate_difference_pp=100*(15/28-18/28))


def evidence_inventory():
    path = ROOT / "experiments/sim/2026-10-27_box_range.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    selected = [r for r in rows if r["code"] == "d23e7b2"]
    groups = {}
    for r in selected:
        key = r["variant"] + "/" + r["scenario"]
        v = groups.setdefault(key, dict(n=0, passed=0, contacts=0))
        v["n"] += 1
        v["passed"] += bool(r["pass_"])
        v["contacts"] += bool(r["contact"])
    side = [r for r in selected if r["scenario"] == "side_step"]
    return dict(total_rows=len(rows), d23e7b2_rows=len(selected), groups=groups,
                side_step_seed_coverage={variant:sorted(r["seed"] for r in side if r["variant"]==variant)
                                         for variant in ("box_range on", "box_range off")},
                missing_new_trials=sum(1 for variant in ("box_range on", "box_range off")
                                       for seed in range(8, 28)
                                       if not any(r["variant"]==variant and r["seed"]==seed for r in side)),
                missing_off_early_seeds=[seed for seed in range(3)
                                        if not any(r["variant"]=="box_range off" and r["seed"]==seed for r in side)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    path = ROOT / "ros2_yolo_ws/scripts/Image/sync_fusion_node.py"
    code = path.read_bytes().replace(b"\r\n", b"\n")
    reference = subprocess.check_output(["git", "show", "d23e7b2:ros2_yolo_ws/scripts/Image/sync_fusion_node.py"], cwd=ROOT)
    assert code == reference
    near = [(D(i/2), 0.8) for i in range(-34, 35)]
    far = [(D(i/2), 7.43) for i in range(34, 40)]
    flat = borrowed_range(visible_scan(near, far))
    assert flat["old_accepted"] and not flat["new_accepted"] and flat["rejected_track_unchanged"]
    person = SectorAssociationTest._person
    circles = borrowed_range(visible_scan(person(0.8, 0), person(7.43*math.cos(D(18)), 7.43*math.sin(D(18)))))
    legs, ambiguity = leg_cases()
    result = dict(code_revision="d23e7b2", sync_fusion_sha256=hashlib.sha256(code).hexdigest(),
                  observation_type="synthetic gate-level; not a ROS closed-loop or hardware run",
                  borrowed_flat_returns=flat, borrowed_circle_returns=circles,
                  leg_cases=legs, neighbouring_leg_ambiguity=ambiguity, bearing_frame=frame_cases(),
                  skip_vs_fallback=skip_cases(), side_step=sidestep_case(), evidence=evidence_inventory())
    encoded = json.dumps(result, indent=2, allow_nan=False)+"\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded, encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
