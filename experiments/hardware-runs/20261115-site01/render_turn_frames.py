"""Render camera frames from a follow run with YOLO boxes, sector grid, target bearing and turn command.

    python render_turn_frames.py RUN_DIR OUT_PNG --times 0.9 1.5 5.6 8.6 12.0 16.5

For each requested time (s from bag start) the /yolo_frame nearest to it is taken, the camera image with
the same capture stamp is decoded, and drawn on it:
  - the 9 camera sectors follow_stop uses in steer_mode=sector, centre band 3-5 shaded green
  - every YOLO person box, and the fused target's column (from /synced_target cx) in red
  - bearing of the target (pinhole, HFOV 70, left +), fused range, and the /cmd_vel at that moment
"""

import argparse
import io
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore

W, H, HFOV = 640, 480, 70.0


def bearing_deg(cx):
    f = (W / 2) / math.tan(math.radians(HFOV / 2))
    return math.degrees(math.atan2(W / 2 - cx, f))


def nearest(rows, t):
    return min(rows, key=lambda r: abs(r[0] - t)) if rows else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--times", type=float, nargs="+", required=True)
    a = ap.parse_args()
    ts = get_typestore(Stores.ROS2_HUMBLE)
    images, frames, synced, cmds = {}, [], [], []
    with AnyReader([a.run_dir / "recording"], default_typestore=ts) as r:
        conns = [c for c in r.connections if c.topic in
                 ("/image_raw/compressed", "/yolo_frame", "/synced_target", "/cmd_vel")]
        t0 = None
        for c, t, raw in r.messages(connections=conns):
            t0 = t0 or t
            s = (t - t0) * 1e-9
            m = r.deserialize(raw, c.msgtype)
            if c.topic == "/image_raw/compressed":
                images[(m.header.stamp.sec, m.header.stamp.nanosec)] = bytes(m.data)
            elif c.topic == "/yolo_frame":
                d = m.data.tolist()
                boxes = [d[5 + 7 * i: 12 + 7 * i] for i in range(d[4])]
                frames.append((s, (d[0], d[1]), boxes))
            elif c.topic == "/synced_target":
                synced.append((s, float(m.data[0]), float(m.data[2])))
            else:
                cmds.append((s, m.linear.x, m.angular.z))

    font = ImageFont.load_default()
    tiles = []
    for want in a.times:
        f = nearest(frames, want)
        jpg = images.get(f[1])
        if jpg is None:  # fall back to the closest image stamp
            key = min(images, key=lambda k: abs((k[0] + k[1] * 1e-9) - (f[1][0] + f[1][1] * 1e-9)))
            jpg = images[key]
        img = Image.open(io.BytesIO(jpg)).convert("RGB").resize((W, H))
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        sw = W / 9
        d.rectangle([3 * sw, 0, 6 * sw, H], fill=(0, 200, 0, 40))
        for k in range(1, 9):
            d.line([k * sw, 0, k * sw, H], fill=(255, 255, 255, 110), width=1)
        for k in range(9):
            d.text((k * sw + 4, 4), f"S{k}", fill=(255, 255, 255, 230), font=font)
        d.line([W / 2, 0, W / 2, H], fill=(255, 255, 0, 160), width=1)
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
        d = ImageDraw.Draw(img)
        for x1, y1, x2, y2, conf, _, _ in f[2]:
            d.rectangle([x1, y1, x2, y2], outline=(0, 255, 0), width=3)
            d.text((x1 + 3, y1 + 3), f"person {conf / 1000:.2f}", fill=(0, 255, 0), font=font)
        st = nearest([x for x in synced if abs(x[0] - f[0]) <= 0.35], f[0])
        cv = nearest(cmds, f[0])
        lines = [f"t = {f[0]:.1f} s   YOLO boxes: {len(f[2])}"]
        if st:
            cx = st[1]
            d.line([cx, 0, cx, H], fill=(255, 40, 40), width=3)
            sec = min(8, int(cx * 9 / W))
            lines.append(f"target cx={cx:.0f}px  sector S{sec}  bearing {bearing_deg(cx):+.1f} deg  range {st[2]:.2f} m")
        else:
            lines.append("no fused target within 0.35 s")
        if cv:
            turn = "LEFT" if cv[2] > 0.05 else "RIGHT" if cv[2] < -0.05 else "none"
            lines.append(f"cmd_vel: forward {cv[1]:+.2f} m/s   turn {cv[2]:+.2f} rad/s ({turn})")
        d.rectangle([0, H - 16 * len(lines) - 8, W, H], fill=(0, 0, 0))
        for i, s in enumerate(lines):
            d.text((6, H - 16 * len(lines) - 4 + 16 * i), s, fill=(255, 255, 255), font=font)
        tiles.append(img)

    cols = 2
    rows = math.ceil(len(tiles) / cols)
    sheet = Image.new("RGB", (cols * W, rows * H), (20, 20, 20))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * W, (i // cols) * H))
    sheet.save(a.out)
    print(f"saved {a.out} ({len(tiles)} frames)")


if __name__ == "__main__":
    main()
