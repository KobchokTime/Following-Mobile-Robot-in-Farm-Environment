"""Build the "ติดตามสด" (live monitor) datasets of the Follower Test Bench dashboard from twin run folders.

Usage (from the repository root):
    python3 tools/dashboard/live/gen_live.py --runs-root <folder holding each experiment's run dir> --out <out dir>

Inputs:
    tools/dashboard/live/registry.json   experiments and their expected runs (schema in tools/dashboard/README.md)
    <runs-root>/<experiment dir>/<tag>/<scenario>_mps/{world.log, score.json, state.jsonl}
                                          what sim.twin.run_scenario writes for each run
Outputs in --out:
    live_experiments.json, live_runs.json, live_tracks.json, past_tracks.json, live_scenarios.json
    tracks_cache.json (reused on the next call so finished runs are not re-read)

A run is done when its score.json exists, running when only its world.log exists, and queued otherwise.
Pass rule, as in every twin write-up: target in view at the end, final gap <= 1.5 m, no contact, and the
target in view >= 90% of the time.
"""
import argparse
import datetime
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from sim.twin.scenarios import SCENARIO_LOOKUP  # noqa: E402

# Thai descriptions shown on the scenario mini-maps (English docs are in sim/twin/scenarios.py)
TH = {
    'close_pair_same': 'สองคนใส่เสื้อเหมือนกันเดินคู่กันห่าง 0.44 m แล้วอีกคนแยกเลี้ยวซ้าย',
    'come_back': 'เดินออกไป 3 m แล้วหันกลับมาหาหุ่น 1.5 m แบบคนงานเดินมาวางของบนรถ แล้วยืนนิ่ง',
    'crossing': 'เดินตรง มีอีกคนเดินตัดผ่านระหว่างหุ่นกับเป้า',
    'curve_left': 'เดินตรงแล้วเลี้ยวซ้ายราว 60°',
    'head_on': 'เดินตรง มีอีกคนเดินสวนเข้าหาหุ่น ผ่านทางซ้าย 0.8 m',
    'lookalike_after_loss': 'เดินตรง กล้องมองไม่เห็นเป้าช่วง 10–12 s (LiDAR ยังเห็น) ขณะมีคนใส่เสื้อเหมือนกันยืนไกล ~7.4 m ทางซ้าย 18°',
    'shade_crossing': 'แบบตัดหน้า แต่เป้าใส่เสื้อฟ้า คนตัดใส่เทา และตรงนั้นเป็นเงาเข้ม',
    'shade_side_by_side': 'แบบเดินคู่ เป้าเสื้อฟ้า อีกคนเสื้อเทา จุดเริ่มอยู่ในเงา',
    'side_by_side': 'อีกคนเดินนำขวาของเป้า แล้วแยกเลี้ยวขวาขณะเป้าเลี้ยวซ้าย',
    'side_by_side_same': 'แบบเดินคู่ แต่ใส่เสื้อสีเดียวกัน สีเสื้อแยกไม่ได้',
    'side_step': 'ก้าวออกข้าง 1 m จนหลุดภาพกล้อง แล้วเดินต่อ',
    'stand_aside': 'เดินผ่านคนที่ยืนห่างทางขวา 0.7 m',
    'stop_and_go': 'เดิน หยุด 5 s แล้วเดินต่อ',
    'straight': 'เดินตรง 0.3 m/s แล้วหยุด',
    'target_loss': 'เดินตรง ตัวตรวจจับมองไม่เห็นใครเลยช่วง 10–14 s',
    'turn_90': 'เดิน 3 m เลี้ยวซ้าย 90° แล้วเดินต่ออีก 3 m',
    'walk_0p6': 'เดินตรง 0.6 m/s นาน 10 s แล้วหยุด',
    'walk_1p0': 'เดินตรง 1.0 m/s (เดินปกติ) นาน 8 s แล้วหยุด',
    'zigzag': 'เดินส่ายซ้ายขวา 0.6 m ทุก 3 s',
}


def iso(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def passed(s):
    return bool(s.get('target_in_camera_fov_end')) and s['final_gap_m'] <= 1.5 and not s['contact'] \
        and s.get('target_visible_share', 0) >= 0.9


def run_rows(e, base, now):
    rows = []
    for r in e['runs']:
        d = os.path.join(base, r['tag'], f"{r['scenario']}_mps")
        sc, wl = os.path.join(d, 'score.json'), os.path.join(d, 'world.log')
        row = dict(experiment=e['id'], run=f"{e['id']}|{r['tag']}|{r['scenario']}", scenario=r['scenario'],
                   seed=r['seed'], variant=r['variant'], light=r['light'], status='queued', final_gap_m=None,
                   visible_share=None, contact=None, max_bearing_deg=None, in_view_end=None, published=None,
                   published_other=None, started_utc=None, finished_utc=None)
        if os.path.exists(sc):
            s = json.load(open(sc, encoding='utf-8'))
            row.update(status='pass' if passed(s) else 'fail', final_gap_m=round(s['final_gap_m'], 2),
                       visible_share=round(s.get('target_visible_share', 0), 3), contact=bool(s['contact']),
                       max_bearing_deg=round(s['max_abs_target_bearing_deg'], 1),
                       in_view_end=bool(s.get('target_in_camera_fov_end')), published=s.get('published'),
                       published_other=s.get('published_other'), finished_utc=iso(os.path.getmtime(sc)))
            if os.path.exists(wl):
                row['started_utc'] = iso(os.path.getmtime(wl))
        elif os.path.exists(wl):
            row.update(status='running', started_utc=iso(os.path.getmtime(wl)))
        rows.append(row)
    return rows


def experiment_row(e, rows, now):
    done = [r for r in rows if r['status'] in ('pass', 'fail')]
    fin = sorted(r['finished_utc'] for r in done)
    eta = None
    if done and len(done) < len(rows):
        t0 = datetime.datetime.fromisoformat(e['started_utc'].replace('Z', '+00:00'))
        eta = round((now - t0).total_seconds() / len(done) * (len(rows) - len(done)) / 60, 1)
    if len(done) == len(rows):
        status = 'done'
    elif any(r['status'] == 'running' for r in rows) or done:
        status = 'running'
    else:
        status = 'queued'
    if e.get('stopped') and status != 'done':
        status = 'stopped'
    return dict(experiment=e['id'], title=e['title'], code=e['code'], order=e.get('order', 0), total=len(rows),
                done=len(done), passed=sum(r['status'] == 'pass' for r in rows),
                failed=sum(r['status'] == 'fail' for r in rows), running=sum(r['status'] == 'running' for r in rows),
                status=status, started_utc=e['started_utc'], last_finished_utc=fin[-1] if fin else None,
                purpose=e.get('purpose', ''), compare=e.get('compare', ''), result=e.get('result', ''), eta_min=eta,
                checked_utc=now.strftime('%Y-%m-%dT%H:%M:%SZ'))


def track_points(key, state_path):
    """World-frame positions at 2 Hz (every 5th 10 Hz state line)."""
    pts = []
    for i, line in enumerate(open(state_path, encoding='utf-8')):
        if i % 5:
            continue
        s = json.loads(line)
        rb = s['robot']
        yaw = math.radians(rb['yaw_deg'])
        row = dict(run=key, t=round(s['t'], 1), rx=round(rb['x'], 2), ry=round(rb['y'], 2), ryaw=round(rb['yaw_deg'], 1),
                   v=round(rb['v'], 2), tx=None, ty=None, ox=None, oy=None, gap=None, tb=None)
        for p in s['people'].values():
            a = yaw + math.radians(p['bearing_deg'])
            x, y = round(rb['x'] + p['range_m'] * math.cos(a), 2), round(rb['y'] + p['range_m'] * math.sin(a), 2)
            if p['is_target']:
                row.update(tx=x, ty=y, gap=round(p['range_m'] - 0.2, 2), tb=round(p['bearing_deg'], 1))
            elif row['ox'] is None:
                row.update(ox=x, oy=y)
        pts.append(row)
    return pts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--registry', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'registry.json'))
    ap.add_argument('--runs-root', required=True, help='folder the registry dirs are relative to')
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    reg = json.load(open(a.registry, encoding='utf-8'))
    now = datetime.datetime.now(datetime.timezone.utc)

    runs, exps = [], []
    for e in reg:
        rows = run_rows(e, os.path.join(a.runs_root, e['dir']), now)
        runs += rows
        exps.append(experiment_row(e, rows, now))
    json.dump(exps, open(os.path.join(a.out, 'live_experiments.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(runs, open(os.path.join(a.out, 'live_runs.json'), 'w', encoding='utf-8'), ensure_ascii=False)

    cache_p = os.path.join(a.out, 'tracks_cache.json')
    cache = json.load(open(cache_p, encoding='utf-8')) if os.path.exists(cache_p) else {}
    tracks, live_tracks = [], []
    for e in reg:
        for r in e['runs']:
            key = f"{e['id']}|{r['tag']}|{r['scenario']}"
            d = os.path.join(a.runs_root, e['dir'], r['tag'], f"{r['scenario']}_mps")
            if key not in cache and os.path.exists(os.path.join(d, 'score.json')):
                cache[key] = track_points(key, os.path.join(d, 'state.jsonl'))
            pts = cache.get(key, [])
            # finished experiments at 1 Hz (every other point) to stay under the dashboard's 8 MB file limit
            if e.get('live'):
                live_tracks.extend(pts)
            else:
                tracks.extend(pts[::2])
    json.dump(cache, open(cache_p, 'w', encoding='utf-8'))
    json.dump(tracks, open(os.path.join(a.out, 'past_tracks.json'), 'w', encoding='utf-8'), separators=(',', ':'))
    json.dump(live_tracks, open(os.path.join(a.out, 'live_tracks.json'), 'w', encoding='utf-8'), separators=(',', ':'))

    names = sorted({r['scenario'] for e in reg for r in e['runs']})
    scen = []
    for n in names:
        # a scenario from a branch not checked out here still gets a row, without its map
        sp = SCENARIO_LOOKUP.get(n, dict(doc=n, duration_s=None, people=[]))
        scen.append(dict(scenario=n, doc=TH.get(n, sp['doc']), duration_s=sp['duration_s'], people=len(sp['people']),
                         paths=json.dumps([dict(name=pn, target=tg, wp=wp) for pn, tg, wp in sp['people']]),
                         notes=json.dumps(dict(blackouts=sp.get('blackouts', []), hidden=sp.get('hidden', {}),
                                               shade=sp.get('shade', []), clothing=sp.get('clothing', {})))))
    json.dump(scen, open(os.path.join(a.out, 'live_scenarios.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(' | '.join(f"{x['experiment']} {x['done']}/{x['total']} {x['status']}" for x in exps))
    return 0


if __name__ == '__main__':
    sys.exit(main())
