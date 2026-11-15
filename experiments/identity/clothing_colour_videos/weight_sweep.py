"""How the histogram's share of the colour cost (hist_weight) trades off across all three video sets.

Usage: weight_sweep.py DATA_DIR ($SYNC_FUSION: the gate from claude/robot/hs-colour)
"""
import sys, os, io, contextlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
S = sys.argv[1]
from colour_models import load, VIDS
import gate_replay
from gate_replay import sf
sys.argv = [sys.argv[0], S, S]
import heldout
Base = sf.TargetGate
with contextlib.redirect_stdout(io.StringIO()):
    vt_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vtest_eval.py')).read().split("tot = collections.defaultdict")[0]
    vt = {'__file__': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vtest_eval.py')}
    exec(vt_src, vt)
lab = [load(S, v) for v, _ in VIDS]
new = {n: heldout.frames_of(n) for n in heldout.CLIPS if not n.startswith('lab')}
strangers = []
for a in new:
    for b in heldout.CLIPS:
        if heldout.CLIPS[a][3] == heldout.CLIPS[b][3]: continue
        pool = [r for fr in (new[b] if b in new else heldout.frames_of(b)) for r in fr if r['who'] == 'T']
        strangers.append([fr + [dict(pool[k % len(pool)], who='O')] for k, fr in enumerate(new[a])])
vis = {w: vt['visits'](vt['frames'], w) for w in vt['NAMES']}
print("hist_weight | lab ranked (min of 4) | held-out kept own (min, mean) | strangers ranked | vtest ranked (min person, all)")
for w in (0.0, 0.25, 0.5, 0.65, 0.75, 0.85, 1.0):
    class G(Base):
        def __init__(self, **k):
            super().__init__(**k); self.hist_weight = w
    sf.TargetGate = G
    labr = []
    for fr in lab:
        for tg in 'BD':
            _, rk = gate_replay.replay(fr, tg, True); labr.append(100 * rk[0] / rk[1])
    keep = []
    for n, fr in new.items():
        st, _ = heldout.replay(fr, True); keep.append(100 * st['CT'] / (st['CT'] + st['WL']))
    s = [0, 0]
    for m in strangers:
        _, rk = heldout.replay(m, True); s[0] += rk[0]; s[1] += rk[1]
    per = []; tot = [0, 0]
    for who, vs in vis.items():
        a = b = 0
        for v in vs:
            x, y = vt['replay_gate'](v, 'both'); a += x; b += y
        per.append(100 * a / max(1, b)); tot[0] += a; tot[1] += b
    print(f"{w:11.2f} | {min(labr):20.1f} | {min(keep):6.1f} {sum(keep) / len(keep):6.1f}        | {100 * s[0] / s[1]:16.1f} | {min(per):6.1f} {100 * tot[0] / tot[1]:6.1f}")
