"""Gate colour variants on both sets: the two-person lab videos (tuning set) and the five held-out clips.

Usage: variants_heldout.py LAB_DIR NEW_DIR. Variants subclass the robot's TargetGate, so only the colour
term changes. All share the committed window (10) and learn slack (0.1).
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colour_models import load, hs_hist, hs_hist2, VIDS
from gate_replay import sf
import heldout

LAB, NEW = sys.argv[1], sys.argv[2]


def make_gate(kind):
    class G(sf.TargetGate):
        def cost(self, t, bearing, rng, chroma=None, hist=None):
            if kind == 'chroma':
                return super().cost(t, bearing, rng, chroma, None)
            c = super().cost(t, bearing, rng, None, None)  # geometry only (no colour) ...
            if kind == 'both' and chroma is not None and self.chroma is not None:
                c += 0.5 * ((chroma[0] - self.chroma[0]) ** 2 + (chroma[1] - self.chroma[1]) ** 2) / self.sc ** 2
            if hist is not None and self.hists:
                d = math.sqrt(max(0.0, 1.0 - sf.bhattacharyya(hist, self.hist_model())))
                c += (0.5 if kind == 'both' else 1.0) * (d / self.hist_sigma) ** 2
            return c
    return G


def feats_for(kind):
    f = hs_hist2 if kind.startswith('grey') or kind == 'both_grey' else hs_hist
    return lambda r: ((r['cb'], r['cr']), None if kind == 'chroma' else [float(x) for x in f(r['hs'])])


VARIANTS = {'chroma': 'chroma', 'hist': 'hist', 'grey bin': 'hist', 'hist + chroma': 'both', 'grey bin + chroma': 'both'}
FEATS = {'chroma': 'chroma', 'hist': 'hist', 'grey bin': 'grey', 'hist + chroma': 'hist', 'grey bin + chroma': 'grey'}


def replay(frames, target, Gate, feats):
    g = Gate(); ranked = [0, 0]; acc = [0, 0]; t = 0.0
    for fr in frames:
        t += 0.1
        here = any(r['who'] == target for r in fr)
        if not g.locked:
            first = [r for r in fr if r['who'] == target]
            if first: g.accept(t, 0.0, 0.8, *feats(first[0]))
            continue
        pb, pr = g._predict(t)
        order = sorted(fr, key=lambda r: g.cost(t, pb, pr, *feats(r)))
        if here and any(r['who'] != target for r in fr):
            ranked[0] += order[0]['who'] == target; ranked[1] += 1
        took = next((r for r in order if g.accept(t, pb, pr, *feats(r))), None)
        if here:
            acc[1] += 1; acc[0] += took is not None and took['who'] == target
    return ranked, acc


lab = [load(LAB, v) for v, _ in VIDS]
new = {n: heldout.frames_of(n) for n in heldout.CLIPS}
print(f"{'variant':20s} | lab: ranked first (B1 B2 D1 D2) | held-out: kept own (min, mean) | strangers ranked first")
for name, kind in VARIANTS.items():
    Gate, feats = make_gate(kind), feats_for(FEATS[name])
    labr = [replay(fr, tg, Gate, feats)[0] for tg in 'BD' for fr in lab]
    keep = []
    for n in heldout.CLIPS:
        if n.startswith('lab'): continue
        _, a = replay(new[n], 'T', Gate, feats); keep.append(a[0] / a[1])
    tot = [0, 0]
    for a in heldout.CLIPS:
        if a.startswith('lab'): continue
        for b in heldout.CLIPS:
            if heldout.CLIPS[a][3] == heldout.CLIPS[b][3]: continue
            pool = [r for fr in new[b] for r in fr if r['who'] == 'T']
            mixed = [fr + [dict(pool[k % len(pool)], who='O')] for k, fr in enumerate(new[a])]
            rk, _ = replay(mixed, 'T', Gate, feats); tot[0] += rk[0]; tot[1] += rk[1]
    print(f"{name:20s} | " + ' '.join(f"{100 * r[0] / r[1]:5.1f}" for r in labr)
          + f" | {100 * min(keep):5.1f} {100 * sum(keep) / len(keep):5.1f} | {100 * tot[0] / tot[1]:5.1f}")
