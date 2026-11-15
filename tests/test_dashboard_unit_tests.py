"""Offline checks for the dashboard unit-test snapshot generator."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_dashboard_unit_tests as generator  # noqa: E402


class DashboardUnitSnapshotTests(unittest.TestCase):
    def test_records_pass_failure_skip_subtest_and_fixture_error(self):
        class PassingSample(unittest.TestCase):
            def test_pass(self):
                self.assertTrue(True)

        class FailingSample(unittest.TestCase):
            def test_failure(self):
                self.fail("synthetic failure")

        class SkippedSample(unittest.TestCase):
            @unittest.skip("synthetic skip")
            def test_skip(self):
                self.fail("must not run")

        class SubtestSample(unittest.TestCase):
            def test_subtest_failure(self):
                with self.subTest(value=1):
                    self.assertEqual(1, 2)

        class FixtureErrorSample(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise RuntimeError("synthetic fixture error")

            def test_never_runs(self):
                self.fail("must not run")

        suite = unittest.TestSuite([
            PassingSample("test_pass"), FailingSample("test_failure"),
            SkippedSample("test_skip"), SubtestSample("test_subtest_failure"),
            FixtureErrorSample("test_never_runs"),
        ])
        rows, result, _ = generator.run_suite(suite, branch="codex/qa/example",
                                              commit="a" * 40, run_utc="2026-10-28T07:00:00Z")
        self.assertFalse(result.wasSuccessful())
        by_test = {row["test"]: row for row in rows}
        self.assertEqual(by_test["test_pass"]["result"], "pass")
        self.assertEqual(by_test["test_failure"]["result"], "fail")
        self.assertEqual(by_test["test_skip"]["result"], "skip")
        self.assertEqual(by_test["test_subtest_failure"]["result"], "fail")
        self.assertTrue(any(row["result"] == "error" for row in rows))
        self.assertEqual(by_test["test_pass"]["file"], "tests/test_dashboard_unit_tests.py")
        self.assertTrue(all(row["branch"] == "codex/qa/example" for row in rows))
        self.assertTrue(all(row["commit"] == "a" * 40 for row in rows))
        self.assertEqual(len({row["test_id"] for row in rows}), len(rows))

    def test_cli_writes_a_dated_snapshot_from_this_checkout(self):
        class PassingSample(unittest.TestCase):
            def test_pass(self):
                self.assertTrue(True)

        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
            output = Path(tmp) / "unit_tests.json"
            suite = unittest.TestSuite([PassingSample("test_pass")])
            with patch.object(generator, "_git_value", side_effect=["codex/qa/example", "a" * 40, ""]), \
                 patch.object(generator.unittest.defaultTestLoader, "discover", return_value=suite):
                self.assertEqual(generator.main(["--output", str(output)]), 0)
            rows = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 1)
            self.assertTrue(all(row["result"] == "pass" for row in rows))
            self.assertTrue(all(row["run_utc"].endswith("Z") for row in rows))
            self.assertEqual(rows[0]["branch"], "codex/qa/example")
            self.assertEqual(rows[0]["commit"], "a" * 40)
            self.assertFalse(rows[0]["working_tree_dirty"])


if __name__ == "__main__":
    unittest.main()
