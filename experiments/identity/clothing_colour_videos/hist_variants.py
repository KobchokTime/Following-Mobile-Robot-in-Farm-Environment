"""H,S histogram variants on the two lab videos (fast; the GMM runs are in evalc.py)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colour_models import *
S = sys.argv[1]

V = [load(S, v) for v, _ in VIDS]
variants = [('hist N=10', dict()), ('grey bin N=10', dict(grey=True)),
            ('grey bin + anchor 0.5', dict(grey=True, anchor=0.5)),
            ('grey bin + margin 0.05', dict(grey=True, margin=0.05)),
            ('grey bin + anchor 0.5 + margin 0.05', dict(grey=True, anchor=0.5, margin=0.05)),
            ('hist + anchor 0.5 + margin 0.05', dict(anchor=0.5, margin=0.05)),
            ('grey bin N=0', dict(grey=True, n=0)),
            ('hist + self gate 0.05', dict(self_gate=0.05)), ('hist + self gate 0.1', dict(self_gate=0.1)),
            ('grey bin + self gate 0.05', dict(grey=True, self_gate=0.05)), ('grey bin + self gate 0.1', dict(grey=True, self_gate=0.1)),
            ('hist + self gate 0.1 + anchor 0.3', dict(self_gate=0.1, anchor=0.3)),
            ('hist + self gate 0.05 + anchor 0.3', dict(self_gate=0.05, anchor=0.3))]
for name, kw in variants:
    out = []
    for target in 'BD':
        for fr in V:
            f = run2(fr, target, Hist(**kw)); out.append(f"{100 * f[0] / f[1]:5.1f}")
    print(f"{name:40s} blue {out[0]} {out[1]} | dark {out[2]} {out[3]}")
