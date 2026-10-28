"""Offline T15 audit: committed records, gate geometry, constructor wiring and guard mutations.

Synthetic checks are not ROS/Docker closed-loop trials. Standard library only.
Usage: python experiments/reviews/t15_review.py --out <report.json>
"""
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
from test_target_gate import _load, TargetGateTest
from test_sector_association import SectorAssociationTest, sectorizer_mids

REL = 'ros2_yolo_ws/scripts/Image/sync_fusion_node.py'
SOURCE = (ROOT / REL).read_text(encoding='utf-8')
M = _load()
HIST = [0.0] * 48
HIST[34] = 1.0
CHROMA = (139, 125)


def execute_definitions(source, env, label):
    tree = ast.parse(source)
    tree.body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
    exec(compile(tree, label, 'exec'), env)


def fisher(a, b, c, d):
    n, k, draws = a+b+c+d, a+c, a+b
    weights = {x: math.comb(k, x)*math.comb(n-k, draws-x)
               for x in range(max(0, draws-(n-k)), min(draws, k)+1)}
    return sum(w for w in weights.values() if w <= weights[a])/sum(weights.values())


def inventory():
    path = ROOT / 'experiments/sim/2026-10-28_lateral_gate.json'
    rows = json.loads(path.read_text())
    assert len(rows) == 165
    assert len({(r['run'], r['scenario'], r['seed']) for r in rows}) == len(rows)
    groups = {}
    for r in rows:
        params = dict(x.split(':=', 1) for x in r['ros_params'])
        assert all(k in M.GATE_PARAMS for k in params)
        assert len(params) == len(r['ros_params'])
        assert float(params['lateral_sigma_m']) in (0.0, 0.15)
        # Necessary conditions only: the collector dropped final FOV and rounded two inputs.
        if r['pass_']:
            assert not r['contact'] and r['final_gap_m'] <= 1.5 and r['target_visible_share'] >= 0.9
        group = r['run'].rsplit('_s', 1)[0]
        groups.setdefault(group, []).append(r)
    expected = {'ss_on': 20, 'ss_off': 20, 'zz_on': 10, 'zz_off': 10,
                'reg_identity': 15, 'reg_solo': 30, 'col_shade_crossing': 10,
                'col_shade_side_by_side': 10, 'look_clean': 10, 'look_real': 10,
                'look_ruleoff_clean': 10, 'look_ruleoff_real': 10}
    assert {k: len(v) for k, v in groups.items()} == expected
    for k, rs in groups.items():
        scenarios = {r['scenario'] for r in rs}
        seeds = set(range(8, 28)) if k.startswith('ss_') else set(range(3)) if k.startswith('reg_') else set(range(10))
        assert {(r['scenario'], r['seed']) for r in rs} == {(s, i) for s in scenarios for i in seeds}
        for r in rs:
            p = dict(x.split(':=', 1) for x in r['ros_params'])
            assert float(p['lateral_sigma_m']) == (0.0 if k in ('ss_off', 'zz_off') else 0.15)
            assert r['realism'] == ('clean' not in k)
            if 'ruleoff' in k:
                assert p == {'lateral_sigma_m': '0.15', 'reacquire_dist_m': '100.0', 'reacquire_dist_max_m': '100.0'}
            else:
                assert set(p) == {'lateral_sigma_m'}
    totals = {k: dict(n=len(rs), passed=sum(r['pass_'] for r in rs), contacts=sum(r['contact'] for r in rs),
                      failures=[dict(scenario=r['scenario'], seed=r['seed']) for r in rs if not r['pass_']])
              for k, rs in groups.items()}
    comparisons = {}
    for k in ('ss', 'zz'):
        on = {r['seed']: r['pass_'] for r in groups[k+'_on']}
        off = {r['seed']: r['pass_'] for r in groups[k+'_off']}
        n, a, c = len(on), sum(on.values()), sum(off.values())
        improved = sum(on[s] and not off[s] for s in on)
        worsened = sum(off[s] and not on[s] for s in on)
        discordant = improved+worsened
        paired = min(1.0, 2*sum(math.comb(discordant, j) for j in range(min(improved, worsened)+1))/2**discordant)
        comparisons[k] = dict(fisher_two_sided=fisher(a, n-a, c, n-c),
                              paired_improved=improved, paired_worsened=worsened, paired_exact_p=paired)
    return dict(rows=len(rows), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), totals=totals,
                comparisons=comparisons, full_pass_recomputation_possible=False,
                missing=['target_in_camera_fov_end', 'unrounded final_gap_m and target_visible_share',
                         'runtime effective parameters', 'per-row code/image provenance', 'accepted detection identity'])


def gate(lateral, rng=0.7):
    g = M.TargetGate(lateral_sigma_m=lateral)
    for i in range(5):
        assert g.accept(i*0.1, 0.0, rng, CHROMA, HIST)
    return g


def geometry():
    widths = {}
    for lateral in (0.0, 0.075, 0.1, 0.15):
        g = gate(lateral)
        lo, hi = 0.0, 1.0
        for _ in range(65):
            y = (lo+hi)/2
            if g.cost(0.5, math.atan2(y, 0.7), math.hypot(y, 0.7), CHROMA, HIST) <= 9:
                lo = y
            else:
                hi = y
        widths[str(lateral)] = lo
    # Reproduce the changed 8-degree colour example, without changing its fixture.
    blue, grey = TargetGateTest._hist(8, 2), TargetGateTest._hist(0, 0, grey=1.0)
    colour = {}
    for lateral in (0.0, 0.1, 0.15):
        g = M.TargetGate(lateral_sigma_m=lateral)
        for t in (0.0, 0.1):
            g.accept(t, 0, 0.8, CHROMA, blue)
        colour[str(lateral)] = {str(b): g.cost(0.2, math.radians(b), 1.0, (131, 128), grey) for b in (8, 10)}
    floor = gate(0.15, 0.5)
    # Inspect finite cost at a hypothetical valid low prediction; cost's 0.3-m floor caps sigma.
    floor.range = 0.1
    bounded = floor.cost(0.5, math.radians(20), 0.1)
    sidestep = {}
    for lateral in (0.0, 0.075, 0.1, 0.15):
        g = M.TargetGate(lateral_sigma_m=lateral)
        for k in range(5):
            g.accept(0.1*k, math.radians(0.5+1.5*k), 0.66)
        c = g.cost(0.7, math.radians(27.5), 0.72)
        sidestep[str(lateral)] = dict(cost=c, accepted=g.accept(0.7, math.radians(27.5), 0.72))
    return dict(transition_range_m=0.15/math.radians(5), floor_max_sigma_deg=math.degrees(0.15/0.3),
                floor_finite_cost=bounded, steady_track_lateral_boundary_m=widths,
                differing_colour_cost=colour, synthetic_unit_sidestep=sidestep,
                note='angle*mean_range is a small-angle arc approximation, not exact Cartesian distance')


def two_people():
    # Twin-style circular people, centres 0.44 m apart, diameter 0.4 m: no overlap in space or angle.
    target, stranger = (1.0, 0.0), (1.0, 0.44)
    radius = 0.2
    b = math.atan2(stranger[1], stranger[0])
    bounds = {}
    for name, (x, y) in [('target', target), ('stranger', stranger)]:
        centre, half = math.atan2(y, x), math.asin(radius/math.hypot(x, y))
        bounds[name] = list(map(math.degrees, (centre-half, centre+half)))
    assert bounds['target'][1] < bounds['stranger'][0]
    assert bounds['stranger'][1] < 35.0  # both people fully in the camera FOV
    pts = SectorAssociationTest._person(*target) + SectorAssociationTest._person(*stranger)
    # Occlusion-correct ray union; use actual box_range, not supplied centre range.
    beams = {}
    for a, r in pts:
        beams[a] = min(r, beams.get(a, math.inf))
    scan = sorted(beams.items())
    rt, rs = M.box_range(scan, 0), M.box_range(scan, b)
    results = {}
    for lateral in (0.0, 0.1, 0.15):
        node = object.__new__(M.SyncFusionNode)
        node.gate = gate(lateral, rt)
        node.buf_lidar, node.lidar_angles = [(0.5, [rt]*9)], sectorizer_mids()
        node.max_dt, node.image_width, node.camera_hfov_deg = 0.1, 640, 70.0
        node.box_range_from_scan, node.scan_time, node.scan_max_age = True, 0.5, 0.3
        node.scan_points, node.use_gate = scan, True
        node.last_target, node.path_block = (320, 240, 4, rt), None
        node.path_half_width, node.path_min_gap = 0.7, 0.2
        node.path_hold, node.path_margin = 0.5, 0.4
        node.get_logger = lambda: SimpleNamespace(debug=lambda *a: None)
        node.sync_count, pubs = 0, []
        node.publish_synced = lambda *args: pubs.append(args)
        before = node.gate.cost(0.5, b, rs, CHROMA, HIST)
        # Correct target first, stranger second, as separate camera-box callbacks in the same frame.
        node.try_sync_from_yolo(0.5, 320, 240, 4, CHROMA, HIST)
        cx = M.bearing_to_cx(b, 640, 70.0)
        node.try_sync_from_yolo(0.501, cx, 240, 0, CHROMA, HIST)
        results[str(lateral)] = dict(stranger_cost_before_target_callback=before,
                                    published_bearings_deg=[math.degrees(M.camera_bearing_rad(p[0], 640, 70.0)) for p in pubs],
                                    last_target_is_stranger=node.last_target[0] == cx,
                                    learned_bearing_deg=math.degrees(node.gate.bearing))
    assert not results['0.0']['last_target_is_stranger']
    assert results['0.15']['last_target_is_stranger']
    return dict(synthetic=True, same_chroma_and_hist=True, centre_distance_m=0.44,
                angular_extents_deg=bounds, box_range_target_m=rt, box_range_stranger_m=rs,
                results=results, note='real production callbacks, fake ROS node, no wheels or closed loop')


def t13_reacquisition():
    results = {}
    for off in (False, True):
        kwargs = dict(reacquire_dist_m=100.0, reacquire_dist_max_m=100.0) if off else {}
        g = M.TargetGate(**kwargs)
        for k in range(5):
            assert g.accept(0.1*k, math.radians(2.0), 0.8+0.05*k, CHROMA, HIST)
        t, b, r = 1.6, math.radians(18), 7.43
        displacement = math.hypot(r*math.cos(b)-g.range*math.cos(g.bearing),
                                  r*math.sin(b)-g.range*math.sin(g.bearing))
        reach = min(g.reacquire_dist_max, g.reacquire_dist+g.reacquire_speed*(t-g.t))
        results['off' if off else 'on'] = dict(displacement_m=displacement, reach_m=reach,
                                              accepted=g.accept(t, b, r, CHROMA, HIST))
    assert not results['on']['accepted'] and results['off']['accepted']
    return results


def guard_outcome(module):
    case = TargetGateTest('test_gate_ros_parameters_match_the_gate_defaults')
    case.Gate, case.gate_params = module.TargetGate, module.GATE_PARAMS
    result = unittest.TestResult()
    case.run(result)
    return dict(passed=result.wasSuccessful(), failures=len(result.failures), errors=len(result.errors))


def constructor(module, overrides):
    """Execute the real constructor with strict declared-parameter and no-op ROS endpoint stubs."""
    class Node:
        def __init__(self, name):
            self.params = {}
        def declare_parameter(self, name, default):
            self.params[name] = overrides.get(name, default)
        def get_parameter(self, name):
            return SimpleNamespace(value=self.params[name])
        def create_subscription(self, *args):
            return None
        create_publisher = create_subscription
        create_timer = create_subscription
        def get_logger(self):
            return SimpleNamespace(info=lambda *a: None)
    class QoS:
        def __init__(self, **kwargs):
            pass
    env = dict(module.__dict__, Node=Node, QoSProfile=QoS,
               QoSReliabilityPolicy=SimpleNamespace(BEST_EFFORT=1),
               QoSHistoryPolicy=SimpleNamespace(KEEP_LAST=1),
               QoSDurabilityPolicy=SimpleNamespace(VOLATILE=1))
    tree = ast.parse(SOURCE)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SyncFusionNode')
    seen = {}
    real = module.TargetGate
    def spy(**kwargs):
        seen.update(kwargs)
        return real(**kwargs)
    env['TargetGate'] = spy
    exec(compile(ast.Module(body=[cls], type_ignores=[]), '<actual SyncFusionNode class>', 'exec'), env)
    obj = env['SyncFusionNode']()
    assert all(obj.params[k] == v and seen[k] == v for k, v in overrides.items())
    return dict(declared={k: obj.params[k] for k in module.GATE_PARAMS}, forwarded=seen)


def guard_checks():
    outcomes = {'production': guard_outcome(M)}
    original = dict(M.GATE_PARAMS)
    try:
        M.GATE_PARAMS['not_a_gate_argument'] = 1.0
        outcomes['unknown_gate_argument'] = guard_outcome(M)
        M.GATE_PARAMS.clear(); M.GATE_PARAMS.update(original)
        M.GATE_PARAMS['lateral_sigma_m'] = 0.151
        outcomes['default_drift'] = guard_outcome(M)
    finally:
        M.GATE_PARAMS.clear(); M.GATE_PARAMS.update(original)
    # These real source mutations leave the existing dictionary-only guard completely green.
    variants = {
        'forwarding_removed': SOURCE.replace('TargetGate(**{name: float(self.get_parameter(name).value) for name in GATE_PARAMS})', 'TargetGate()'),
        'declarations_removed': SOURCE.replace('self.declare_parameter(name, value)', 'pass'),
    }
    for label, text in variants.items():
        assert text != SOURCE
        env = dict(M.__dict__)
        execute_definitions(text, env, '<mutated fusion>')
        outcomes[label] = guard_outcome(SimpleNamespace(**env))
    overrides = {k: float(v)+0.0123 for k, v in M.GATE_PARAMS.items()}
    current = constructor(M, overrides)
    assert not outcomes['unknown_gate_argument']['passed'] and not outcomes['default_drift']['passed']
    assert outcomes['forwarding_removed']['passed'] and outcomes['declarations_removed']['passed']
    return dict(existing_guard_mutations=outcomes, real_constructor_with_stub_overrides=current,
                limitation='not an actual rclpy parameter service/CLI test')


def old_gate_equivalence():
    old_source = subprocess.check_output(['git', 'show', '13f570b:'+REL], cwd=ROOT).decode('utf-8')
    env = dict(M.__dict__)
    execute_definitions(old_source, env, '<13f570b fusion>')
    old_gate = env['TargetGate']
    rng = random.Random(15028)
    calls = 0
    for track in range(500):
        a, b = old_gate(), M.TargetGate(lateral_sigma_m=0.0)
        for i in range(40):
            t = i*0.1
            angle = rng.uniform(-0.6, 0.6) if i else 0.0
            distance = rng.uniform(0.3, 3.0) if i else 0.8
            chroma = (rng.uniform(120, 150), rng.uniform(110, 150)) if track % 3 else None
            hist = HIST if track % 2 else None
            assert a.cost(t, angle, distance, chroma, hist) == b.cost(t, angle, distance, chroma, hist)
            assert a.accept(t, angle, distance, chroma, hist) == b.accept(t, angle, distance, chroma, hist)
            state = dict(b.__dict__); state.pop('lateral_sigma')
            assert a.__dict__ == state
            calls += 1
    return dict(frames=calls, tracks=500, cost_accept_state_mismatches=0, baseline='13f570b')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    blob = subprocess.check_output(['git', 'show', '207ceda:'+REL], cwd=ROOT).decode('utf-8')
    assert SOURCE.replace('\r\n', '\n') == blob.replace('\r\n', '\n')
    report = dict(reviewed_hub='207ceda', data=inventory(), geometry=geometry(),
                  two_separate_people=two_people(), parameter_guard=guard_checks(),
                  t13_gate_level=t13_reacquisition(),
                  lateral_zero_equivalence=old_gate_equivalence(),
                  docker_closed_loop_rerun=False)
    args.out.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
