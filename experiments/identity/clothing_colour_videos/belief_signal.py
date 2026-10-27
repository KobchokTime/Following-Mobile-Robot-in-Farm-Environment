"""Does the identity belief tell when the gate has taken the wrong person? (use_belief off: report only)

Same cases and leave-one-clip-out colour table as belief_eval.py. At every frame where the gate takes a
box, record the belief after the update and whether the box was the target. AUC = chance that the
belief is higher on a correct take than on a wrong one.
"""
import sys, os, io, contextlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
S = sys.argv[1]
with contextlib.redirect_stdout(io.StringIO()):
    import belief_eval as be
from colour_models import hs_hist
from gate_replay import sf
from separability import auc

allr, allw = [], []
print(f"{'case':16s} | wrong takes | belief AUC (correct vs wrong takes)")
for k, (label, frames, others) in be.sep.CLIPS.items():
    g = sf.TargetGate(); g.COLOUR_LR = be.table(k); t = 0.0
    f = lambda r: ((r['cb'], r['cr']), [float(x) for x in hs_hist(r['hs'])])
    right, wrong = [], []
    for fr in frames:
        t += 0.1
        if not g.locked:
            first = sorted((r for r in fr if r['who'] == 'T'), key=lambda r: r['y1'] - r['y2'])
            if first: g.accept(t, 0.0, 0.8, *f(first[0]))
            continue
        pb, pr = g._predict(t)
        took = next((r for r in sorted(fr, key=lambda r: g.cost(t, pb, pr, *f(r))) if g.accept(t, pb, pr, *f(r))), None)
        if took is not None:
            (right if took['who'] == 'T' else wrong).append(g.belief)
    a = auc(right, wrong); allr += right; allw += wrong
    print(f"{k:16s} | {len(wrong):4d}/{len(right) + len(wrong):4d} | {'-' if a is None else f'{a:.2f}'}")
print(f"{'all':16s} | {len(allw):4d}/{len(allr) + len(allw):4d} | {auc(allr, allw):.2f}")
