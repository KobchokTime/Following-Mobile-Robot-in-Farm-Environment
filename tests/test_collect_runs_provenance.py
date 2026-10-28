"""Offline checks that collected twin rows retain traceable run provenance."""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "collect_runs", ROOT / "experiments/sim/scripts/collect_runs.py")
collect_runs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collect_runs)


class CollectRunsProvenanceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "tests")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / "solo_s0"
        score_dir = self.run / "solo_mps"
        score_dir.mkdir(parents=True)
        self.score_path = score_dir / "score.json"
        self.score = {
            "scenario": "solo", "seed": 0, "target_in_camera_fov_end": True,
            "final_gap_m": 0.51234, "contact": False, "target_visible_share": 0.96,
            "max_abs_target_bearing_deg": 12.34, "ros_params": ["target_gate:=true"],
            "realism": True,
        }
        self.write_score()

    def write_score(self):
        self.score_path.write_text(json.dumps(self.score), encoding="utf-8")
        return hashlib.sha256(self.score_path.read_bytes()).hexdigest()

    def write_manifest(self, **changes):
        manifest = {
            "score_sha256": hashlib.sha256(self.score_path.read_bytes()).hexdigest(),
            "image_id": "sha256:" + "a" * 64,
            "code_revision": "b" * 40,
            "effective_ros_params": {"target_gate": "true"},
        }
        manifest.update(changes)
        (self.run / "run-provenance.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_historical_row_marks_missing_provenance_without_inventing_values(self):
        row, = collect_runs.collect(self.root)
        self.assertTrue(row["pass_"])
        self.assertTrue(row["target_in_camera_fov_end"])
        self.assertEqual(row["ros_params"], ["target_gate:=true"])
        self.assertEqual(row["provenance_status"], "missing")
        self.assertIsNone(row["image_id"])
        self.assertIsNone(row["code_revision"])
        self.assertIsNone(row["effective_ros_params"])
        self.assertEqual(row["score_sha256"], hashlib.sha256(self.score_path.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError, "missing run-provenance.json"):
            collect_runs.collect(self.root, require_provenance=True)

    def test_complete_manifest_preserves_declared_values_separate_from_requested(self):
        self.write_manifest(effective_ros_params={"target_gate": "false", "lateral_sigma_m": 0.15})
        row, = collect_runs.collect(self.root, require_provenance=True)
        self.assertEqual(row["provenance_status"], "metadata_complete")
        self.assertEqual(row["image_id"], "sha256:" + "a" * 64)
        self.assertEqual(row["code_revision"], "b" * 40)
        self.assertEqual(row["effective_ros_params"]["target_gate"], "false")
        self.assertEqual(row["ros_params"], ["target_gate:=true"])
        self.assertEqual(row["provenance_source"], "solo_s0/run-provenance.json")

    def test_score_change_after_manifest_is_rejected(self):
        self.write_manifest()
        self.score["final_gap_m"] = 1.8
        self.write_score()
        with self.assertRaisesRegex(ValueError, "does not match"):
            collect_runs.collect(self.root)

    def test_partial_manifest_cannot_pass_publish_mode(self):
        self.write_manifest(image_id=None, effective_ros_params=None)
        row, = collect_runs.collect(self.root)
        self.assertEqual(row["provenance_status"], "partial")
        self.assertIsNone(row["image_id"])
        with self.assertRaisesRegex(ValueError, "needs image, code, and nonempty effective"):
            collect_runs.collect(self.root, require_provenance=True)

    def test_empty_effective_params_do_not_pass_publish_mode(self):
        for empty in ({}, []):
            with self.subTest(empty=empty):
                self.write_manifest(effective_ros_params=empty)
                row, = collect_runs.collect(self.root)
                self.assertEqual(row["provenance_status"], "partial")
                with self.assertRaisesRegex(ValueError, "nonempty effective ROS parameters"):
                    collect_runs.collect(self.root, require_provenance=True)

    def test_image_tag_is_not_accepted_as_immutable_image_id(self):
        self.write_manifest(image_id="twin:lateral")
        with self.assertRaisesRegex(ValueError, "immutable sha256 digest"):
            collect_runs.collect(self.root)


if __name__ == "__main__":
    unittest.main()
