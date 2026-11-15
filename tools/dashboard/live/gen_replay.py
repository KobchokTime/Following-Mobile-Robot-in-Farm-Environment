#!/usr/bin/env python3
"""Build replay_runs.json and replay_paths.json: two whole-twin baselines side by side, for the replay cards
on the follow, target-gate and colour tabs (before vs now).

Each --set is <variant>=<code>=<runs_dir>, a run_baseline.sh output folder (<scenario>_s<seed>/<scenario>_mps).

    python3 tools/dashboard/live/gen_replay.py --set before=5c72c4d=<dir> --set now=7b0d8ae=<dir> --out <out_dir>
"""
import argparse
import glob
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_current import group_of, passed  # noqa: E402  (same groups and pass rule as current_runs)


def world(robot, person):
    """A person's world (x, y) from the robot pose and the person's range and bearing from the robot."""
    a = math.radians(robot['yaw_deg'] + person['bearing_deg'])
    return robot['x'] + person['range_m'] * math.cos(a), robot['y'] + person['range_m'] * math.sin(a)


def one_run(variant, code, run_dir, hz):
    score = json.load(open(glob.glob(os.path.join(run_dir, '*_mps', 'score.json'))[0], encoding='utf-8'))
    states = [json.loads(line) for line in open(glob.glob(os.path.join(run_dir, '*_mps', 'state.jsonl'))[0],
                                                 encoding='utf-8') if line.strip()]
    scenario, seed = score['scenario'], int(score['seed'])
    run_id = f"{scenario}-{variant}-{seed}"
    target = next(n for n, p in states[0]['people'].items() if p['is_target'])
    others = [n for n in states[0]['people'] if n != target]
    summary = dict(run_id=run_id, scenario=scenario, group=group_of(scenario), variant=variant, seed=seed, code=code,
                   **{'pass': passed(score)}, contact=bool(score['contact']),
                   final_gap_m=round(score['final_gap_m'], 2), visible_share=round(score.get('target_visible_share', 0), 3),
                   min_person_range_m=round(score['min_person_range_m'], 2), others=others,
                   duration_s=round(states[-1]['t'], 1))
    step = max(1, round(1.0 / (hz * (states[1]['t'] - states[0]['t']))))
    paths = []
    for r in states[::step] + ([states[-1]] if (len(states) - 1) % step else []):
        tx, ty = world(r['robot'], r['people'][target])
        row = dict(run_id=run_id, t=round(r['t'], 1), rx=round(r['robot']['x'], 3), ry=round(r['robot']['y'], 3),
                   yaw=round(r['robot']['yaw_deg'], 1), v=round(r['robot']['v'], 2), w=round(r['robot']['w'], 2),
                   tx=round(tx, 3), ty=round(ty, 3), pub=(r.get('synced') or [''])[0])
        for i, n in enumerate(others):
            ox, oy = world(r['robot'], r['people'][n])
            row[f'o{i}x'], row[f'o{i}y'] = round(ox, 3), round(oy, 3)
        paths.append(row)
    return summary, paths


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--set', action='append', required=True, help='<variant>=<code>=<runs_dir>')
    ap.add_argument('--out', required=True)
    ap.add_argument('--hz', type=float, default=2.5)
    ap.add_argument('--groups', default='solo,identity,colour')
    a = ap.parse_args(argv)
    groups = set(a.groups.split(','))
    runs, paths = [], []
    for spec in a.set:
        variant, code, runs_dir = spec.split('=', 2)
        for run_dir in sorted(glob.glob(os.path.join(runs_dir, '*_s*'))):
            if not os.path.isdir(run_dir) or not glob.glob(os.path.join(run_dir, '*_mps', 'score.json')):
                continue
            s, p = one_run(variant, code, run_dir, a.hz)
            if s['group'] in groups:
                runs.append(s)
                paths.extend(p)
    if not runs:
        sys.exit('no finished runs')
    os.makedirs(a.out, exist_ok=True)
    for name, rows in (('replay_runs.json', runs), ('replay_paths.json', paths)):
        json.dump(rows, open(os.path.join(a.out, name), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f"{len(runs)} runs, {len(paths)} path points")
    return 0


if __name__ == '__main__':
    sys.exit(main())
