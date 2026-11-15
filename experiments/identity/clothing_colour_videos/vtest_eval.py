"""Colour models on OpenCV's vtest.avi (PETS 2009 S2.L1, view 1): many people, mostly dark clothes.

Five people with recognisable clothes were labelled by eye (RN red/navy puffer, LB light blue
jacket, BL blonde in a black coat, RD red top, BJ blue jacket); everyone else is O, unclear boxes X.
Each person walks through the scene several times; each visit (gap > 2 s ends it) is replayed on its
own. The lock-on box is the visit's largest box that lies fully inside the image within its first
2 s, as the robot locks on a person standing close and in full view; the replay starts there (locking
on the first box, often half outside the image, gave a wrong reference for every method). Colour only,
as in gate_replay.py. Reported: in frames where the
person and someone else are both in view, how often the person scores best.
Usage: vtest_eval.py DATA_DIR  ($SYNC_FUSION: the gate from claude/robot/hs-colour)
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colour_models import load, hs_hist, GMMHS, Chroma
from gate_replay import sf

S = sys.argv[1]
NAMES = {'RN': 'red/navy puffer', 'LB': 'light blue jacket', 'BL': 'blonde, black coat', 'RD': 'red top', 'BJ': 'blue jacket'}


def visits(frames, who):
    out, cur, last = [], [], None
    for i, fr in enumerate(frames):
        if any(r['who'] == who for r in fr):
            if last is not None and i - last > 20:
                out.append(cur); cur = []
            last = i
        if last is not None and i - last <= 20:
            cur.append([dict(r, who=('T' if r['who'] == who else 'O')) for r in fr if r['who'] != 'X'])
    if cur: out.append(cur)
    keep = []
    for v in out:
        inside = [(r['y2'] - r['y1'], i) for i, fr in enumerate(v[:20]) for r in fr
                  if r['who'] == 'T' and r['x1'] > 4 and r['x2'] < W - 4 and r['y1'] > 4 and r['y2'] < H - 4]
        if not inside: continue
        v = v[max(inside)[1]:]  # start at the lock-on frame
        if sum(any(r['who'] == 'T' for r in fr) for fr in v) >= 20: keep.append(v)
    return keep


def replay_gate(frames, kind):
    g = sf.TargetGate(); t = 0.0; ranked = [0, 0]
    if kind == 'chroma':
        f = lambda r: ((r['cb'], r['cr']), None)
    else:
        f = lambda r: ((r['cb'], r['cr']), [float(x) for x in hs_hist(r['hs'])])
    if kind == 'hist':
        g.hist_weight = 1.0
    for fr in frames:
        t += 0.1
        if not g.locked:
            first = sorted((r for r in fr if r['who'] == 'T'), key=lambda r: r['y1'] - r['y2'])
            if first: g.accept(t, 0.0, 0.8, *f(first[0]))
            continue
        pb, pr = g._predict(t)
        order = sorted(fr, key=lambda r: g.cost(t, pb, pr, *f(r)))
        if any(r['who'] == 'T' for r in fr) and any(r['who'] != 'T' for r in fr):
            ranked[0] += order[0]['who'] == 'T'; ranked[1] += 1
        next((r for r in order if g.accept(t, pb, pr, *f(r))), None)
    return ranked


def replay_model(frames, model):
    ranked = [0, 0]; locked = False
    for fr in frames:
        if not locked:
            first = sorted((r for r in fr if r['who'] == 'T'), key=lambda r: r['y1'] - r['y2'])
            if first: model.init(first[0]); locked = True
            continue
        sc = sorted(((model.score(r), r) for r in fr), key=lambda x: -x[0])
        if any(r['who'] == 'T' for r in fr) and any(r['who'] != 'T' for r in fr):
            ranked[0] += sc[0][1]['who'] == 'T'; ranked[1] += 1
        if sc and model.accept(sc[0][0]): model.update(sc[0][1])
    return ranked


import json
meta = json.load(open(f"{S}/detections_vtest.json")); W, H = meta['width'], meta['height']
frames = load(S, 'vtest')
tot = collections.defaultdict(lambda: [0, 0])
chance = [0.0, 0]
print(f"{'person':22s} visits frames | Cb/Cr  hist  hist+Cb/Cr  GMM N=10")
for who, name in NAMES.items():
    vs = visits(frames, who); acc = collections.defaultdict(lambda: [0, 0])
    for v in vs:
        for fr in v[1:]:
            if any(r['who'] == 'T' for r in fr) and any(r['who'] != 'T' for r in fr):
                chance[0] += 1.0 / len(fr); chance[1] += 1
        for kind in ('chroma', 'hist', 'both'):
            a, b = replay_gate(v, kind); acc[kind][0] += a; acc[kind][1] += b
        a, b = replay_model(v, GMMHS(10)); acc['gmm'][0] += a; acc['gmm'][1] += b
    for k, (a, b) in acc.items(): tot[k][0] += a; tot[k][1] += b
    pct = lambda k: f"{100 * acc[k][0] / max(1, acc[k][1]):5.1f}%"
    print(f"{who} {name:19s} {len(vs):6d} {acc['chroma'][1]:6d} | {pct('chroma')} {pct('hist')} {pct('both')}     {pct('gmm')}")
print('all', ' '.join(f"{k} {100 * a / b:.1f}% ({a}/{b})" for k, (a, b) in tot.items()))
print(f"chance (a random pick among the boxes in view): {100 * chance[0] / chance[1]:.1f}%")
