"""Held-out check of the robot's TargetGate colour models on five more clips (one person each).

Settings are frozen as committed (hist_sigma 0.2, window 10, learn slack 0.1), chosen on the two lab
videos only. Usage: heldout.py LAB_DIR NEW_DIR
  A. Stability: does the gate keep accepting the clip's own person through sun, shade and turns?
  B. Strangers: each frame also shows a box of a different person from another clip (cycled in
     order), as if two people were in view. Does the gate still rank its own person first?
Colour only, as in gate_replay.py: every box gets the gate's predicted bearing and range.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colour_models import load, hs_hist
from gate_replay import sf

LAB, NEW = sys.argv[1], sys.argv[2]
CLIPS = {  # clip: (data dir, label of its person, who it is)
    "park_black_1": (NEW, "WIN_20241126_14_23_33_Pro", "T", "black tee"),
    "park_black_2": (NEW, "WIN_20241126_14_24_34_Pro", "T", "black tee"),
    "park_pattern": (NEW, "WIN_20241126_14_26_37_Pro", "T", "patterned shirt"),
    "farm_beige_1": (NEW, "WIN_20241210_13_47_33_Pro", "T", "beige tee"),
    "farm_beige_2": (NEW, "WIN_20241210_13_51_31_Pro", "T", "beige tee"),
    "lab_blue": (LAB, "WIN_20250408_14_00_41_Pro", "B", "blue top"),
    "lab_grey": (LAB, "WIN_20250408_14_00_41_Pro", "D", "dark grey top"),
}


def frames_of(name):
    d, v, who, _ = CLIPS[name]
    out = []
    for fr in load(d, v):
        fr = [dict(r, who=('T' if r['who'] == who else ('O' if r['who'] in 'OBD' else 'X'))) for r in fr]
        out.append([r for r in fr if r['who'] != 'X'])
    return out


def replay(frames, use_hist):
    g = sf.TargetGate(); st = dict(CT=0, CL=0, WT=0, WL=0); ranked = [0, 0]; t = 0.0
    feats = lambda r: ((r['cb'], r['cr']), [float(x) for x in hs_hist(r['hs'])] if use_hist else None)
    for fr in frames:
        t += 0.1
        here = any(r['who'] == 'T' for r in fr)
        if not g.locked:
            first = [r for r in fr if r['who'] == 'T']
            if first:
                g.accept(t, 0.0, 0.8, *feats(first[0]))
            continue
        pb, pr = g._predict(t)
        order = sorted(fr, key=lambda r: g.cost(t, pb, pr, *feats(r)))
        if here and any(r['who'] != 'T' for r in fr):
            ranked[0] += order[0]['who'] == 'T'; ranked[1] += 1
        took = next((r for r in order if g.accept(t, pb, pr, *feats(r))), None)
        st[('CT' if took['who'] == 'T' else 'WT') if took else ('WL' if here else 'CL')] += 1
    return st, ranked


def pct(a, b):
    return f"{100 * a / b:5.1f}%" if b else "   - "


if __name__ == "__main__":
    data = {n: frames_of(n) for n in CLIPS}
    print("A. stability: share of the person's frames the gate accepts (CT / (CT + WL))")
    for n in CLIPS:
        if n.startswith("lab"): continue
        row = []
        for h in (False, True):
            st, rk = replay(data[n], h)
            row.append(pct(st['CT'], st['CT'] + st['WL']) + (f" (real other person ranked below: {pct(*rk)})" if rk[1] else ""))
        print(f"  {n:13s} Cb,Cr {row[0]} | Cb,Cr + H,S hist {row[1]}")
    print("B. strangers: own person ranked first / stranger taken (WT share of frames)")
    tot = {False: [0, 0], True: [0, 0]}
    for a in CLIPS:
        if a.startswith("lab"): continue
        for b in CLIPS:
            if CLIPS[a][3] == CLIPS[b][3]: continue  # same person
            pool = [r for fr in data[b] for r in fr if r['who'] == 'T']
            mixed, k = [], 0
            for fr in data[a]:
                s = dict(pool[k % len(pool)], who='O'); k += 1
                mixed.append(fr + [s])
            out = []
            for h in (False, True):
                st, rk = replay(mixed, h); n = sum(st.values())
                tot[h][0] += rk[0]; tot[h][1] += rk[1]
                out.append(f"{pct(*rk)} / {pct(st['WT'], n)}")
            print(f"  {a:13s} vs {b:13s} Cb,Cr {out[0]} | Cb,Cr + H,S hist {out[1]}")
    print("  all pairs ranked first: Cb,Cr", pct(*tot[False]), "| Cb,Cr + H,S hist", pct(*tot[True]))
