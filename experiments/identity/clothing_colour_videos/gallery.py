"""Example crops for every test video, from the original frames, with the measured torso Cb/Cr.

Usage: gallery.py SCRATCH_DIR REPO_DIR (videos in SCRATCH_DIR/videos, written to SCRATCH_DIR/gallery).
"""
import sys, json, cv2, numpy as np
S, R = sys.argv[1], sys.argv[2]
D = f"{R}/experiments/identity/clothing_colour_videos"
CLIPS = [  # (video file, label key -> row title)
    ("WIN_20250408_14_00_41_Pro", {"B": "blue top", "D": "dark grey top"}),
    ("WIN_20250408_14_10_21_Pro", {"B": "blue top", "D": "dark grey top"}),
    ("WIN_20241126_14_23_33_Pro", {"T": "black tee"}),
    ("WIN_20241126_14_24_34_Pro", {"T": "black tee"}),
    ("WIN_20241126_14_26_37_Pro", {"T": "patterned shirt"}),
    ("WIN_20241210_13_47_33_Pro", {"T": "beige tee", "O": "worker (other person)"}),
    ("WIN_20241210_13_51_31_Pro", {"T": "beige tee"}),
]
N = 8
for v, who in CLIPS:
    rows = json.load(open(f"{D}/detections_{v}.json"))['rows']; L = json.load(open(f"{D}/labels_{v}.json"))
    cap = cv2.VideoCapture(f"{S}/videos/{v}.mp4")
    lines = []
    for k in who:
        rs = [r for r in rows if L[str(r['id'])] == k and r['y2'] - r['y1'] > 120]
        if not rs: continue
        pick = [rs[int(i * (len(rs) - 1) / (N - 1))] for i in range(min(N, len(rs)))]
        tiles = []
        for r in pick:
            cap.set(cv2.CAP_PROP_POS_FRAMES, r['frame']); ok, fr = cap.read()
            im = fr[max(0, r['y1']):r['y2'], max(0, r['x1']):r['x2']]
            h, w = im.shape[:2]; s = 220 / h
            im = cv2.resize(im, (max(1, int(w * s)), 220), interpolation=cv2.INTER_AREA)
            im = im[:, max(0, (im.shape[1] - 110) // 2):][:, :110]
            if im.shape[1] < 110: im = cv2.copyMakeBorder(im, 0, 0, 0, 110 - im.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255))
            im = cv2.copyMakeBorder(im, 0, 34, 3, 3, cv2.BORDER_CONSTANT, value=(255, 255, 255))
            cv2.putText(im, f"Cb {r['cb']} Cr {r['cr']}", (5, 236), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (40, 40, 40), 1)
            cv2.putText(im, f"t = {r['t']:.0f} s", (5, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (110, 110, 110), 1)
            tiles.append(im)
        while len(tiles) < N: tiles.append(np.full_like(tiles[0], 255))
        lines.append(np.hstack(tiles))
    img = np.vstack([np.vstack([l, np.full((6, l.shape[1], 3), 255, np.uint8)]) for l in lines])
    cv2.imwrite(f"{S}/gallery/{v}.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88]); print(v, img.shape)
