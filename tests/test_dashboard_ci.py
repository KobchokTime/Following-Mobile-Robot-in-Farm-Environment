"""Offline checks for the GitHub Actions CI snapshot generator."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "dashboard" / "ci"))
from gen_ci import api_url, main, make_rows  # noqa: E402


GENERATED = "2026-10-28T04:00:00Z"
API = api_url("KobchokTime", "Following-Mobile-Robot-in-Farm-Environment", "twin.yml", 60)


def run(number, status, conclusion, **extra):
    return {
        "id": number + 1000, "run_number": number, "run_attempt": 1,
        "head_branch": "integration-hub", "head_sha": "1234567890abcdef",
        "event": "push", "status": status, "conclusion": conclusion,
        "created_at": "2026-10-28T01:00:00Z", "updated_at": "2026-10-28T01:10:00Z",
        "html_url": f"https://github.com/example/actions/runs/{number + 1000}",
        **extra,
    }


def convert(runs, fetched="2026-10-28T03:00:00Z"):
    return make_rows({"workflow_runs": runs}, source_api_url=API,
                     fetched_utc=fetched, generated_utc=GENERATED)


class CiGeneratorTests(unittest.TestCase):
    def test_success_in_progress_failure_and_no_stale_green(self):
        rows = convert([
            run(4, "completed", "success"),
            run(5, "in_progress", "success"),  # rerun retained an old conclusion
            run(6, "queued", None),
            run(7, "completed", "failure"),
            run(8, "completed", None),
        ])
        self.assertEqual([r["result"] for r in rows],
                         ["success", "running", "running", "failure", "unknown"])
        self.assertEqual(rows[0]["commit"], "12345678")
        self.assertEqual(rows[0]["fetched_utc"], "2026-10-28T03:00:00Z")

    def test_stable_order_latest_attempt_and_limit(self):
        older_attempt = run(11, "completed", "success", run_attempt=1,
                            updated_at="2026-10-28T02:00:00Z")
        new_attempt = run(11, "in_progress", "success", run_attempt=2,
                          updated_at="2026-10-28T02:10:00Z")
        inputs = [run(9, "completed", "failure"), older_attempt,
                  run(10, "completed", "success"), new_attempt]
        a = convert(inputs)
        b = convert(list(reversed(inputs)))
        self.assertEqual(a, b)
        self.assertEqual([r["run"] for r in a], [9, 10, 11])
        self.assertEqual(a[-1]["result"], "running")
        limited = make_rows(inputs, source_api_url=API, fetched_utc=None,
                            generated_utc=GENERATED, limit=2)
        self.assertEqual([r["run"] for r in limited], [10, 11])

    def test_missing_optional_values_do_not_claim_a_fresh_fetch(self):
        row = convert([{"run_number": 2, "status": "completed", "conclusion": "cancelled"}],
                      fetched=None)[0]
        self.assertEqual((row["branch"], row["commit"], row["trigger"]),
                         ("—", "—", "—"))
        self.assertIsNone(row["started_utc"])
        self.assertIsNone(row["fetched_utc"])
        self.assertEqual(row["result"], "cancelled")

    def test_cli_reads_snapshot_and_writes_page_compatible_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            inp, out = Path(tmp) / "runs.json", Path(tmp) / "ci_runs.json"
            inp.write_text(json.dumps({"workflow_runs": [run(21, "completed", "success")]}),
                           encoding="utf-8")
            self.assertEqual(main(["--input", str(inp), "--output", str(out),
                                   "--fetched-at", "2026-10-28T03:00:00Z"]), 0)
            rows = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["run"], 21)
            self.assertEqual(rows[0]["fetched_utc"], "2026-10-28T03:00:00Z")
            self.assertTrue(rows[0]["source_url"].startswith("https://github.com/"))

    def test_rejects_missing_run_number(self):
        with self.assertRaisesRegex(ValueError, "run_number"):
            convert([{"status": "completed", "conclusion": "success"}])


if __name__ == "__main__":
    unittest.main()
