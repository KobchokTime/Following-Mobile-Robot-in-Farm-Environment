import sys, gzip, json, numpy as np
S = sys.argv[1]
for v, lf in (("WIN_20250408_14_00_41_Pro", "14_00_41"), ("WIN_20250408_14_10_21_Pro", "14_10_21")):
    rows = json.load(open(f"{S}/detections_{v}.json"))['rows']; L = json.load(open(f"{S}/labels_{v}.json"))
    for r in rows: r['who'] = L[str(r['id'])]
    B = np.array([[r['cb'], r['cr']] for r in rows if r['who'] == 'B']); D = np.array([[r['cb'], r['cr']] for r in rows if r['who'] == 'D'])
    print(v)
    print('  blue  Cb,Cr median', np.median(B, 0), 'p10-p90 Cb', np.percentile(B[:, 0], [10, 90]), 'Cr', np.percentile(B[:, 1], [10, 90]))
    print('  dark  Cb,Cr median', np.median(D, 0), 'p10-p90 Cb', np.percentile(D[:, 0], [10, 90]), 'Cr', np.percentile(D[:, 1], [10, 90]))
    # how often is a blue box closer (in Cb,Cr) to the dark median than to its own, and vice versa
    mb, md = np.median(B, 0), np.median(D, 0)
    bw = np.mean(np.linalg.norm(B - md, axis=1) < np.linalg.norm(B - mb, axis=1)); dw = np.mean(np.linalg.norm(D - mb, axis=1) < np.linalg.norm(D - md, axis=1))
    print(f'  nearest-median errors: blue {bw:.1%}, dark {dw:.1%}; median gap {np.linalg.norm(mb - md):.1f}')
    # outliers to spot-check
    print('  blue with Cb<133:', [r['id'] for r in rows if r['who'] == 'B' and r['cb'] < 133][:40])
    print('  dark with Cb>142:', [r['id'] for r in rows if r['who'] == 'D' and r['cb'] > 142][:40])
