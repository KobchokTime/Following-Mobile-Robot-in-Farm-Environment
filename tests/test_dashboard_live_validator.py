"""Contract checks between the live-data generator and the dashboard publisher."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_dashboard_live import validate  # noqa: E402


def experiment(eid, live, tag, queued=False):
    return {
        "id": eid, "title": eid, "code": "a" * 40, "dir": eid, "started_utc": "2026-10-28T00:00:00Z",
        "order": 2 if live else 1, "live": live, "purpose": "test", "compare": "", "result": "",
        "runs": [{"tag": tag, "scenario": "straight", "seed": 0, "variant": "baseline", "light": "ปกติ"}],
    }


class DashboardLiveValidatorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runs = self.root / "runs"
        self.out = self.root / "output"
        self.registry = self.root / "registry.json"
        self.registry.write_text(json.dumps([
            experiment("live_case", True, "live_s0"),
            experiment("past_case", False, "past_s0"),
            experiment("queued_case", False, "queued_s0"),
        ], ensure_ascii=False), encoding="utf-8")
        for eid, tag in (("live_case", "live_s0"), ("past_case", "past_s0")):
            d = self.runs / eid / tag / "straight_mps"
            d.mkdir(parents=True)
            (d / "world.log").write_text("started\n", encoding="utf-8")
            (d / "score.json").write_text(json.dumps({
                "scenario": "straight", "target_in_camera_fov_end": True, "final_gap_m": 0.6,
                "contact": False, "target_visible_share": 0.96, "max_abs_target_bearing_deg": 12.3,
            }), encoding="utf-8")
            state = {
                "t": 0.0, "robot": {"x": 0.0, "y": 0.0, "yaw_deg": 0.0, "v": 0.2},
                "people": {"person_0": {"bearing_deg": 0.0, "range_m": 0.8, "is_target": True}},
            }
            (d / "state.jsonl").write_text(json.dumps(state) + "\n", encoding="utf-8")
        self.generate()

    def generate(self):
        proc = subprocess.run([sys.executable, "tools/dashboard/live/gen_live.py", "--registry", str(self.registry),
                               "--runs-root", str(self.runs), "--out", str(self.out)], cwd=ROOT,
                              capture_output=True, text=True, check=False, env={**os.environ, "PYTHONUTF8": "0"})
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def mutate(self, filename, change):
        path = self.out / filename
        rows = json.loads(path.read_text(encoding="utf-8"))
        change(rows)
        path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    def test_generated_done_and_queued_files_pass(self):
        self.assertEqual(validate(self.registry, self.out), [])

    def test_empty_live_tracks_warns_but_still_passes(self):
        self.mutate("live_tracks.json", lambda rows: rows.clear())
        warnings = []
        self.assertEqual(validate(self.registry, self.out, warnings), [])
        self.assertTrue(any("live_tracks.json: no track samples" in warning for warning in warnings))

    def test_no_live_experiment_warns_but_still_passes(self):
        registry = json.loads(self.registry.read_text(encoding="utf-8"))
        registry[0]["live"] = False
        self.registry.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
        self.generate()
        warnings = []
        self.assertEqual(validate(self.registry, self.out, warnings), [])
        self.assertTrue(any("no experiment has live: true" in warning for warning in warnings))
        self.assertTrue(any("live_tracks.json: no track samples" in warning for warning in warnings))

    def test_past_tracks_size_warns_before_hard_limit_without_failing_cli(self):
        path = self.out / "past_tracks.json"
        with path.open("ab") as stream:
            stream.write(b" " * (6_500_001 - path.stat().st_size))
        warnings = []
        self.assertEqual(validate(self.registry, self.out, warnings), [])
        self.assertTrue(any("6500000-byte warning threshold" in warning for warning in warnings))
        proc = subprocess.run([sys.executable, "scripts/validate_dashboard_live.py", str(self.out),
                               "--registry", str(self.registry)], cwd=ROOT,
                              capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("[WARN] past_tracks.json", proc.stdout)
        self.assertIn("[PASS]", proc.stdout)

    def test_duplicate_and_missing_run_keys_fail(self):
        def corrupt(rows):
            rows.append(dict(rows[0]))
            rows.pop(2)
        self.mutate("live_runs.json", corrupt)
        errors = validate(self.registry, self.out)
        self.assertTrue(any("duplicate run key" in error for error in errors))
        self.assertTrue(any("missing expected run" in error for error in errors))

    def test_experiment_count_and_status_must_match_runs(self):
        self.mutate("live_experiments.json", lambda rows: rows[0].update(passed=0, status="queued"))
        errors = validate(self.registry, self.out)
        self.assertTrue(any("passed is" in error for error in errors))
        self.assertTrue(any("status is" in error for error in errors))

    def test_pass_and_unfinished_score_null_rules(self):
        self.mutate("live_runs.json", lambda rows: (rows[0].update(contact=True), rows[2].update(final_gap_m=0.5)))
        errors = validate(self.registry, self.out)
        self.assertTrue(any("pass contradicts" in error for error in errors))
        self.assertTrue(any("unfinished run has score" in error for error in errors))

    def test_timestamps_and_track_references(self):
        self.mutate("live_runs.json", lambda rows: rows[0].update(finished_utc="tomorrow"))
        self.mutate("live_tracks.json", lambda rows: rows[0].update(run="missing|run|straight"))
        errors = validate(self.registry, self.out)
        self.assertTrue(any("invalid finished_utc" in error for error in errors))
        self.assertTrue(any("unknown run reference" in error for error in errors))

    def test_track_time_must_increase_and_lane_must_match(self):
        self.mutate("live_tracks.json", lambda rows: rows.append(dict(rows[0])))
        self.mutate("past_tracks.json", lambda rows: rows[0].update(run="live_case|live_s0|straight"))
        errors = validate(self.registry, self.out)
        self.assertTrue(any("t must increase" in error for error in errors))
        self.assertTrue(any("wrong live/past file" in error for error in errors))

    def test_generated_track_can_have_negative_gap_at_close_range(self):
        state_path = self.runs / "live_case" / "live_s0" / "straight_mps" / "state.jsonl"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["people"]["person_0"]["range_m"] = 0.1
        state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")
        self.out = self.root / "output_close_range"  # fresh cache, so the generator reads the changed state
        self.generate()
        track = json.loads((self.out / "live_tracks.json").read_text(encoding="utf-8"))[0]
        self.assertEqual(track["gap"], -0.1)
        self.assertEqual(validate(self.registry, self.out), [])

    def test_scenario_reference_and_file_limit(self):
        self.mutate("live_scenarios.json", lambda rows: rows.clear())
        self.assertTrue(any("missing scenario straight" in error for error in validate(self.registry, self.out)))
        with (self.out / "past_tracks.json").open("ab") as stream:
            stream.write(b" " * 8_000_001)
        self.assertTrue(any("exceeds" in error for error in validate(self.registry, self.out)))

    def test_null_dataset_and_invalid_status_are_reported_without_crashing(self):
        self.mutate("live_runs.json", lambda rows: rows[0].update(status=["pass"]))
        self.assertTrue(any("invalid status" in error for error in validate(self.registry, self.out)))
        (self.out / "live_runs.json").write_text("null", encoding="utf-8")
        self.assertTrue(any("expected a JSON list" in error for error in validate(self.registry, self.out)))


if __name__ == "__main__":
    unittest.main()
