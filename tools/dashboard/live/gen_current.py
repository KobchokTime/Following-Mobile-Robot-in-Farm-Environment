#!/usr/bin/env python3
"""Build current_runs.json: one row per finished run of a whole-twin baseline (run_baseline.sh).

The dashboard's "current code" cards read it, so every tab can show how the code on integration-hub does
today next to its dated experiments.

    python3 tools/dashboard/live/gen_current.py --runs <baseline_out_dir> --code <commit> --out current_runs.json
"""
import argparse
import datetime
import glob
import json
import os
import sys

SOLO = ['straight', 'stop_and_go', 'curve_left', 'target_loss', 'walk_0p6', 'walk_1p0', 'turn_90', 'side_step',
        'come_back', 'zigzag']
IDENTITY = ['crossing', 'side_by_side', 'side_by_side_same', 'head_on', 'stand_aside']
COLOUR = ['shade_crossing', 'shade_side_by_side', 'lookalike_after_loss', 'close_pair_same', 'walk_up_same']


def group_of(scenario):
    return 'solo' if scenario in SOLO else 'identity' if scenario in IDENTITY else \
        'colour' if scenario in COLOUR else 'other'


def passed(s):
    """The pass rule used everywhere: in view at the end, final gap <= 1.5 m, no contact, in view >= 90%."""
    return bool(s.get('target_in_camera_fov_end')) and s['final_gap_m'] <= 1.5 and not s['contact'] \
        and s.get('target_visible_share', 0) >= 0.9


def rows(runs_dir, code):
    out = []
    for path in sorted(glob.glob(os.path.join(runs_dir, '*', '*_mps', 'score.json'))):
        s = json.load(open(path, encoding='utf-8'))
        tag = path.split(os.sep)[-3]
        out.append(dict(
            run=tag, scenario=s['scenario'], **{'pass': passed(s)}, group=group_of(s['scenario']), seed=s['seed'], realism=bool(s['realism']),
            code=code, contact=bool(s['contact']), final_gap_m=round(s['final_gap_m'], 2),
            visible_share=round(s.get('target_visible_share', 0), 3),
            min_person_range_m=round(s['min_person_range_m'], 2),
            published_other=s.get('published_other'),
            finished_utc=datetime.datetime.fromtimestamp(os.path.getmtime(path), datetime.timezone.utc)
            .strftime('%Y-%m-%dT%H:%M:%SZ')))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runs', required=True)
    ap.add_argument('--code', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    r = rows(a.runs, a.code)
    if not r:
        sys.exit('no finished runs')
    json.dump(r, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f"{len(r)} runs, {sum(x['pass'] for x in r)} passed")
    return 0


if __name__ == '__main__':
    sys.exit(main())
