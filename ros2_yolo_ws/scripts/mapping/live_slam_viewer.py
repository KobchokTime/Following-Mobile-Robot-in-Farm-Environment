#!/usr/bin/env python3
"""Local, read-only SLAM map viewer for the PC. No ROS publisher and no motor connection.

Run on the Windows PC: ``py -3 ros2_yolo_ws/scripts/mapping/live_slam_viewer.py`` and open
http://127.0.0.1:8772/ . A ROS subscriber started over SSH streams ``/map`` and ``/scan``
from the robot (subscriptions only, plus a TF listener). The newest archived map stays
visible while SLAM is offline and is clearly labelled as an archive. Save writes a
PGM/YAML pair plus a JSON provenance sidecar on this PC only, and only while a fresh
live ``/map`` is arriving; the archive is never re-saved as if it were live.

Reviewed from Codex's local prototype (SHA-256 D3CE8FDE...2790BA, 2026-11-15) by Claude.
Changes against the prototype are listed in ``README.md`` next to this file.

Environment overrides: SLAM_VIEW_PORT, SLAM_ROBOT, SLAM_ARCHIVE_DIR, SLAM_SAVE_DIR,
SLAM_LIVE_MAX_AGE_S, SLAM_NO_SSH=1 (offline: archive only).
"""

import ast
import json
import math
import os
import re
import subprocess
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HOST = "127.0.0.1"
PORT = int(os.environ.get("SLAM_VIEW_PORT", "8772"))
ROBOT = os.environ.get("SLAM_ROBOT", "yakgreen001@192.168.1.51")
DATA_ROOT = Path.home() / "Documents" / "robot_day_data"
ARCHIVE = Path(os.environ.get("SLAM_ARCHIVE_DIR", str(DATA_ROOT / "20261115-site01" / "maps")))
# Live captures go to their own folder so they are never confused with the archive.
SAVE_DIR = Path(os.environ.get("SLAM_SAVE_DIR", str(DATA_ROOT / "slam_live_captures")))
# slam_toolbox publishes /map every map_update_interval seconds (5 s in the 2026-11-15
# params, 2 s in slam_params_mapping_only.yaml). The live window must be longer than that.
LIVE_MAX_AGE_S = float(os.environ.get("SLAM_LIVE_MAX_AGE_S", "12"))
SAVE_HEADER = "X-Slam-Viewer"  # custom header: a cross-site form post cannot set it

# Shared by the robot-side subscriber and the offline tests. Rotates (x, y, 0) by a full
# quaternion. The LiDAR frame has roll = pi (mirrored scan), so a yaw-only rotation would
# draw the scan mirrored on the map.
TF_MATH = r"""
def rot_xy(q, x, y):
    w, qx, qy, qz = q.w, q.x, q.y, q.z
    return ((1 - 2 * (qy * qy + qz * qz)) * x + 2 * (qx * qy - qz * w) * y,
            2 * (qx * qy + qz * w) * x + (1 - 2 * (qx * qx + qz * qz)) * y)

def yaw_of(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))

def project(tr, pts):
    tx, ty = tr.translation.x, tr.translation.y
    out = []
    for x, y in pts:
        a, b = rot_xy(tr.rotation, x, y)
        out.append([round(tx + a, 3), round(ty + b, 3)])
    return out
"""

REMOTE_CODE = r"""
import json, math, os, time
""" + TF_MATH + r"""
import rclpy
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, qos_profile_sensor_data
from nav_msgs.msg import OccupancyGrid
from sensor_msgs.msg import LaserScan

PARENT = os.getppid()
rclpy.init()
# Unique name: an older viewer's subscriber may still be on the graph.
node = rclpy.create_node('slam_map_viewer_read_only_%d' % os.getpid())
last_map = 0.0
last_scan = 0.0
try:
    from tf2_ros import Buffer, TransformListener
    tf_buffer = Buffer()
    tf_listener = TransformListener(tf_buffer, node)
except ImportError:
    tf_buffer = None

def stamp_s(h):
    return h.stamp.sec + h.stamp.nanosec * 1e-9

def lookup(target, source):
    if tf_buffer is None:
        return None
    try:
        return tf_buffer.lookup_transform(target, source, rclpy.time.Time()).transform
    except Exception:
        return None

def on_map(msg):
    global last_map
    now = time.monotonic()
    if now - last_map < 0.8:
        return
    last_map = now
    print(json.dumps({'kind': 'map', 'robot_time': time.time(), 'stamp': stamp_s(msg.header),
        'frame': msg.header.frame_id, 'width': msg.info.width, 'height': msg.info.height,
        'resolution': msg.info.resolution,
        'origin': [msg.info.origin.position.x, msg.info.origin.position.y,
                   yaw_of(msg.info.origin.orientation)], 'data': list(msg.data)},
        separators=(',', ':')), flush=True)

def on_scan(msg):
    global last_scan
    now = time.monotonic()
    if now - last_scan < 0.18:
        return
    last_scan = now
    pts = []
    for i, r in enumerate(msg.ranges):
        if math.isfinite(r) and msg.range_min <= r <= msg.range_max:
            a = msg.angle_min + i * msg.angle_increment
            pts.append((r * math.cos(a), r * math.sin(a)))
    frame = msg.header.frame_id
    in_map = lookup('map', frame)
    in_base = lookup('base_link', frame)
    base_in_map = lookup('map', 'base_link')
    pose = None
    if base_in_map is not None:
        pose = [base_in_map.translation.x, base_in_map.translation.y, yaw_of(base_in_map.rotation)]
    print(json.dumps({'kind': 'scan', 'robot_time': time.time(), 'stamp': stamp_s(msg.header),
        'frame': frame, 'valid': len(pts), 'beams': len(msg.ranges),
        'map_points': project(in_map, pts[::2]) if in_map is not None else None,
        'base_points': project(in_base, pts) if in_base is not None else None,
        'raw_points': None if in_base is not None else [[round(x, 3), round(y, 3)] for x, y in pts],
        'pose': pose}, separators=(',', ':')), flush=True)

def watchdog():
    # ssh -T gives no SIGHUP; exit when the SSH session that started us is gone.
    if os.getppid() != PARENT:
        os._exit(0)

map_qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                     durability=DurabilityPolicy.TRANSIENT_LOCAL)
node.create_subscription(OccupancyGrid, '/map', on_map, map_qos)
node.create_subscription(LaserScan, '/scan', on_scan, qos_profile_sensor_data)
node.create_timer(1.0, watchdog)
try:
    rclpy.spin(node)
finally:
    node.destroy_node()
    rclpy.shutdown()
"""

state = {"map": None, "map_at": None, "map_seq": 0, "scan": None, "scan_at": None,
         "source": None, "error": "กำลังเชื่อมต่อกับ ROS"}
state_lock = threading.Lock()


def archive_map(directory=None):
    """Read the most recent ROS map_saver PGM/YAML pair, without modifying it."""
    directory = Path(directory) if directory is not None else ARCHIVE
    for pgm in sorted(directory.glob("map_*.pgm"), reverse=True):
        yaml_path = pgm.with_suffix(".yaml")
        if not yaml_path.exists():
            continue
        try:
            raw = pgm.read_bytes()
            # map_saver may put a "# CREATOR: ..." comment line after the magic number.
            header = re.match(rb"P5\s+(?:#[^\n]*\n\s*)*(\d+)\s+(\d+)\s+255\s", raw)
            if not header:
                continue
            width, height = map(int, header.group(1, 2))
            pixels = raw[header.end():]
            if len(pixels) != width * height:
                continue
            yaml_text = yaml_path.read_text(encoding="utf-8")
            resolution = float(re.search(r"(?m)^resolution:\s*([\d.]+)", yaml_text).group(1))
            origin = ast.literal_eval(re.search(r"(?m)^origin:\s*(\[[^\]]+\])", yaml_text).group(1))
            # PGM rows are top-down; ROS OccupancyGrid rows are bottom-up.
            rows = [pixels[y * width:(y + 1) * width] for y in range(height)]
            data = [(-1 if p == 205 else 0 if p >= 250 else 100 if p <= 5 else
                     max(0, min(100, round((254 - p) / 2.54))))
                    for row in reversed(rows) for p in row]
            return {"kind": "map", "width": width, "height": height,
                    "resolution": resolution, "origin": list(origin), "data": data,
                    "frame": "map", "archive_name": pgm.name}
        except (OSError, ValueError, AttributeError, SyntaxError):
            continue
    return None


def accept_item(item, now=None):
    """Apply one JSON line from the robot to the shared state. Returns True if used."""
    now = time.monotonic() if now is None else now
    if not isinstance(item, dict):
        return False
    with state_lock:
        if item.get("kind") == "map" and isinstance(item.get("data"), list) and len(item["data"]) == (
                item.get("width", 0) * item.get("height", 0)) and item["data"]:
            state.update(map=item, map_at=now, map_seq=state["map_seq"] + 1, source="live", error="")
            return True
        if item.get("kind") == "scan":
            state.update(scan=item, scan_at=now, error="")
            return True
    return False


_JOB = None


def bind_child_to_viewer(proc):
    """Windows: put the ssh child in a job object that is killed when this process exits.

    Without it, a hard-killed viewer leaves ssh.exe running, and the robot-side subscriber
    stays on the ROS graph (seen 2026-11-15: two leftover read-only subscribers).
    """
    global _JOB
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        class IoCounters(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class BasicLimits(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", IoCounters),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        if _JOB is None:
            job = kernel32.CreateJobObjectW(None, None)
            info = ExtendedLimits()
            info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not job or not kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
                return False
            _JOB = job
        return bool(kernel32.AssignProcessToJobObject(_JOB, wintypes.HANDLE(int(proc._handle))))
    except Exception:
        return False


def read_ros():
    while True:
        command = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
                   "-o", "StrictHostKeyChecking=yes", "-o", "ServerAliveInterval=5",
                   "-o", "ServerAliveCountMax=2", ROBOT,
                   "bash -lc 'source /opt/ros/humble/setup.bash && exec python3 -u -'"]
        proc = None
        try:
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, bufsize=1,
                                    encoding="utf-8", errors="replace")
            bind_child_to_viewer(proc)
            proc.stdin.write(REMOTE_CODE)
            proc.stdin.close()
            for line in proc.stdout:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    with state_lock:
                        state["error"] = line.strip()[:180]
                    continue
                accept_item(item)
            code = proc.wait(timeout=3)
            with state_lock:
                state["error"] = f"SSH/ROS หยุดทำงาน (code {code})"
        except Exception as exc:
            with state_lock:
                state["error"] = f"{type(exc).__name__}: {str(exc)[:130]}"
        finally:
            if proc is not None and proc.poll() is None:
                proc.kill()
        time.sleep(3)


def map_to_pgm(map_msg):
    """Convert ROS occupancy values to map_saver-compatible trinary P5 bytes."""
    width, height = map_msg["width"], map_msg["height"]
    values = map_msg["data"]
    if width < 1 or height < 1 or len(values) != width * height:
        raise ValueError("invalid map dimensions")
    output = bytearray()
    for y in range(height - 1, -1, -1):
        for value in values[y * width:(y + 1) * width]:
            output.append(205 if value < 0 or 25 < value < 65 else 0 if value >= 65 else 254)
    return f"P5\n{width} {height}\n255\n".encode("ascii") + output


def map_stats(map_msg):
    data = map_msg["data"]
    known = sum(1 for v in data if v >= 0)
    return {"cells": len(data), "known_cells": known,
            "occupied_cells": sum(1 for v in data if v >= 65),
            "free_cells": sum(1 for v in data if 0 <= v <= 25),
            "known_share": round(known / len(data), 4) if data else 0.0}


def save_live_map(map_msg, save_dir=None, received_age_s=None):
    save_dir = Path(save_dir) if save_dir is not None else SAVE_DIR
    save_dir.mkdir(parents=True, exist_ok=True)
    stem = "live_map_" + datetime.now().strftime("%Y%m%dT%H%M%S")
    pgm, yaml, meta = (save_dir / (stem + ext) for ext in (".pgm", ".yaml", ".json"))
    if pgm.exists() or yaml.exists():
        raise FileExistsError("map name already exists; retry in one second")
    pgm.write_bytes(map_to_pgm(map_msg))
    x, y, heading = map_msg["origin"]
    yaml.write_text(f"image: {pgm.name}\nmode: trinary\nresolution: {map_msg['resolution']}\n"
                    f"origin: [{x}, {y}, {heading}]\nnegate: 0\n"
                    "occupied_thresh: 0.65\nfree_thresh: 0.25\n", encoding="utf-8")
    meta.write_text(json.dumps({
        "source": "live /map from slam_toolbox via read-only SSH subscriber",
        "robot": ROBOT.split("@")[-1], "saved_at_local": datetime.now().isoformat(timespec="seconds"),
        "map_stamp": map_msg.get("stamp"), "robot_time_at_send": map_msg.get("robot_time"),
        "received_age_s": None if received_age_s is None else round(received_age_s, 2),
        "frame": map_msg.get("frame"), "width": map_msg["width"], "height": map_msg["height"],
        "resolution": map_msg["resolution"], "origin": map_msg["origin"], **map_stats(map_msg),
        "viewer": "ros2_yolo_ws/scripts/mapping/live_slam_viewer.py"}, indent=2), encoding="utf-8")
    return {"pgm": str(pgm), "yaml": str(yaml), "json": str(meta)}


def fresh_live_map():
    """Return (map, age_s) if a live /map arrived within LIVE_MAX_AGE_S, else (None, age_s)."""
    with state_lock:
        age = None if state["map_at"] is None else time.monotonic() - state["map_at"]
        live = state["source"] == "live" and age is not None and age < LIVE_MAX_AGE_S
        return (state["map"] if live else None), age


HTML = r"""<!doctype html><html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>แผนที่ SLAM สด</title><style>
:root{font-family:system-ui,'Segoe UI',sans-serif;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:#0b1421;color:#e9f2ff}
header{padding:14px 20px;background:#152438;border-bottom:1px solid #31465e;display:flex;gap:16px;align-items:center;justify-content:space-between;flex-wrap:wrap}
h1{font-size:21px;margin:0}h2{font-size:17px;margin:0 0 8px}
#status{font-weight:700;color:#ffcf72}#status.live{color:#7beaaf}
button{background:#246344;border:1px solid #6ae5a1;border-radius:7px;padding:9px 13px;color:white;font-weight:700;cursor:pointer}
button:disabled{opacity:.4;cursor:default}
main{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:14px;padding:14px;height:calc(100vh - 78px)}
.card{background:#142337;border:1px solid #2b435b;border-radius:10px;padding:14px;min-height:0}
.mapbox{height:calc(100% - 80px);min-height:260px;background:#cdd1d4;border-radius:5px;overflow:hidden}
canvas{width:100%;height:100%;display:block}.side{display:flex;flex-direction:column;gap:14px;min-height:0}
.scanbox{height:300px;background:#091828;border-radius:5px}
.muted{color:#adc2d7;font-size:13px;line-height:1.5;word-break:break-all}
.numbers{display:grid;grid-template-columns:1fr 1fr;gap:10px}.number{background:#0c1a2a;padding:10px;border-radius:7px}
.number strong{display:block;font-size:19px}.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:13px}
.swatch{display:inline-block;width:11px;height:11px;margin-right:5px}
@media(max-width:850px){main{display:block;height:auto}.mapbox{height:55vh}.side{margin-top:14px}.scanbox{height:260px}}
</style></head><body>
<header><h1>แผนที่ SLAM · พื้นที่ที่สแกนแล้ว</h1><span id="status">กำลังเชื่อมต่อ…</span>
<button id="save" disabled>บันทึกแผนที่สด</button></header>
<main><section class="card"><h2 id="maptitle">แผนที่</h2>
<div class="mapbox"><canvas id="map"></canvas></div>
<p class="muted" id="mapnote">ภาพเดิมจะแสดงจนกว่าจะได้รับ /map สด</p></section>
<div class="side"><section class="card"><h2>ภาพ LiDAR ล่าสุด</h2><div class="scanbox"><canvas id="scan"></canvas></div>
<p class="muted" id="scannote">รอ /scan</p></section>
<section class="card"><h2>ความคืบหน้า</h2><div class="numbers">
<div class="number">พื้นที่ที่ทราบ<strong id="known">—</strong></div>
<div class="number">ขนาดแผนที่<strong id="size">—</strong></div></div>
<p class="muted" id="source">—</p><div class="legend">
<span><i class="swatch" style="background:#f8fafc"></i>สแกนว่าโล่ง</span>
<span><i class="swatch" style="background:#171c28"></i>พบสิ่งกีดขวาง</span>
<span><i class="swatch" style="background:#cdd1d4"></i>ยังไม่ทราบ</span></div>
<p class="muted" id="saveinfo"></p></section></div></main>
<script>
const LIVE_MAX=__LIVE_MAX__;
let map=null,scan=null,mapSeq=-1,source=null,mapAge=null,scanAge=null;
const mapCanvas=document.getElementById('map'),scanCanvas=document.getElementById('scan');
function canvasSize(el){const d=window.devicePixelRatio||1,w=el.clientWidth,h=el.clientHeight;
  if(el.width!==Math.round(w*d)||el.height!==Math.round(h*d)){el.width=Math.round(w*d);el.height=Math.round(h*d)}
  const c=el.getContext('2d');c.setTransform(d,0,0,d,0,0);return [c,w,h]}
function mapPoint(x,y){if(!map)return null;const [ox,oy,a]=map.origin,dx=x-ox,dy=y-oy;
  return [(Math.cos(a)*dx+Math.sin(a)*dy)/map.resolution,
    (-Math.sin(a)*dx+Math.cos(a)*dy)/map.resolution]}
function drawMap(){const [ctx,w,h]=canvasSize(mapCanvas);ctx.fillStyle='#cdd1d4';ctx.fillRect(0,0,w,h);
  if(!map)return;const raster=document.createElement('canvas');raster.width=map.width;raster.height=map.height;
  const rc=raster.getContext('2d'),img=rc.createImageData(map.width,map.height);
  for(let row=0;row<map.height;row++)for(let col=0;col<map.width;col++){
    const v=map.data[(map.height-1-row)*map.width+col],i=(row*map.width+col)*4;
    const rgb=v<0?[205,209,212]:v>=65?[23,28,40]:v<=25?[248,250,252]:[156,170,181];
    img.data.set([...rgb,255],i)}rc.putImageData(img,0,0);
  const scale=Math.min(w/map.width,h/map.height)*.94,offX=(w-map.width*scale)/2,offY=(h-map.height*scale)/2;
  ctx.imageSmoothingEnabled=false;ctx.drawImage(raster,offX,offY,map.width*scale,map.height*scale);
  if(scan&&scanAge!==null&&scanAge<2&&source==='live'){
    if(scan.map_points){ctx.fillStyle='rgba(242,86,72,.88)';
      scan.map_points.forEach(([x,y])=>{const q=mapPoint(x,y);
        if(q&&q[0]>=0&&q[0]<map.width&&q[1]>=0&&q[1]<map.height)
          ctx.fillRect(offX+q[0]*scale-1.5,offY+(map.height-q[1])*scale-1.5,3,3)})}
    if(scan.pose){const [sx,sy,sa]=scan.pose,p=mapPoint(sx,sy),px=offX+p[0]*scale,py=offY+(map.height-p[1])*scale;
      const b=-(sa-map.origin[2]);
      ctx.fillStyle='#147ad6';ctx.strokeStyle='white';ctx.lineWidth=2;
      ctx.beginPath();ctx.arc(px,py,6,0,2*Math.PI);ctx.fill();ctx.stroke();
      ctx.beginPath();ctx.moveTo(px,py);ctx.lineTo(px+Math.cos(b)*16,py+Math.sin(b)*16);ctx.stroke()}
  }
}
function drawScan(){const [ctx,w,h]=canvasSize(scanCanvas),cx=w/2,cy=h/2,px=Math.min(w,h)*.43/4;
  ctx.fillStyle='#091828';ctx.fillRect(0,0,w,h);ctx.strokeStyle='#31445d';ctx.fillStyle='#9cb4ca';ctx.font='12px system-ui';
  for(let r=1;r<=4;r++){ctx.beginPath();ctx.arc(cx,cy,r*px,0,2*Math.PI);ctx.stroke();ctx.fillText(r+' m',cx+4,cy-r*px-3)}
  const pts=scan&&scanAge!==null&&scanAge<2?(scan.base_points||scan.raw_points):null;
  if(pts)pts.forEach(([x,y])=>{const r=Math.hypot(x,y);if(r>4)return;
    ctx.fillStyle=r<.45?'#ff7676':r<1.5?'#71e6ac':'#5cafff';ctx.fillRect(cx-y*px-1.5,cy-x*px-1.5,3,3)});
  ctx.fillStyle='#5cafff';ctx.beginPath();ctx.arc(cx,cy,5,0,2*Math.PI);ctx.fill();
  ctx.fillStyle='#b8cce0';ctx.fillText(scan&&scan.base_points?'ด้านบน = หน้าหุ่น (base_link)':
    'ยังไม่มี TF · เฟรม laser ดิบ (กลับด้าน)',8,18)
}
async function poll(){try{const r=await fetch('/api/state?seq='+mapSeq,{cache:'no-store'}),d=await r.json();
    if(d.map){map=d.map;mapSeq=d.map_seq}scan=d.scan;source=d.source;mapAge=d.map_age_s;scanAge=d.scan_age_s;
    const live=source==='live'&&mapAge!==null&&mapAge<LIVE_MAX;
    const status=document.getElementById('status');status.className=live?'live':'';
    status.textContent=live?'● แผนที่สด · อัปเดตล่าสุด '+mapAge.toFixed(1)+' วินาทีก่อน':
      source==='archive'?'● ภาพเก่าที่บันทึกไว้ (ไม่ใช่ข้อมูลสด)':source==='live'?'● /map หยุดอัปเดต':'● รอแผนที่จาก ROS';
    document.getElementById('save').disabled=!live;
    document.getElementById('maptitle').textContent=live?'แผนที่กำลังสร้าง':
      source==='archive'?'แผนที่ที่บันทึกไว้':'แผนที่ล่าสุด · ข้อมูลเก่า';
    document.getElementById('mapnote').textContent=live?
      (scan?.map_points?'จุดแดง = สแกนล่าสุดบนแผนที่ · จุดฟ้า = ตำแหน่งหุ่น (ขีด = ทิศหน้า)':'รอ TF map→laser เพื่อวางสแกนลงบนแผนที่'):
      source==='archive'?'ภาพนี้เป็นไฟล์เดิม ไม่ใช่ข้อมูลสด · ปุ่มบันทึกจะใช้ได้เมื่อมี /map สด':'ข้อมูล /map หยุดอัปเดตแล้ว';
    document.getElementById('scannote').textContent=scanAge!==null&&scanAge<2&&scan?
      '/scan สด · '+scanAge.toFixed(1)+' วินาที · beam ที่ใช้ได้ '+scan.valid+'/'+scan.beams:'ยังไม่มี /scan สด';
    if(map){const known=map.data.filter(v=>v>=0).length;
      document.getElementById('known').textContent=(known/map.data.length*100).toFixed(1)+'%';
      document.getElementById('size').textContent=(map.width*map.resolution).toFixed(1)+' × '+(map.height*map.resolution).toFixed(1)+' ม.'}
    document.getElementById('source').textContent=live?'แหล่งข้อมูล: /map จากหุ่นผ่าน SSH แบบอ่านอย่างเดียว':
      source==='archive'&&map?'ไฟล์เดิม: '+map.archive_name+' · '+(d.error||''):'รอ /map ใหม่ · '+(d.error||'');
    drawMap();drawScan();
  }catch(e){document.getElementById('status').textContent='● ติดต่อเซิร์ฟเวอร์ไม่ได้'}
  setTimeout(poll,500)}
document.getElementById('save').addEventListener('click',async()=>{const b=document.getElementById('save');b.disabled=true;
  const n=document.getElementById('saveinfo');n.textContent='กำลังบันทึก…';
  try{const r=await fetch('/api/save',{method:'POST',headers:{'X-Slam-Viewer':'save'}}),d=await r.json();
    n.textContent=d.ok?'บันทึกแล้ว: '+d.pgm+' · '+d.yaml+' · '+d.json:'บันทึกไม่สำเร็จ: '+d.error}
  catch(e){n.textContent='ติดต่อเซิร์ฟเวอร์ไม่ได้'}setTimeout(()=>{b.disabled=false},1000)});
window.addEventListener('resize',()=>{drawMap();drawScan()});poll();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def host_ok(self):
        port = self.server.server_address[1]
        if self.headers.get("Host", "") in (f"127.0.0.1:{port}", f"localhost:{port}"):
            return True
        self.send_error(403, "host not allowed")
        return False

    def do_GET(self):
        if not self.host_ok():
            return
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = HTML.replace("__LIVE_MAX__", repr(LIVE_MAX_AGE_S)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/api/state":
            try:
                client_seq = int(parse_qs(parsed.query).get("seq", ["-1"])[0])
            except ValueError:
                client_seq = -1
            with state_lock:
                now = time.monotonic()
                map_age = None if state["map_at"] is None else now - state["map_at"]
                scan_age = None if state["scan_at"] is None else now - state["scan_at"]
                payload = {"map": state["map"] if client_seq != state["map_seq"] else None,
                           "map_seq": state["map_seq"], "map_age_s": map_age,
                           "scan": state["scan"] if scan_age is not None and scan_age < 2 else None,
                           "scan_age_s": scan_age, "source": state["source"],
                           "live_max_age_s": LIVE_MAX_AGE_S, "error": state["error"]}
            self.send_json(payload)
        elif parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self.send_error(404)

    def do_POST(self):
        if not self.host_ok():
            return
        if self.path != "/api/save":
            self.send_error(404)
            return
        if self.headers.get(SAVE_HEADER) != "save":
            self.send_json({"ok": False, "error": "missing viewer header"}, 403)
            return
        map_msg, age = fresh_live_map()
        if map_msg is None:
            self.send_json({"ok": False, "error": "no fresh live /map; archived image was not resaved"}, 409)
            return
        try:
            self.send_json({"ok": True, **save_live_map(map_msg, received_age_s=age)})
        except (OSError, ValueError) as exc:
            self.send_json({"ok": False, "error": str(exc)}, 500)

    def log_message(self, fmt, *args):
        if not self.path.startswith("/api/state"):
            super().log_message(fmt, *args)


def main():
    saved = archive_map()
    if saved:
        state.update(map=saved, source="archive", map_seq=1, error="รอ ROS /map สด")
    if os.environ.get("SLAM_NO_SSH") != "1":
        threading.Thread(target=read_ros, daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"SLAM viewer: http://{HOST}:{PORT}/  (archive {ARCHIVE}, saves to {SAVE_DIR})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
