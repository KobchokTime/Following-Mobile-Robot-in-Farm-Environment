#!/usr/bin/env python3
"""Arena 2 scorer (DRAFT until both agents agree in DISCUSSION.md). Standard library only.

    python3 -m sim.arena.score_entry_v2 --twin RUN_DIR [RUN_DIR ...] [--gazebo SUMMARY ...] \
        --agent claude|codex --base-ref REF [--head-ref HEAD]

Each RUN_DIR holds a `summary.json` from `sim.twin.run_scenario --scenario all --bridge-mode all`.
Each Gazebo SUMMARY is a `summary_gazebo.json` from `sim.gazebo.run_gazebo`. Lessons from Arena 1
are built in: repeated runs, failures counted, and stricter scope checks.

Scoring, 100 points, everything on the `fixed` bridge (the real bridge with angular.z):
- Lag, 50: for straight, stop_and_go and curve_left, the median gap should be close to the 0.5 m
  set-point. Each is worth up to 50/3, falling linearly to 0 at 1.5 m of error, averaged over the
  twin repeats.
- Reliability, 30: curve_left must end with the target in view and within 1.5 m, in every twin
  repeat and every Gazebo run. 30 × the share of runs that pass.
- Safety-relevant behaviour, 20, 5 off per failed check: no contact in any run of any bridge;
  target_loss stops within 1.5 s in every repeat; curve_left still turns.
- Scope: any changed file outside the allowed paths, a rename (checked with --no-renames), another
  agent's log, or a protected file means 0 points.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path

ALLOWED = ("ros2_yolo_ws/scripts/", "tests/", "experiments/arena/entries/")
PROTECTED = ("ros2_yolo_ws/scripts/MAIN/Control/zlac_joystick_bridge.py",)
LAG_SCENARIOS = ("straight", "stop_and_go", "curve_left")


def load(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8"))


def scope(base: str, head: str, agent: str) -> list:
    out = subprocess.run(["git", "diff", "--name-status", "--no-renames", f"{base}...{head}"],
                         check=True, capture_output=True, text=True).stdout
    bad = []
    for line in out.splitlines():
        status, path = line.split("\t", 1)
        own_log = path == f"logs/{agent}.md"
        if path in PROTECTED or not (own_log or path.startswith(ALLOWED)):
            bad.append(f"{status} {path}")
    return bad


def is_failure(r: dict) -> bool:
    return not r.get("target_in_camera_fov_end") or r["final_gap_m"] > 1.5


def score(twin_runs: list, gazebo_runs: list) -> dict:
    lag_points, lag_detail = [], {}
    for sc in LAG_SCENARIOS:
        meds = [r["median_gap_m"] for run in twin_runs for r in run
                if r["scenario"] == sc and r["bridge_mode"] == "fixed"]
        if not meds:
            lag_detail[sc] = "missing"
            continue
        m = statistics.fmean(meds)
        lag_points.append(max(0.0, (50 / 3) * (1 - abs(m - 0.5) / 1.5)))
        lag_detail[sc] = round(m, 3)
    lag = sum(lag_points)

    curve = [r for run in twin_runs for r in run if r["scenario"] == "curve_left" and r["bridge_mode"] == "fixed"]
    curve += [r for r in gazebo_runs if r["scenario"] == "curve_left" and r["bridge_mode"] == "fixed"]
    failures = sum(is_failure(r) for r in curve)
    reliability = 30 * (1 - failures / len(curve)) if curve else 0.0

    checks = []
    every = [r for run in twin_runs for r in run] + list(gazebo_runs)
    if any(r["contact"] for r in every):
        checks.append("contact in at least one run")
    if any(r["scenario"] == "target_loss" and (r.get("stop_latency_s") is None or r["stop_latency_s"] > 1.5)
           for r in every):
        checks.append("target_loss did not stop within 1.5 s")
    if curve and not all(r["turned"] for r in curve):
        checks.append("curve_left did not turn in every run")
    behaviour = max(0, 20 - 5 * len(checks))

    return {"points": round(lag + reliability + behaviour, 2), "max_points": 100,
            "lag": {"points": round(lag, 2), "mean_median_gap_m": lag_detail},
            "reliability": {"points": round(reliability, 2), "runs": len(curve), "failures": failures},
            "behaviour": {"points": behaviour, "failed_checks": checks},
            "twin_repeats": len(twin_runs), "gazebo_runs": len(gazebo_runs)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--twin", nargs="+", type=Path, required=True)
    ap.add_argument("--gazebo", nargs="*", type=Path, default=[])
    ap.add_argument("--agent", choices=["claude", "codex"])
    ap.add_argument("--base-ref")
    ap.add_argument("--head-ref", default="HEAD")
    args = ap.parse_args()
    result = score([load(d / "summary.json") for d in args.twin], [r for p in args.gazebo for r in load(p)])
    if args.base_ref:
        bad = scope(args.base_ref, args.head_ref, args.agent or "")
        result["out_of_scope"] = bad
        if bad:
            result["points"] = 0.0
            result["disqualified"] = "changed files outside scope, renamed, or protected"
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
