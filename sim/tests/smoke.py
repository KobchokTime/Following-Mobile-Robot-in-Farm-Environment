#!/usr/bin/env python3
"""Regression smoke check over a twin run summary (sim_runs/summary.json).

Asserts only behaviour the current robot code already shows, so a failure means a
regression, not an open research question. Open findings live in DISCUSSION.md.
"""

import json
import sys
from pathlib import Path

summary = {(r["scenario"], r["bridge_mode"]): r
           for r in json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))}
failures = []


def check(key, cond, text):
    if key in summary and not cond(summary[key]):
        failures.append(f"{key}: {text}: {json.dumps(summary[key])}")


for key, r in summary.items():
    check(key, lambda r: not r["contact"], "robot touched a person")
check(("straight", "current"), lambda r: r["distance_travelled_m"] > 2.0, "robot did not follow")
check(("target_loss", "current"),
      lambda r: r["stop_latency_s"] is not None and r["stop_latency_s"] <= 1.5,
      "robot did not stop within 1.5 s of target loss")

print("\n".join(failures) or f"smoke OK ({len(summary)} runs)")
sys.exit(1 if failures else 0)
