"""Offline tests for ros2_yolo_ws/scripts/mapping/live_slam_viewer.py (no ROS, no SSH)."""

import importlib.util
import json
import math
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "ros2_yolo_ws" / "scripts" / "mapping" / "live_slam_viewer.py"


def load_viewer():
    spec = importlib.util.spec_from_file_location("live_slam_viewer_under_test", VIEWER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _q_yaw_roll(roll, yaw):
    # q = q_yaw * q_roll (static_transform_publisher RPY with pitch 0)
    cr, sr, cy, sy = math.cos(roll / 2), math.sin(roll / 2), math.cos(yaw / 2), math.sin(yaw / 2)
    return SimpleNamespace(w=cy * cr, x=cy * sr, y=sy * sr, z=sy * cr)


class TfMathTest(unittest.TestCase):
    def setUp(self):
        self.ns = {"math": math}
        exec(load_viewer().TF_MATH, self.ns)

    def test_mount_mirror_gives_bearing_minus_raw_plus_offset(self):
        q = _q_yaw_roll(math.pi, 0.10821)
        for raw_deg in (-60.0, 0.0, 30.0, 90.0):
            a = math.radians(raw_deg)
            x, y = self.ns["rot_xy"](q, math.cos(a), math.sin(a))
            bearing = math.degrees(math.atan2(y, x))
            self.assertAlmostEqual(bearing, -raw_deg + 6.2, places=1)

    def test_yaw_only_quaternion_is_plain_rotation(self):
        q = _q_yaw_roll(0.0, math.pi / 2)
        x, y = self.ns["rot_xy"](q, 1.0, 0.0)
        self.assertAlmostEqual(x, 0.0)
        self.assertAlmostEqual(y, 1.0)
        self.assertAlmostEqual(self.ns["yaw_of"](q), math.pi / 2)

    def test_project_adds_translation(self):
        tr = SimpleNamespace(translation=SimpleNamespace(x=1.0, y=2.0), rotation=_q_yaw_roll(0.0, 0.0))
        self.assertEqual(self.ns["project"](tr, [(0.5, -0.5)]), [[1.5, 1.5]])

    def test_remote_code_compiles_and_only_subscribes(self):
        code = load_viewer().REMOTE_CODE
        compile(code, "remote", "exec")
        self.assertNotIn("create_publisher", code)
        self.assertNotIn("cmd_vel", code)


class MapFileTest(unittest.TestCase):
    def setUp(self):
        self.v = load_viewer()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def live_map(self):
        # 3 x 2, bottom row first (ROS order): unknown, free, occupied / free, 50 (unknown), 100
        return {"kind": "map", "width": 3, "height": 2, "resolution": 0.05,
                "origin": [-1.0, -2.0, 0.0], "data": [-1, 0, 100, 10, 50, 90],
                "frame": "map", "stamp": 123.5}

    def test_pgm_is_top_down_trinary(self):
        pgm = self.v.map_to_pgm(self.live_map())
        self.assertTrue(pgm.startswith(b"P5\n3 2\n255\n"))
        self.assertEqual(list(pgm[-6:]), [254, 205, 0, 205, 254, 0])

    def test_save_then_archive_round_trip(self):
        out = self.v.save_live_map(self.live_map(), save_dir=self.dir, received_age_s=1.234)
        meta = json.loads(Path(out["json"]).read_text(encoding="utf-8"))
        self.assertEqual(meta["known_cells"], 5)
        self.assertEqual(meta["received_age_s"], 1.23)
        self.assertIn("live /map", meta["source"])
        # rename to the archive pattern and read it back
        stem = self.dir / "map_test"
        Path(out["pgm"]).rename(stem.with_suffix(".pgm"))
        Path(out["yaml"]).rename(stem.with_suffix(".yaml"))
        back = self.v.archive_map(self.dir)
        self.assertEqual(back["data"], [-1, 0, 100, 0, -1, 100])
        self.assertEqual(back["origin"], [-1.0, -2.0, 0.0])

    def test_live_captures_are_not_read_as_archive(self):
        self.v.save_live_map(self.live_map(), save_dir=self.dir)
        self.assertIsNone(self.v.archive_map(self.dir))


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.v = load_viewer()
        self.tmp = tempfile.TemporaryDirectory()
        self.v.SAVE_DIR = Path(self.tmp.name)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.v.Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def post(self, headers=None, host=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/save", data=b"", method="POST",
                                     headers=dict(headers or {}))
        if host:
            req.add_header("Host", host)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            body = err.read()
            return err.code, (json.loads(body) if body.startswith(b"{") else None)

    def test_archive_is_never_saved(self):
        self.v.state.update(map={"width": 1, "height": 1, "data": [0], "resolution": 0.05,
                                 "origin": [0, 0, 0]}, map_at=None, source="archive")
        code, body = self.post({"X-Slam-Viewer": "save"})
        self.assertEqual(code, 409)
        self.assertFalse(body["ok"])

    def test_fresh_live_map_saves_and_stale_does_not(self):
        item = {"kind": "map", "width": 2, "height": 1, "resolution": 0.05,
                "origin": [0, 0, 0], "data": [0, 100], "frame": "map"}
        self.assertTrue(self.v.accept_item(item))
        code, body = self.post({"X-Slam-Viewer": "save"})
        self.assertEqual(code, 200, body)
        self.assertTrue(Path(body["pgm"]).exists())
        # older than the live window (map_update_interval 5 s must still count as live)
        self.assertGreater(self.v.LIVE_MAX_AGE_S, 5.0)
        with self.v.state_lock:
            self.v.state["map_at"] = time.monotonic() - self.v.LIVE_MAX_AGE_S - 1
        code, _ = self.post({"X-Slam-Viewer": "save"})
        self.assertEqual(code, 409)

    def test_save_needs_viewer_header_and_local_host(self):
        self.v.accept_item({"kind": "map", "width": 1, "height": 1, "resolution": 0.05,
                            "origin": [0, 0, 0], "data": [0]})
        self.assertEqual(self.post()[0], 403)
        self.assertEqual(self.post({"X-Slam-Viewer": "save"}, host="evil.example:80")[0], 403)

    def test_malformed_map_is_ignored(self):
        self.assertFalse(self.v.accept_item({"kind": "map", "width": 2, "height": 2, "data": [0]}))


if __name__ == "__main__":
    unittest.main()
