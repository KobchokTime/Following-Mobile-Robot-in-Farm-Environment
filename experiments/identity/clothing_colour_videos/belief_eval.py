"""Identity belief on the labelled videos: TargetGate with use_belief on and off, colour only.

The colour likelihood table is rebuilt for each case without that case's own clip (leave one clip
out) from separability.json. Cases: the lab pairs (the other person), the five one-person clips
with a stranger box each frame, and the vtest crowd. Reported per case: kept own (share of the
target's frames in which the gate takes the target) and wrong takes (share of all frames in which
it takes someone else). Usage: belief_eval.py DATA_DIR  ($SYNC_FUSION: gate with identity belief)
"""
import sys, os, json, io, contextlib
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
S = sys.argv[1]
sys.argv = [sys.argv[0], S]
with contextlib.redirect_stdout(io.StringIO()):
    import separability as sep  # builds the cases (sep.CLIPS) and the per-step costs file
from colour_models import hs_hist
from gate_replay import sf

D = json.load(open(os.path.join(S, 'separability.json')))
KNOTS = (0.0, 0.5, 1.0, 2.0, 3.0)


def table(exclude):
    group = exclude.split('_')[0] if exclude.startswith(('lab', 'vtest')) else exclude  # a lab clip's two targets go together
    same = np.array([s['target'] for k, v in D.items() if not k.startswith(group) for s in v['series'] if s['target'] is not None])
    oth = np.array([s['other_min'] for k, v in D.items() if not k.startswith(group) for s in v['series'] if s['other_min'] is not None])
    out = []
    for c in KNOTS:
        sel = (lambda a: a >= 2.5) if c == 3.0 else (lambda a, c=c: np.abs(a - c) < 0.25)
        r = np.mean(sel(same)) / max(np.mean(sel(oth)), 1e-6)
        out.append((c, float(min(5.0, max(0.1, r)))))
    return tuple(out)


def replay(frames, use_belief, knots):
    g = sf.TargetGate(use_belief=use_belief); g.COLOUR_LR = knots; t = 0.0
    f = lambda r: ((r['cb'], r['cr']), [float(x) for x in hs_hist(r['hs'])])
    st = dict(CT=0, CL=0, WT=0, WL=0); doubts = 0
    for fr in frames:
        t += 0.1
        here = any(r['who'] == 'T' for r in fr)
        if not g.locked:
            first = sorted((r for r in fr if r['who'] == 'T'), key=lambda r: r['y1'] - r['y2'])
            if first: g.accept(t, 0.0, 0.8, *f(first[0]))
            continue
        pb, pr = g._predict(t)
        was = g.suspect
        took = next((r for r in sorted(fr, key=lambda r: g.cost(t, pb, pr, *f(r))) if g.accept(t, pb, pr, *f(r))), None)
        doubts += (g.suspect and not was)
        st[('CT' if took['who'] == 'T' else 'WT') if took else ('WL' if here else 'CL')] += 1
    n = sum(st.values())
    return 100 * st['CT'] / max(1, st['CT'] + st['WL']), 100 * st['WT'] / max(1, n), doubts


print(f"{'case':16s} | kept own: off -> on | wrong takes: off -> on | times in doubt (on)")
tot = {False: [0, 0], True: [0, 0]}
for k, (label, frames, others) in sep.CLIPS.items():
    knots = table(k)
    off = replay(frames, False, knots); on = replay(frames, True, knots)
    print(f"{k:16s} | {off[0]:5.1f} -> {on[0]:5.1f}     | {off[1]:5.1f} -> {on[1]:5.1f}          | {on[2]}")
    tot[False][0] += off[0]; tot[False][1] += off[1]; tot[True][0] += on[0]; tot[True][1] += on[1]
n = len(sep.CLIPS)
print(f"{'mean':16s} | {tot[False][0] / n:5.1f} -> {tot[True][0] / n:5.1f}     | {tot[False][1] / n:5.1f} -> {tot[True][1] / n:5.1f}")
