"""Colour-only target identification on the two lab videos: our chroma reference against the paper's H,S GMM."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colour_models import *
S = sys.argv[1]

for target, name in (('B', 'เสื้อฟ้า'), ('D', 'เสื้อเทาดำ')):
    for v, lf in VIDS:
        frames = load(S, v)
        for label, mk in (('ours (Cb,Cr ref, rate 0.05)', lambda: Chroma()), ('ours, fixed ref', lambda: Chroma(rate=0.0)),
                          ('paper GMM H,S, N=10', lambda: GMMHS(10)), ('paper GMM H,S, N=0', lambda: GMMHS(0)),
                          ('H,S histogram, N=10', lambda: HistHS(10)), ('H,S histogram, N=0', lambda: HistHS(0))):
            st, n, fo = run(frames, target, mk())
            print(f"target={target} {lf} {label:30s} " + ' '.join(f"{k} {100 * st[k] / n:5.1f}%" for k in ('CT', 'CL', 'WT', 'WL')) +
                  f" | both in view: target ranked first {fo[0]}/{fo[1]} ({100 * fo[0] / max(1, fo[1]):.1f}%)")
