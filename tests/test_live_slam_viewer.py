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


FIXTURES = ROOT / "tests" / "fixtures" / "slam"


class ArchivedMapTest(unittest.TestCase):
    """Real map_saver output from 2026-11-15 (map_20261115T115027, 126 x 120 @ 0.05 m)."""

    def setUp(self):
        self.v = load_viewer()

    def test_archive_reads_real_map_saver_output(self):
        m = self.v.archive_map(FIXTURES)
        self.assertEqual((m["width"], m["height"], m["resolution"]), (126, 120, 0.05))
        self.assertEqual(m["origin"], [-6.42, -3.11, 0])
        self.assertEqual(m["archive_name"], "map_20261115T115027.pgm")
        # 254 occupied, 2,571 free (follow_and_slam.md), rest unknown
        self.assertEqual(sum(v == 100 for v in m["data"]), 254)
        self.assertEqual(sum(v == 0 for v in m["data"]), 2571)
        self.assertEqual(sum(v == -1 for v in m["data"]), 126 * 120 - 254 - 2571)

    def test_pgm_rows_are_flipped_to_ros_bottom_up_and_back(self):
        raw = (FIXTURES / "map_20261115T115027.pgm").read_bytes()
        pixels = raw[len(raw) - 126 * 120:]
        m = self.v.archive_map(FIXTURES)
        # ROS row 0 (bottom, y = origin_y) is the LAST row of the top-down PGM
        to_occ = {205: -1, 254: 0, 0: 100}
        self.assertEqual(m["data"][:126], [to_occ[p] for p in pixels[-126:]])
        self.assertEqual(m["data"][-126:], [to_occ[p] for p in pixels[:126]])
        # Saving the archive's grid reproduces map_saver's bytes exactly
        self.assertEqual(self.v.map_to_pgm(m), raw)

    def test_pgm_header_with_creator_comment(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "map_c.pgm").write_bytes(b"P5\n# CREATOR: map_saver.cpp 0.050 m/pix\n2 1\n255\n\xfe\x00")
            (d / "map_c.yaml").write_text("resolution: 0.05\norigin: [0, 0, 0]\n", encoding="utf-8")
            self.assertEqual(self.v.archive_map(d)["data"], [0, 100])


class _Msg(SimpleNamespace):
    pass


def _stub_ros(transforms, map_msg, scan_msg):
    """Minimal rclpy / msgs / tf2_ros stand-ins so REMOTE_CODE runs offline."""
    import types
    rec = {"subs": {}, "timers": []}

    class Node:
        def __init__(self, name):
            rec["node_name"] = name

        def create_subscription(self, msg_type, topic, cb, qos):
            rec["subs"][topic] = (msg_type, cb, qos)

        def create_timer(self, period, cb):
            rec["timers"].append(period)

        def destroy_node(self):
            pass

    def spin(node):
        rec["subs"]["/map"][1](map_msg)
        rec["subs"]["/scan"][1](scan_msg)

    rclpy = types.ModuleType("rclpy")
    rclpy.init, rclpy.shutdown, rclpy.spin = (lambda: None), (lambda: None), spin
    rclpy.create_node = Node
    rclpy.time = types.SimpleNamespace(Time=lambda: 0)
    qos = types.ModuleType("rclpy.qos")
    qos.QoSProfile = lambda **kw: dict(kw)
    qos.ReliabilityPolicy = types.SimpleNamespace(RELIABLE="RELIABLE", BEST_EFFORT="BEST_EFFORT")
    qos.DurabilityPolicy = types.SimpleNamespace(TRANSIENT_LOCAL="TRANSIENT_LOCAL", VOLATILE="VOLATILE")
    qos.qos_profile_sensor_data = "SENSOR_DATA"
    nav, nav_msg = types.ModuleType("nav_msgs"), types.ModuleType("nav_msgs.msg")
    nav_msg.OccupancyGrid = "OccupancyGrid"
    sen, sen_msg = types.ModuleType("sensor_msgs"), types.ModuleType("sensor_msgs.msg")
    sen_msg.LaserScan = "LaserScan"
    tf2 = types.ModuleType("tf2_ros")

    class Buffer:
        def lookup_transform(self, target, source, when):
            if (target, source) not in transforms:
                raise LookupError(f"{target}<-{source}")
            return SimpleNamespace(transform=transforms[(target, source)])

    tf2.Buffer, tf2.TransformListener = Buffer, (lambda buf, node: None)
    modules = {"rclpy": rclpy, "rclpy.qos": qos, "nav_msgs": nav, "nav_msgs.msg": nav_msg,
               "sensor_msgs": sen, "sensor_msgs.msg": sen_msg, "tf2_ros": tf2}
    return modules, rec


def _tr(x, y, z, roll, yaw):
    return SimpleNamespace(translation=SimpleNamespace(x=x, y=y, z=z), rotation=_q_yaw_roll(roll, yaw))


class RemoteSubscriberTest(unittest.TestCase):
    """Runs the robot-side REMOTE_CODE against stubs: QoS, JSON output, TF placement."""

    def run_remote(self, transforms):
        import contextlib
        import io
        import sys
        from unittest import mock
        header = _Msg(frame_id="map", stamp=_Msg(sec=100, nanosec=500_000_000))
        map_msg = _Msg(header=header, data=[-1, 0, 100, 0], info=_Msg(
            width=2, height=2, resolution=0.05,
            origin=_Msg(position=_Msg(x=-1.0, y=-2.0), orientation=_Msg(w=1.0, x=0.0, y=0.0, z=0.0))))
        # beam 0 at raw +30 deg, 2 m; beam 1 out of range (dropped); beam 2 at raw -30 deg, 1 m
        a0 = math.radians(30.0)
        scan_msg = _Msg(header=_Msg(frame_id="laser", stamp=_Msg(sec=101, nanosec=0)),
                        angle_min=a0, angle_increment=-a0, range_min=0.1, range_max=12.0,
                        ranges=[2.0, float("inf"), 1.0])
        modules, rec = _stub_ros(transforms, map_msg, scan_msg)
        out = io.StringIO()
        with mock.patch.dict(sys.modules, modules), contextlib.redirect_stdout(out):
            exec(load_viewer().REMOTE_CODE, {"__name__": "remote"})
        lines = [json.loads(line) for line in out.getvalue().splitlines()]
        return rec, {item["kind"]: item for item in lines}

    def mounted(self):
        mount = _tr(0.0, 0.0, 0.715, math.pi, 0.10821)        # base_link <- laser
        robot = _tr(1.0, 2.0, 0.0, 0.0, math.pi / 2)          # map <- base_link
        # map <- laser = robot * mount (2D part): yaw adds, roll stays pi
        in_map = _tr(1.0, 2.0, 0.715, math.pi, math.pi / 2 + 0.10821)
        return {("base_link", "laser"): mount, ("map", "base_link"): robot, ("map", "laser"): in_map}

    def test_map_subscription_is_reliable_transient_local(self):
        rec, _ = self.run_remote(self.mounted())
        msg_type, _, qos = rec["subs"]["/map"]
        self.assertEqual(msg_type, "OccupancyGrid")
        self.assertEqual(qos["durability"], "TRANSIENT_LOCAL")   # gets slam_toolbox's latched map
        self.assertEqual(qos["reliability"], "RELIABLE")
        self.assertEqual(qos["depth"], 1)
        self.assertEqual(rec["subs"]["/scan"][2], "SENSOR_DATA")
        self.assertEqual(set(rec["subs"]), {"/map", "/scan"})
        self.assertTrue(rec["node_name"].startswith("slam_map_viewer_read_only_"))

    def test_map_json_matches_message(self):
        _, items = self.run_remote(self.mounted())
        m = items["map"]
        self.assertEqual((m["width"], m["height"], m["data"]), (2, 2, [-1, 0, 100, 0]))
        self.assertEqual(m["origin"], [-1.0, -2.0, 0.0])
        self.assertAlmostEqual(m["stamp"], 100.5)

    def test_scan_is_placed_through_full_tf(self):
        _, items = self.run_remote(self.mounted())
        s = items["scan"]
        self.assertEqual((s["valid"], s["beams"]), (2, 3))
        self.assertIsNone(s["raw_points"])
        # base_link: bearing = -raw + 6.2 deg
        bearings = [math.degrees(math.atan2(y, x)) for x, y in s["base_points"]]
        self.assertAlmostEqual(bearings[0], -30.0 + 6.2, places=1)
        self.assertAlmostEqual(bearings[1], 30.0 + 6.2, places=1)
        # map: robot at (1, 2) facing +y; a point at bearing b, range r is at (1 - r sin b, 2 + r cos b)
        b = math.radians(-30.0 + 6.2)
        x, y = s["map_points"][0]  # map_points keeps every 2nd beam -> beam 0
        self.assertAlmostEqual(x, 1.0 - 2.0 * math.sin(b), places=2)
        self.assertAlmostEqual(y, 2.0 + 2.0 * math.cos(b), places=2)
        self.assertEqual(s["pose"][:2], [1.0, 2.0])
        self.assertAlmostEqual(s["pose"][2], math.pi / 2)

    def test_scan_without_tf_is_sent_raw_and_unplaced(self):
        _, items = self.run_remote({})
        s = items["scan"]
        self.assertIsNone(s["map_points"])
        self.assertIsNone(s["base_points"])
        self.assertIsNone(s["pose"])
        self.assertEqual(len(s["raw_points"]), 2)


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
