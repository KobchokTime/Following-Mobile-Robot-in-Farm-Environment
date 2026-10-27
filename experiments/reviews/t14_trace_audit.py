"""Audit the T14 response's debug patch, traces and production-median regression.

Uses NumPy only to execute the actual sectorizer callback. No ROS or hardware is started.
The debug patch is applied to a temporary copy, never to the working robot source.
"""
import argparse
import ast
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

from t14_gate_review import ROOT, M, HIST, CHROMA, D, evidence_inventory
sys.path.insert(0, str(ROOT))
import test_sector_association as helper
from sim.arena.score_entry_v3 import passes

REL = "ros2_yolo_ws/scripts/Image/sync_fusion_node.py"
DEBUG = ROOT / "experiments/sim/box_range_debug"


class WithoutDocstrings(ast.NodeTransformer):
    def visit_Module(self, node):
        return self.clean(node)

    visit_ClassDef = visit_FunctionDef = visit_AsyncFunctionDef = visit_Module

    def clean(self, node):
        self.generic_visit(node)
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) \
                and isinstance(node.body[0].value.value, str):
            node.body.pop(0)
        return node


class RemoveBoxFeature(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        return None if node.name == "box_range" else self.generic_visit(node)

    def visit_Expr(self, node):
        v = node.value
        if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and v.func.attr == "declare_parameter" \
                and v.args and isinstance(v.args[0], ast.Constant) and v.args[0].value == "box_range_from_scan":
            return None
        return self.generic_visit(node)

    def visit_Assign(self, node):
        if any(isinstance(t, ast.Attribute) and t.attr == "box_range_from_scan" for t in node.targets):
            return None
        return self.generic_visit(node)

    def visit_If(self, node):
        if isinstance(node.test, ast.BoolOp) and isinstance(node.test.values[0], ast.Attribute) \
                and node.test.values[0].attr == "box_range_from_scan":
            return None
        return self.generic_visit(node)


def dump_ast(text, remove_feature=False):
    tree = ast.parse(text)
    if remove_feature:
        tree = RemoveBoxFeature().visit(tree)
    return ast.dump(WithoutDocstrings().visit(tree), include_attributes=False)


def baseline_comparison():
    results = {}
    for path in (REL, "ros2_yolo_ws/scripts/Image/fusion_prob_node.py",
                 "ros2_yolo_ws/scripts/MAIN/Control/follow_stop_node.py"):
        old = subprocess.check_output(["git", "show", "808dc6c:"+path], cwd=ROOT).decode("utf-8")
        new = (ROOT/path).read_text(encoding="utf-8")
        results[path] = dump_ast(old) == dump_ast(new, remove_feature=path == REL)
    results["sim_unchanged"] = not subprocess.check_output(["git", "diff", "808dc6c", "d23e7b2", "--", "sim"], cwd=ROOT)
    assert all(results.values()), results
    return results


def callback_node(module, case):
    published = []
    node = object.__new__(module.SyncFusionNode)
    node.buf_lidar, node.lidar_angles = [(10.0, [0.8]*9)], helper.sectorizer_mids()
    node.max_dt, node.image_width, node.camera_hfov_deg = 0.1, 640, 70.0
    node.box_range_from_scan, node.scan_time, node.scan_max_age = case != "option_off", 10.0, 0.3
    node.scan_points = [(0.0, 0.8)]
    node.use_gate = case != "gate_off"
    node.gate = module.TargetGate()
    if case != "initial_lock":
        node.gate.accept(9.9, 0.0, 0.8, CHROMA, HIST)
    if case == "give_way":
        node.gate.range = 2.0
    if case == "no_cluster":
        node.scan_points = []
    if case == "stale_scan":
        node.scan_time = 9.6
    if case == "reject_far":
        node.scan_points = [(D(18), 7.43)]
    node.last_target, node.path_half_width, node.path_min_gap = (320, 240, 4, 2.0), 0.7, 0.2
    node.path_block, node.path_margin, node.path_hold = None, 0.4, 0.5
    node.last_camera_fix, node.last_camera_bearing, node.sync_count = 9.9, 0.0, 0
    node.get_logger = lambda: SimpleNamespace(info=lambda *args: None, debug=lambda *args: None)
    node.publish_synced = lambda *args: published.append(args)
    node.now_sec = lambda: 10.0
    return node, published


def state(node, published):
    return dict(gate=copy.deepcopy(node.gate.__dict__), publications=published,
                last_target=node.last_target, path_block=node.path_block,
                camera_fix=node.last_camera_fix, camera_bearing=node.last_camera_bearing,
                sync_count=node.sync_count)


def debug_patch_check():
    source = ROOT/REL
    before = source.read_bytes()
    matches = {}
    with tempfile.TemporaryDirectory(prefix="t14-debug-audit-", dir=ROOT.parent) as directory:
        scratch = Path(directory).resolve()
        assert scratch.is_relative_to(ROOT.parent.resolve())
        target = scratch/REL
        target.parent.mkdir(parents=True)
        target.write_bytes(before)
        subprocess.run([sys.executable, str(DEBUG/"make_debug_build.py"), str(scratch)], check=True)
        compile(target.read_text(encoding="utf-8"), str(target), "exec")
        saved = helper.SYNC
        try:
            helper.SYNC = target
            patched = helper._load_sync_module()
        finally:
            helper.SYNC = saved
        for case in ("initial_lock", "accepted", "reject_far", "give_way", "no_cluster", "stale_scan", "option_off", "gate_off"):
            snapshots = []
            for module in (M, patched):
                node, published = callback_node(module, case)
                cx = module.bearing_to_cx(D(18), 640, 70) if case == "reject_far" else 320
                node.try_sync_from_yolo(10.0, cx, 240, 4, CHROMA, HIST)
                snapshots.append(state(node, published))
            matches[case] = snapshots[0] == snapshots[1]
        for module in (M, patched):
            node, published = callback_node(module, "accepted")
            node.use_lidar_track, node.last_camera_fix = True, 9.0
            node.lidar_after, node.lidar_max, node.edge_rad = 0.3, 5.0, D(27)
            node.last_camera_bearing, node.gate.bearing, node.gate.range = D(30), D(30), 1.0
            node.scan_points = helper.SectorAssociationTest._person(math.cos(D(30)), math.sin(D(30)))
            node.track_with_lidar()
            if module is M:
                plain = state(node, published)
            else:
                matches["lidar_track"] = plain == state(node, published)
    assert source.read_bytes() == before
    assert all(matches.values()), matches
    return dict(patch_applies_to_copy=True, source_unchanged=True, fixed_callback_results_equal=matches,
                limit="logging adds wall-clock overhead; this does not establish ROS timing equivalence")


def production_regression():
    import numpy as np
    source = ROOT/"ros2_yolo_ws/scripts/Lidar/lidar_sectorizer_node.py"
    cls = next(n for n in ast.parse(source.read_text(encoding="utf-8")).body if isinstance(n, ast.ClassDef))
    cb = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "cb")
    ns = dict(np=np, math=math, Float32MultiArray=SimpleNamespace, LaserScan=object)
    exec(compile(ast.Module(body=[cb], type_ignores=[]), str(source), "exec"), ns)
    emitted = []
    node = SimpleNamespace(frame_count=0, angle_offset=math.pi, fov_min=-35, fov_max=35, N=9,
                           pub_dist=SimpleNamespace(publish=lambda msg:emitted.append(msg.data)),
                           pub_var=SimpleNamespace(publish=lambda msg:None),
                           pub_angle=SimpleNamespace(publish=lambda msg:None))
    ranges = []
    for i in range(720):
        robot_deg = (i*0.5 + 180) % 360 - 180
        ranges.append(0.8 if -17 <= robot_deg <= 17 else 7.43 if 17.5 <= robot_deg <= 19 else math.inf)
    # raw -pi + i*0.5deg, rotated by pi, has robot bearing i*0.5deg, wrapped above.
    scan = SimpleNamespace(ranges=ranges, angle_min=-math.pi, angle_max=-math.pi+D(0.5)*719,
                           range_min=0.05, range_max=12.0)
    ns["cb"](node, scan)
    actual = emitted[0][M.nearest_sector(D(18), helper.sectorizer_mids())]
    assert actual == 0.8
    name = "test_a_box_far_behind_a_near_person_gets_its_own_range"
    baseline = unittest.TestResult()
    unittest.TestSuite([helper.SectorAssociationTest(name)]).run(baseline)

    class SectorOnly(helper.SectorAssociationTest):
        @classmethod
        def setUpClass(cls):
            cls.m = SimpleNamespace(**M.__dict__)
            cls.m.box_range = lambda points, bearing: cls._sector_median(points, bearing)

    mutant = unittest.TestResult()
    unittest.TestSuite([SectorOnly(name)]).run(mutant)
    assert baseline.wasSuccessful() and len(mutant.failures) == 1 and not mutant.errors
    return dict(actual_sectorizer_median_m=float(actual), revised_test_passed=baseline.wasSuccessful(),
                old_sector_only_mutant_failures=len(mutant.failures), numpy_version=np.__version__)


def historical_rows_check(cohorts):
    old = json.loads((ROOT/"experiments/sim/2026-10-27_hs_colour_twin_t13.json").read_text())
    results = []
    for row in cohorts["off"]:
        if row["code"] != "808dc6c":
            continue
        source = [r for r in old if r["scenario"] == "side_step" and r["seed"] == row["seed"]]
        assert len(source) == 1
        source = source[0]
        exact = all(row[k] == source[k] for k in ("pass_", "contact", "target_visible_share", "max_abs_target_bearing_deg"))
        rounded_gap = round(source["final_gap_m"], 2) == row["final_gap_m"]
        assert exact and rounded_gap
        results.append(dict(seed=row["seed"], source_fields_match=exact, gap_matches_at_record_precision=rounded_gap))
    return results


def trace_checks(cohorts):
    result = {}
    for path in sorted(DEBUG.glob("*_gate.log")):
        mode, seed = path.stem.split("_")[:2]
        seed = int(seed[1:])
        rows, last_update, previous, key = [], None, -math.inf, None
        track_count = 0
        for line in path.read_text().splitlines():
            values = dict(re.findall(r"(\w+)=([^ ]+)", line))
            t = float(values["t"])
            assert t >= previous
            previous = t
            if "lidar-track" in line:
                last_update = t
                track_count += 1
                continue
            if "skip-inf" in line:
                continue
            row = {k:float(values[k]) for k in ("t", "b", "d", "sec", "pb", "pr", "cost")}
            row["ok"] = values["ok"] == "True"
            if not row["ok"] and last_update is not None and key is None and abs(row["pb"]) < 10 \
                    and 15 <= abs(row["b"]) <= 35 and abs(row["d"]-row["pr"]) <= 0.1 \
                    and t-last_update < 0.5 and row["cost"] > 9:
                # Bounds include +/-0.005 s and +/-0.05 deg rounding in each printed value.
                max_dt = t-last_update+0.01
                widen = 1+max(0.0, max_dt-0.2)
                bearing_lower = (max(0, abs(row["b"]-row["pb"])-0.1)/(5*widen))**2
                key = dict(**row, seconds_since_last_update=round(t-last_update, 3),
                           bearing_cost_lower_bound=bearing_lower)
            rows.append(row)
            if row["ok"]:
                last_update = t
        score_path = path.with_name(path.name.replace("_gate.log", "_score.json"))
        score = json.loads(score_path.read_text())
        assert score["seed"] == seed and score["ros_params"] == ["box_range_from_scan:="+mode]
        expected_mode = "on" if mode == "true" else "off"
        cohort = next(r for r in cohorts[expected_mode] if r["seed"] == seed)
        result[path.name] = dict(log_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            score_passed=passes(score), counted_cohort_passed=cohort["pass_"],
            score_visible_share=score["target_visible_share"], cohort_visible_share=cohort["target_visible_share"],
            score_matches_counted_run=abs(score["target_visible_share"]-cohort["target_visible_share"])<=0.0005
                and abs(score["max_abs_target_bearing_deg"]-cohort["max_abs_target_bearing_deg"])<=0.05,
            gate_events=len(rows), lidar_track_events=track_count, first_close_angular_rejection=key)
    for name in ("true_s10_gate.log", "false_s12_gate.log"):
        assert result[name]["first_close_angular_rejection"]["bearing_cost_lower_bound"] > 9
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    evidence = evidence_inventory()
    result = dict(baseline_comparison=baseline_comparison(), debug_patch=debug_patch_check(),
                  production_regression=production_regression(),
                  historical_rows=historical_rows_check(evidence["side_step_records"]),
                  traces=trace_checks(evidence["side_step_records"]),
                  trace_limit="instrumented reruns, not the counted side_step_check trials; no ROS rerun here")
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
