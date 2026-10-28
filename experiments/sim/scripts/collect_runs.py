"""Collect every twin run under a folder into JSON rows, with the pass rule used in the twin write-ups.

Usage: python3 experiments/sim/scripts/collect_runs.py <out_dir> > rows.json
Each row: run (folder), scenario, seed, pass_, contact, final_gap_m, target_visible_share,
max_abs_target_bearing_deg, ros_params, realism.
"""
import json
import sys
from pathlib import Path


def passed(s):
    return bool(s.get('target_in_camera_fov_end')) and s['final_gap_m'] <= 1.5 and not s['contact'] \
        and s.get('target_visible_share', 0) >= 0.9


rows = []
for f in sorted(Path(sys.argv[1]).glob('*/*_mps/score.json')):
    s = json.loads(f.read_text())
    rows.append(dict(run=f.parent.parent.name, scenario=s['scenario'], seed=s['seed'], pass_=passed(s),
                     contact=bool(s['contact']), final_gap_m=round(s['final_gap_m'], 3),
                     target_visible_share=round(s.get('target_visible_share', 0), 3),
                     max_abs_target_bearing_deg=round(s['max_abs_target_bearing_deg'], 1),
                     ros_params=s.get('ros_params', []), realism=bool(s.get('realism'))))
json.dump(rows, sys.stdout, indent=0)
