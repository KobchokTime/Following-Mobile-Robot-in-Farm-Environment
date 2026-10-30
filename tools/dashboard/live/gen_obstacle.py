#!/usr/bin/env python3
"""Build obstacle_runs.json and obstacle_paths.json: the obstacle stop/avoid off-vs-on runs, for the LiDAR-map tab.

Run folders are named <scenario>_<off|on>_s<seed> (sim.twin.run_scenario --out sim_runs/<tag>), as made by
the off/on comparison: pass_by with obstacle_avoid false/true, blind_corner with obstacle_stop false/true.

    python3 tools/dashboard/live/gen_obstacle.py --runs <dir> --code <commit> --out <out_dir>
"""
import argparse
import glob
import json
import math
import os
import re
import sys

TAG = re.compile(r'^(?P<scenario>[a-z_]+)_(?P<variant>off|on)_s(?P<seed>\d+)$')
SWITCH = {'pass_by': 'obstacle_avoid', 'blind_corner': 'obstacle_stop'}


def passed(s):
    """The pass rule used everywhere: in view at the end, final gap <= 1.5 m, no contact, in view >= 90%."""
    return bool(s.get('target_in_camera_fov_end')) and s['final_gap_m'] <= 1.5 and not s['contact'] \
        and s.get('target_visible_share', 0) >= 0.9


def world(robot, person):
    """A person's world (x, y) from the robot pose and the person's range and bearing from the robot."""
    a = math.radians(robot['yaw_deg'] + person['bearing_deg'])
    return robot['x'] + person['range_m'] * math.cos(a), robot['y'] + person['range_m'] * math.sin(a)


def one_run(tag, run_dir, code, hz):
    m = TAG.match(tag)
    score = json.load(open(glob.glob(os.path.join(run_dir, '*_mps', 'score.json'))[0], encoding='utf-8'))
    states = [json.loads(line) for line in open(glob.glob(os.path.join(run_dir, '*_mps', 'state.jsonl'))[0],
                                                 encoding='utf-8') if line.strip()]
    run_id = f"{m['scenario']}-{m['variant']}-{m['seed']}"
    others = [n for n, p in states[0]['people'].items() if not p['is_target']]
    target = next(n for n, p in states[0]['people'].items() if p['is_target'])
    closest = min(states, key=lambda r: min(r['people'][n]['range_m'] for n in others))
    ox, oy = world(closest['robot'], closest['people'][others[0]])
    summary = dict(run_id=run_id, scenario=m['scenario'], variant=m['variant'], seed=int(m['seed']),
                   switch=SWITCH.get(m['scenario'], ''), code=code, **{'pass': passed(score)},
                   contact=bool(score['contact']), min_other_m=round(score.get('min_other_range_m', 9.0), 3),
                   final_gap_m=round(score['final_gap_m'], 2),
                   target_visible_share=round(score.get('target_visible_share', 0), 3),
                   closest_t=round(closest['t'], 1), closest_robot_x=round(closest['robot']['x'], 3),
                   closest_robot_y=round(closest['robot']['y'], 3),
                   closest_robot_yaw_deg=round(closest['robot']['yaw_deg'], 1),
                   other_x=round(ox, 3), other_y=round(oy, 3))
    step = max(1, round(1.0 / (hz * (states[1]['t'] - states[0]['t']))))
    paths = []
    for r in states[::step]:
        tx, ty = world(r['robot'], r['people'][target])
        paths.append(dict(run_id=run_id, t=round(r['t'], 1), robot_x=round(r['robot']['x'], 3),
                          robot_y=round(r['robot']['y'], 3), robot_yaw_deg=round(r['robot']['yaw_deg'], 1),
                          target_x=round(tx, 3), target_y=round(ty, 3)))
    return summary, paths


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runs', required=True)
    ap.add_argument('--code', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--hz', type=float, default=5.0)
    a = ap.parse_args(argv)
    runs, paths = [], []
    for run_dir in sorted(glob.glob(os.path.join(a.runs, '*'))):
        tag = os.path.basename(run_dir)
        if not os.path.isdir(run_dir) or not TAG.match(tag) or not glob.glob(os.path.join(run_dir, '*_mps', 'score.json')):
            continue
        s, p = one_run(tag, run_dir, a.code, a.hz)
        runs.append(s)
        paths.extend(p)
    if not runs:
        sys.exit('no finished off/on runs')
    os.makedirs(a.out, exist_ok=True)
    for name, rows in (('obstacle_runs.json', runs), ('obstacle_paths.json', paths)):
        json.dump(rows, open(os.path.join(a.out, name), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f"{len(runs)} runs, {len(paths)} path points")
    return 0


if __name__ == '__main__':
    sys.exit(main())
