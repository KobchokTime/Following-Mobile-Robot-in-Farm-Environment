"""Run the offline unit suite and export the dashboard's unit_tests dataset.

The output is a dated snapshot of this checkout. It is never a live test status.
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _file_for(test: unittest.case.TestCase) -> str:
    module = test.__class__.__module__
    if module.startswith("test_"):
        return f"tests/{module}.py"
    if module != "unittest.suite":
        return module.replace(".", "/") + ".py"
    return "tests/<suite fixture>"


class RecordingResult(unittest.TextTestResult):
    """Keep one outcome per discovered test, including fixture failures."""

    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.records: list[dict[str, str]] = []
        self._by_id: dict[str, dict[str, str]] = {}

    def _record(self, test, outcome: str) -> None:
        test_id = test.id()
        row = self._by_id.get(test_id)
        if row is None:
            row = {
                "test_id": test_id,
                "file": _file_for(test),
                "test": getattr(test, "_testMethodName", test_id),
                "result": outcome,
            }
            self.records.append(row)
            self._by_id[test_id] = row
        else:
            row["result"] = outcome

    def startTest(self, test):
        super().startTest(test)
        self._record(test, "unknown")

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "pass")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "fail")

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "error")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "skip")

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._record(test, "expected_failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._record(test, "unexpected_success")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self._record(test, "fail" if issubclass(err[0], AssertionError) else "error")


def run_suite(suite: unittest.TestSuite, *, branch: str, commit: str,
              run_utc: str | None = None, dirty: bool = False
              ) -> tuple[list[dict[str, object]], unittest.TestResult, str]:
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=0,
                                     resultclass=RecordingResult).run(suite)
    run_utc = run_utc or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows = [dict(row, branch=branch, commit=commit, run_utc=run_utc,
                 working_tree_dirty=dirty,
                 source="scripts/generate_dashboard_unit_tests.py")
            for row in result.records]
    return rows, result, output.getvalue()


def _git_value(*args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=ROOT, check=True,
                               capture_output=True, text=True)
    return completed.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="write the dated unit_tests JSON array")
    args = parser.parse_args(argv)
    try:
        branch = _git_value("branch", "--show-current") or "detached"
        commit = _git_value("rev-parse", "HEAD")
        dirty = bool(_git_value("status", "--porcelain"))
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
        rows, result, detail = run_suite(suite, branch=branch, commit=commit, dirty=dirty)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        parser.exit(2, f"generate_dashboard_unit_tests: {exc}\n")
    print(f"Wrote {len(rows)} test outcomes to {args.output} from {branch} @ {commit[:8]}")
    print(f"Passed: {sum(r['result'] == 'pass' for r in rows)}/{len(rows)}")
    if not result.wasSuccessful():
        print(detail, file=sys.stderr)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
