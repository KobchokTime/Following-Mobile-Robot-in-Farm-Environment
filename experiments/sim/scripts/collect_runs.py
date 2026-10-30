"""Collect every twin run under a folder into JSON rows, with the pass rule used in the twin write-ups.

Usage: python3 experiments/sim/scripts/collect_runs.py <out_dir> > rows.json
Each row: run (folder), scenario, seed, pass_, contact, final_gap_m, target_visible_share,
max_abs_target_bearing_deg, target_in_camera_fov_end, published / published_other (whose box the fusion
node published, from world_node), gate_log (the effective gate settings), ros_params, realism.
"""
import json
import sys
from pathlib import Path


def passed(s):
    return bool(s.get('target_in_camera_fov_end')) and s['final_gap_m'] <= 1.5 and not s['contact'] \
        and s.get('target_visible_share', 0) >= 0.9


def _gate_line(run_dir):
    """The [GATE] line sync_fusion logs at start: the gate settings the run really used."""
    log = run_dir / 'sync_fusion.log'
    for line in (log.read_text(errors='replace').splitlines() if log.exists() else []):
        if '[GATE]' in line:
            return line.split('[GATE]', 1)[1].strip()
    return None


rows = []
for f in sorted(Path(sys.argv[1]).glob('*/*_mps/score.json')):
    s = json.loads(f.read_text())
    rows.append(dict(run=f.parent.parent.name, scenario=s['scenario'], seed=s['seed'], pass_=passed(s),
                     contact=bool(s['contact']), final_gap_m=round(s['final_gap_m'], 3),
                     target_visible_share=round(s.get('target_visible_share', 0), 3),
                     max_abs_target_bearing_deg=round(s['max_abs_target_bearing_deg'], 1),
                     target_in_camera_fov_end=bool(s.get('target_in_camera_fov_end')),
                     published=s.get('published'), published_other=s.get('published_other'),
                     published_other_share=s.get('published_other_share'),
                     gate_log=_gate_line(f.parent),
                     ros_params=s.get('ros_params', []), realism=bool(s.get('realism'))))
json.dump(rows, sys.stdout, indent=0)
