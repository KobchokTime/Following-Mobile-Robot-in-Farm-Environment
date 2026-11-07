"""Colour models and replay for the lab-video experiments (imported by evalc.py and hist_variants.py)."""
import sys, gzip, json, numpy as np, warnings
from sklearn.mixture import GaussianMixture
warnings.filterwarnings('ignore')
VIDS = (("WIN_20250408_14_00_41_Pro", "14_00_41"), ("WIN_20250408_14_10_21_Pro", "14_10_21"))

def load(S, v):
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

def hs_hist(px, hb=12, sb=4):
    """Normalised H,S histogram of torso pixels (OpenCV H 0-179, S 0-255): the camera node can send it as hb*sb numbers."""
    h, _, _ = np.histogram2d(px[:, 0], px[:, 1], bins=(hb, sb), range=((0, 180), (0, 256)))
    h = h.ravel(); return h / max(1.0, h.sum())

class HistHS:
    """Light stand-in for the paper's model: mean H,S histogram of the target's last N picked boxes, Bhattacharyya score."""
    def __init__(self, n=10, accept=0.5): self.n, self.acc, self.q = n, accept, []
    def init(self, r): self.q = [hs_hist(r['hs'])]
    def score(self, r): return float(np.sum(np.sqrt(hs_hist(r['hs']) * np.mean(self.q, axis=0))))
    def accept(self, s): return s >= self.acc
    def update(self, r):
        if self.n: self.q = (self.q + [hs_hist(r['hs'])])[-self.n:]

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


def hs_hist2(px, hb=12, sb=3, s_min=40):
    """Hue bins only where saturation is high enough for hue to mean something; one grey bin for the rest."""
    chrom = px[:, 1] >= s_min
    h, _, _ = np.histogram2d(px[chrom, 0], px[chrom, 1], bins=(hb, sb), range=((0, 180), (s_min, 256)))
    v = np.append(h.ravel(), np.sum(~chrom)); return v / max(1.0, v.sum())

class Hist:
    def __init__(self, n=10, grey=False, anchor=0.0, upd=0.0, margin=0.0, self_gate=None):
        self.n, self.f, self.anchor, self.upd, self.margin = n, (hs_hist2 if grey else hs_hist), anchor, upd, margin
        self.self_gate = self_gate  # learn only from a box about as similar as the boxes already learned (as the GMM threshold does)
    def model(self):
        m = np.mean(self.q, axis=0); return self.anchor * self.a + (1 - self.anchor) * m
    def init(self, r): self.a = self.f(r['hs']); self.q = [self.a]
    def score(self, r): return float(np.sum(np.sqrt(self.f(r['hs']) * self.model())))
    def accept(self, s): return s >= 0.5
    def update(self, r, second=None):
        s = self.score(r)
        if s < self.upd or (second is not None and s - second < self.margin): return
        if self.self_gate is not None:
            m = self.model()
            if s < min(float(np.sum(np.sqrt(h * m))) for h in self.q) - self.self_gate: return
        if self.n: self.q = (self.q + [self.f(r['hs'])])[-self.n:]

def run2(frames, target, model):
    st = dict(CT=0, CL=0, WT=0, WL=0); forced = [0, 0]; locked = False
    for fr in frames:
        tgt = any(r['who'] == target for r in fr)
        if not locked:
            first = [r for r in fr if r['who'] == target]
            if first: model.init(first[0]); locked = True
            continue
        sc = sorted(((model.score(r), r) for r in fr), key=lambda x: -x[0])
        if tgt and any(r['who'] != target for r in fr):
            forced[0] += sc[0][1]['who'] == target; forced[1] += 1
        if sc and model.accept(sc[0][0]):
            st['CT' if sc[0][1]['who'] == target else 'WT'] += 1
            model.update(sc[0][1], sc[1][0] if len(sc) > 1 else None)
        else:
            st['WL' if tgt else 'CL'] += 1
    return forced

