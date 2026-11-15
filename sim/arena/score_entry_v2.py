#!/usr/bin/env python3
"""Arena 2 scorer (frozen 2026-10-21 after both agents agreed in DISCUSSION.md T7). Standard library only.

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

The minimum protocol is enforced before scoring (T7 review): at least 3 twin repeats with distinct
integer seeds, each holding every scenario on every bridge mode exactly once, and at least 2 Gazebo
`curve_left`/`fixed` runs, each from a different file. An incomplete input set is not scored; the
scorer exits with code 2. `--agent` and `--base-ref` are required, so the scope check always runs.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path

from sim.twin.scenarios import SCENARIOS

ALLOWED = ("ros2_yolo_ws/scripts/", "tests/")
PROTECTED = ("ros2_yolo_ws/scripts/MAIN/Control/zlac_joystick_bridge.py",)
LAG_SCENARIOS = ("straight", "stop_and_go", "curve_left")
BRIDGE_MODES = ("current", "fixed", "diff_drive")
MIN_TWIN_REPEATS = 3
MIN_GAZEBO_CURVE_RUNS = 2


def load(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8"))


def scope(base: str, head: str, agent: str) -> list:
    out = subprocess.run(["git", "diff", "--name-status", "--no-renames", f"{base}...{head}"],
                         check=True, capture_output=True, text=True).stdout
    bad = []
    for line in out.splitlines():
        status, path = line.split("\t", 1)
        own = path in (f"logs/{agent}.md", f"experiments/arena/entries/{agent}.md")
        if path in PROTECTED or not (own or path.startswith(ALLOWED)):
            bad.append(f"{status} {path}")
    return bad


def validate(twin_runs: list, gazebo_runs: list) -> list:
    """Reasons the inputs fall short of the minimum protocol; empty when they meet it."""
    problems = []
    if len(twin_runs) < MIN_TWIN_REPEATS:
        problems.append(f"{len(twin_runs)} twin repeats, need at least {MIN_TWIN_REPEATS}")
    want = sorted((sc, m) for sc in SCENARIOS for m in BRIDGE_MODES)
    seeds = []
    for i, run in enumerate(twin_runs):
        got = sorted((r.get("scenario"), r.get("bridge_mode")) for r in run)
        if got != want:
            missing = sorted(set(want) - set(got))
            extra = sorted(set(got) - set(want))
            dupes = len(got) - len(set(got))
            problems.append(f"twin repeat {i}: missing {missing}, unexpected {extra}, duplicates {dupes}")
        run_seeds = {r.get("seed") for r in run}
        if any(not isinstance(x, int) or isinstance(x, bool) for x in run_seeds):
            problems.append(f"twin repeat {i}: every row needs an integer seed, got {sorted(map(str, run_seeds))}")
        elif len(run_seeds) != 1:
            problems.append(f"twin repeat {i}: expected one seed, got {sorted(map(str, run_seeds))}")
        seeds.extend(run_seeds)
    if len(set(seeds)) != len(seeds):
        problems.append(f"twin repeats reuse a seed: {sorted(map(str, seeds))}")
    curve = [r for r in gazebo_runs if r.get("scenario") == "curve_left" and r.get("bridge_mode") == "fixed"]
    if len(curve) < MIN_GAZEBO_CURVE_RUNS:
        problems.append(f"{len(curve)} Gazebo curve_left/fixed runs, need at least {MIN_GAZEBO_CURVE_RUNS}")
    return problems


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
    ap.add_argument("--agent", choices=["claude", "codex"], required=True)
    ap.add_argument("--base-ref", required=True, help="the freeze commit; the scope check always runs")
    ap.add_argument("--head-ref", default="HEAD")
    args = ap.parse_args()
    paths = [d.resolve() for d in args.twin] + [g.resolve() for g in args.gazebo]
    if len(set(paths)) != len(paths):
        print(json.dumps({"invalid_inputs": ["the same run directory or Gazebo summary was passed twice"]}, indent=2))
        return 2
    twin_runs = [load(d / "summary.json") for d in args.twin]
    gazebo_runs = [r for p in args.gazebo for r in load(p)]
    problems = validate(twin_runs, gazebo_runs)
    if problems:
        print(json.dumps({"invalid_inputs": problems}, indent=2))
        return 2
    result = score(twin_runs, gazebo_runs)
    bad = scope(args.base_ref, args.head_ref, args.agent)
    result["out_of_scope"] = bad
    if bad:
        result["points"] = 0.0
        result["disqualified"] = "changed files outside scope, renamed, or protected"
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
