"""Colour-only target identification on the two lab videos: our chroma reference against the paper's H,S GMM."""
import sys, gzip, json, numpy as np, warnings
from sklearn.mixture import GaussianMixture
warnings.filterwarnings('ignore')
S = sys.argv[1]
VIDS = (("WIN_20250408_14_00_41_Pro", "14_00_41"), ("WIN_20250408_14_10_21_Pro", "14_10_21"))

def load(v, lf):
    rows = json.load(open(f"{S}/detections_{v}.json"))['rows']; L = json.load(open(f"{S}/labels_{v}.json"))
    hs = json.load(gzip.open(f"{S}/hs_pixels_{v}.json.gz", "rt"))
    for r in rows:
        r['who'] = L[str(r['id'])]; r['hs'] = np.array(hs.get(str(r['id']), [[0, 0]]), float)
    frames = {}
    for r in rows: frames.setdefault(r['frame'], []).append(r)
    return [frames[f] for f in sorted(frames)]

class Chroma:
    """Ours: TargetGate's colour term. Reference from lock-on, nudged 5 % towards each accepted box."""
    def __init__(self, rate=0.05, gate=45.0): self.rate, self.gate, self.ref = rate, gate, None
    def init(self, r): self.ref = np.array([r['cb'], r['cr']], float)
    def score(self, r): return -np.hypot(r['cb'] - self.ref[0], r['cr'] - self.ref[1])
    def accept(self, s): return -s <= self.gate
    def update(self, r): self.ref += self.rate * (np.array([r['cb'], r['cr']]) - self.ref)

class GMMHS:
    """Paper: H,S pixels of the target's torso over the last N tracked frames, GMM with k by BIC (N=0: learn once)."""
    def __init__(self, n=10, kmax=6): self.n, self.kmax, self.q = n, kmax, []
    def fit(self):
        X = np.vstack(self.q); best = None
        for k in range(1, self.kmax + 1):
            g = GaussianMixture(k, covariance_type='full', random_state=0, reg_covar=1.0).fit(X)
            b = g.bic(X)
            if best is None or b < best[0]: best = (b, g)
        self.g = best[1]
        tr = [self.g.score(x) for x in self.q]; self.thr = min(tr) - 1.0  # accept a box about as likely as the training boxes
    def init(self, r): self.q = [r['hs']]; self.fit()
    def score(self, r): return self.g.score(r['hs'])
    def accept(self, s): return s >= self.thr
    def update(self, r):
        if self.n == 0: return
        self.q = (self.q + [r['hs']])[-self.n:]; self.fit()

def run(frames, target, model):
    st = dict(CT=0, CL=0, WT=0, WL=0); forced = [0, 0]; locked = False
    for fr in frames:
        tgt_here = any(r['who'] == target for r in fr)
        if not locked:
            first = [r for r in fr if r['who'] == target]
            if first: model.init(first[0]); locked = True
            continue
        scored = sorted(((model.score(r), r) for r in fr), key=lambda x: -x[0])
        best = scored[0] if scored else None
        acc = best is not None and model.accept(best[0])
        if tgt_here and any(r['who'] != target for r in fr):  # both present: does colour rank the target first?
            forced[0] += best[1]['who'] == target; forced[1] += 1
        if acc:
            st['CT' if best[1]['who'] == target else 'WT'] += 1
            model.update(best[1])
        else:
            st['WL' if tgt_here else 'CL'] += 1
    n = sum(st.values())
    return st, n, forced

for target, name in (('B', 'เสื้อฟ้า'), ('D', 'เสื้อเทาดำ')):
    for v, lf in VIDS:
        frames = load(v, lf)
        for label, mk in (('ours (Cb,Cr ref, rate 0.05)', lambda: Chroma()), ('ours, fixed ref', lambda: Chroma(rate=0.0)),
                          ('paper GMM H,S, N=10', lambda: GMMHS(10)), ('paper GMM H,S, N=0', lambda: GMMHS(0))):
            st, n, fo = run(frames, target, mk())
            print(f"target={target} {lf} {label:30s} " + ' '.join(f"{k} {100 * st[k] / n:5.1f}%" for k in ('CT', 'CL', 'WT', 'WL')) +
                  f" | both in view: target ranked first {fo[0]}/{fo[1]} ({100 * fo[0] / max(1, fo[1]):.1f}%)")
