"""Run the project's YOLOv8n OpenVINO model on a video and record each person box with its torso colour.

Usage: detect.py VIDEO MODEL_XML OUT_DIR STEP  (STEP 6 = 10 fps from the 60 fps videos)
Writes OUT_DIR/detections_<video>.json, OUT_DIR/hs_pixels_<video>.json.gz and, for labelling,
OUT_DIR/crops_<video>/<id>.jpg.
"""
import sys, os, gzip, json, numpy as np, cv2, openvino as ov

def torso_roi(frame, x1, y1, x2, y2):
    # same region as ros2_yolo_live.torso_chroma
    h, w = y2 - y1, x2 - x1
    return frame[max(0, y1 + int(0.20 * h)):max(0, y1 + int(0.55 * h)), max(0, x1 + w // 4):max(0, x2 - w // 4)]

def torso_chroma(roi):
    # copied from ros2_yolo_ws/scripts/ros2_yolo_live.py
    if roi.size == 0:
        return 128, 128
    b, g, r = (roi[..., i].astype(np.float32) for i in range(3))
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cb = np.clip((b - y) * 0.564 + 128.0, 0, 255)
    cr = np.clip((r - y) * 0.713 + 128.0, 0, 255)
    return int(round(float(np.median(cb)))), int(round(float(np.median(cr))))

video, model_xml, out, step = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
core = ov.Core(); net = core.compile_model(model_xml, 'CPU')
cap = cv2.VideoCapture(video); fps = cap.get(cv2.CAP_PROP_FPS)
rows, hs = [], {}
name = os.path.splitext(os.path.basename(video))[0]
os.makedirs(f"{out}/crops_{name}", exist_ok=True)
i = -1
while True:
    ok, frame = cap.read()
    if not ok: break
    i += 1
    if i % step: continue
    H, W = frame.shape[:2]
    s = 640 / max(H, W); nh, nw = int(H * s), int(W * s)
    img = np.full((640, 640, 3), 114, np.uint8); img[:nh, :nw] = cv2.resize(frame, (nw, nh))
    x = img[..., ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    pred = net(x)[0][0]  # 84 x 8400
    conf = pred[4]; keep = conf > 0.5
    boxes = pred[:4, keep].T; confs = conf[keep]
    xyxy = np.stack([boxes[:, 0] - boxes[:, 2] / 2, boxes[:, 1] - boxes[:, 3] / 2, boxes[:, 0] + boxes[:, 2] / 2, boxes[:, 1] + boxes[:, 3] / 2], 1) / s
    idx = cv2.dnn.NMSBoxes([[float(a), float(b), float(c - a), float(d - b)] for a, b, c, d in xyxy], confs.tolist(), 0.5, 0.45)
    for k in np.array(idx).flatten():
        x1, y1, x2, y2 = [int(v) for v in np.clip(xyxy[k], 0, [W, H, W, H])]
        roi = torso_roi(frame, x1, y1, x2, y2)
        cb, cr = torso_chroma(roi)
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV) if roi.size else np.zeros((0, 0, 3), np.uint8)
        n = len(rows)
        if roi.size:
            px = hsv.reshape(-1, 3); px = px[np.random.default_rng(n).choice(len(px), min(300, len(px)), replace=False)]
            hs[n] = px[:, :2].tolist()
            cv2.imwrite(f"{out}/crops_{name}/{n:05d}.jpg", cv2.resize(frame[y1:y2, x1:x2], (64, 128)))
        rows.append(dict(id=n, frame=i, t=round(i / fps, 3), x1=x1, y1=y1, x2=x2, y2=y2, conf=round(float(confs[k]), 3), cb=cb, cr=cr,
                         y_med=float(np.median(0.299 * roi[..., 2] + 0.587 * roi[..., 1] + 0.114 * roi[..., 0])) if roi.size else None))
json.dump(dict(fps=fps, width=W, height=H, rows=rows), open(f"{out}/detections_{name}.json", "w"))
json.dump(hs, gzip.open(f"{out}/hs_pixels_{name}.json.gz", "wt"))
print(video, 'frames', i + 1, 'boxes', len(rows))
