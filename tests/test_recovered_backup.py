import ast
import csv
import math
import statistics
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "ros2_yolo_ws" / "scripts"
CSV_PATH = SCRIPTS / "log" / "synced_20251111_123335.csv"
MODEL_DIR = ROOT / "yolov8n_openvino_model"


class RecoveredBackupTests(unittest.TestCase):
    def test_all_python_sources_parse(self):
        files = sorted(SCRIPTS.rglob("*.py"))
        self.assertEqual(len(files), 29)
        for path in files:
            with self.subTest(path=path.relative_to(ROOT)):
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_expected_ros_pipeline_topics_are_present(self):
        source = "\n".join(
            path.read_text(encoding="utf-8") for path in SCRIPTS.rglob("*.py")
        )
        for topic in (
            "/synced_target",
            "/target_fused_prob",
            "/cmd_vel",
        ):
            with self.subTest(topic=topic):
                self.assertIn(topic, source)

    def test_experiment_csv_is_well_formed(self):
        with CSV_PATH.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 3528)
        self.assertEqual(
            set(rows[0]), {"cx", "cy", "dist_m", "sector", "dt_ms", "stamp"}
        )
        for row in rows:
            values = [float(row[key]) for key in row]
            self.assertTrue(all(math.isfinite(value) for value in values))
            self.assertGreaterEqual(float(row["cx"]), 0.0)
            self.assertLessEqual(float(row["cx"]), 640.0)
            self.assertGreaterEqual(float(row["sector"]), 0.0)
            self.assertLessEqual(float(row["sector"]), 8.0)
            self.assertGreater(float(row["dist_m"]), 0.0)
            self.assertGreaterEqual(float(row["dt_ms"]), 0.0)

    def test_experiment_latency_regression_guard(self):
        with CSV_PATH.open(newline="", encoding="utf-8") as handle:
            delays = [float(row["dt_ms"]) for row in csv.DictReader(handle)]
        self.assertAlmostEqual(statistics.mean(delays), 49.087873, places=5)
        self.assertAlmostEqual(statistics.median(delays), 49.189926, places=5)
        self.assertLess(max(delays), 100.0)

    def test_openvino_export_is_complete(self):
        xml_path = MODEL_DIR / "yolov8n.xml"
        bin_path = MODEL_DIR / "yolov8n.bin"
        metadata_path = MODEL_DIR / "metadata.yaml"
        ET.parse(xml_path)
        self.assertGreater(bin_path.stat().st_size, 10_000_000)
        metadata = metadata_path.read_text(encoding="utf-8")
        self.assertIn("task: detect", metadata)
        self.assertIn("0: person", metadata)


if __name__ == "__main__":
    unittest.main()
