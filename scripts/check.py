"""Offline checks every agent runs before handing off. Standard library only.

Usage (Windows: ``py -3 scripts/check.py``, Linux/macOS: ``python3 scripts/check.py``).
Exits non-zero when a blocking check fails; missing quest sources are warnings.
"""

from __future__ import annotations

import compileall
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY_DIRS = ["ros2_yolo_ws/scripts", "src", "tests", "tools", "scripts"]
QUEST_DATA = ROOT / "tools/thesis_desk/thesis_data.json"
SOURCE_RE = re.compile(r"[\w./-]+\.(?:md|py|json|csv|yaml)")


def check_compile() -> bool:
    ok = all(compileall.compile_dir(str(ROOT / d), quiet=1) for d in PY_DIRS if (ROOT / d).exists())
    print(f"[{'PASS' if ok else 'FAIL'}] compile {', '.join(PY_DIRS)}")
    return ok


def check_tests() -> bool:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    ok = result.wasSuccessful()
    print(f"[{'PASS' if ok else 'FAIL'}] unit tests ({result.testsRun} run)")
    return ok


def check_quest_data() -> bool:
    try:
        data = json.loads(QUEST_DATA.read_text(encoding="utf-8"))
        tasks = data["tasks"]
    except (OSError, ValueError, KeyError) as exc:
        print(f"[FAIL] {QUEST_DATA.relative_to(ROOT)}: {exc}")
        return False
    print(f"[PASS] {QUEST_DATA.relative_to(ROOT)} ({len(tasks)} tasks)")
    missing = sorted({p for t in tasks for p in SOURCE_RE.findall(str(t.get("source", ""))) if not (ROOT / p).exists()})
    for path in missing:
        print(f"[WARN] quest source not in repo: {path}")
    return True


def main() -> int:
    results = [check_compile(), check_quest_data(), check_tests()]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
