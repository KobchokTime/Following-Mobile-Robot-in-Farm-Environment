"""How well colour alone separates the target from other people, clip by clip.

For each clip the robot's TargetGate (colour only, as in gate_replay.py) follows the target from its
lock-on box. At every frame the colour cost of the target's box and of every other person's box is
taken against the gate's current model. "Others" are the other people in the same clip, and for the
one-person clips the strangers of heldout.py (a box of another clip's person, cycled in order).
AUC = chance that a random target box costs less than a random other box (1 = always apart,
0.5 = no better than a coin). Three colour models: Cb/Cr only, H,S histogram only, and the gate's mix.
Writes separability.json (per clip: AUC, time series, Cb/Cr points) and prints the AUC table.
Usage: separability.py DATA_DIR  ($SYNC_FUSION: the gate from claude/robot/hs-colour)
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
S = sys.argv[1]
sys.argv = [sys.argv[0], S, S]
from colour_models import hs_hist
from gate_replay import sf
import heldout

KINDS = {'chroma': 0.0, 'hist': 1.0, 'both': None}  # hist_weight; None = the gate's own


def auc(pos, neg):
    if not pos or not neg: return None
    import bisect
    neg = sorted(neg); wins = 0.0
    for p in pos:
        lo = bisect.bisect_left(neg, p); hi = bisect.bisect_right(neg, p)
        wins += (len(neg) - hi) + 0.5 * (hi - lo)
    return wins / (len(pos) * len(neg))


def follow(frames, kind):
    """Replay; return per-frame (t, target cost or None, [other costs])."""
    g = sf.TargetGate()
    if KINDS[kind] is not None: g.hist_weight = KINDS[kind]
    f = lambda r: ((r['cb'], r['cr']), [float(x) for x in hs_hist(r['hs'])] if kind != 'chroma' else None)
    t = 0.0; out = []
    for fr in frames:
        t += 0.1
        if not g.locked:
            first = sorted((r for r in fr if r['who'] == 'T'), key=lambda r: r['y1'] - r['y2'])
            if first: g.accept(t, 0.0, 0.8, *f(first[0]))
            continue
        cost = {id(r): g.colour_cost(*f(r)) for r in fr}
        tc = [cost[id(r)] for r in fr if r['who'] == 'T']
        out.append((round(t, 1), min(tc) if tc else None, [cost[id(r)] for r in fr if r['who'] != 'T']))  # time since the replay began
        pb, pr = g._predict(t)
        next((r for r in sorted(fr, key=lambda r: g.cost(t, pb, pr, *f(r))) if g.accept(t, pb, pr, *f(r))), None)
    return out


CLIPS = {}
lab = {'lab_1': 'WIN_20250408_14_00_41_Pro', 'lab_2': 'WIN_20250408_14_10_21_Pro'}
for name, v in lab.items():
    from colour_models import load
    fr = load(S, v)
    for tg, other, label in (('B', 'D', 'เป้า = เสื้อฟ้า'), ('D', 'B', 'เป้า = เสื้อเทาดำ')):
        CLIPS[f"{name}_{tg}"] = (label, [[dict(r, who='T' if r['who'] == tg else 'O') for r in f if r['who'] in 'BD'] for f in fr], 'same clip')
for n in heldout.CLIPS:
    if n.startswith('lab'): continue
    own = heldout.frames_of(n)
    pool = [r for b in heldout.CLIPS if heldout.CLIPS[b][3] != heldout.CLIPS[n][3]
            for fr in heldout.frames_of(b) for r in fr if r['who'] == 'T']
    pool = pool[::max(1, len(pool) // 400)]
    mixed = [fr + [dict(pool[k % len(pool)], who='O')] for k, fr in enumerate(own)]
    real = sum(1 for fr in own for r in fr if r['who'] == 'O')
    CLIPS[n] = (heldout.CLIPS[n][3], mixed, 'strangers from other clips' + (f' + {real} boxes of a real passer-by' if real else ''))

# the crowd video: each labelled person, every visit, against everyone else in view
vt = {'__file__': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vtest_eval.py')}
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    exec(open(vt['__file__']).read().split("tot = collections.defaultdict")[0], vt)
for who, name in vt['NAMES'].items():
    frames = [fr for v in vt['visits'](vt['frames'], who) for fr in v]
    CLIPS[f"vtest_{who}"] = (f"vtest: {name}", frames, 'everyone else in view (crowd)')

out = {}
print(f"{'clip':16s} {'others':40s} | AUC Cb/Cr  hist  mix")
for k, (label, frames, others) in CLIPS.items():
    res = {}
    for kind in KINDS:
        series = follow(frames, kind)
        pos = [c for _, c, _ in series if c is not None]; neg = [c for _, _, o in series for c in o]
        res[kind] = dict(auc=auc(pos, neg), series=series)
    pts = [dict(cb=r['cb'], cr=r['cr'], who=r['who']) for fr in frames for r in fr]
    out[k] = dict(label=label, others=others, auc={kk: res[kk]['auc'] for kk in KINDS},
                  series=[dict(t=t, target=None if c is None else round(c, 3), other_min=round(min(o), 3) if o else None)
                          for t, c, o in res['both']['series']],
                  series_chroma=[dict(t=t, target=None if c is None else round(c, 3), other_min=round(min(o), 3) if o else None)
                                 for t, c, o in res['chroma']['series']],
                  points=pts[::max(1, len(pts) // 600)])
    a = out[k]['auc']
    print(f"{k:16s} {others[:40]:40s} | {a['chroma']:.3f}   {a['hist']:.3f}  {a['both']:.3f}")
json.dump(out, open(os.path.join(S, 'separability.json'), 'w'))
