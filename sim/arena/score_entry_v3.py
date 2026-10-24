#!/usr/bin/env python3
"""Arena 3 scorer (frozen 2026-10-22 after both agents agreed in DISCUSSION.md T8). Standard library only.

    python3 -m sim.arena.score_entry_v3 --twin RUN_DIR [RUN_DIR ...] --gazebo SUMMARY [SUMMARY ...] \
        --agent claude|codex --base-ref FREEZE_SHA [--head-ref HEAD]

Each RUN_DIR holds a `summary.json` from
`sim.twin.run_scenario --scenario everything --bridge-mode turning --seed N` (fixed and diff_drive). Each Gazebo SUMMARY is a `summary_gazebo.json`
from `sim.gazebo.run_gazebo --bridge-mode fixed`.

Scoring, 100 points, on the `fixed` bridge unless stated:
- Identity, 50: the identity scenarios (crossing, side_by_side, side_by_side_same, head_on,
  stand_aside), twin and
  Gazebo. 30 × the share of runs that pass (target in view at the end, within 1.5 m, no contact,
  target visible for at least 90% of the run) + 20 × the mean visible share.
- Following, 30: 20 for lag (as Arena 2: median gap of straight, stop_and_go and curve_left against
  0.5 m, falling to 0 at 1.5 m of error) + 10 × the share of curve_left runs that pass.
- Behaviour, 20, 5 off per failed check, on both bridges: any contact; target_loss not stopping
  within 1.5 s; curve_left not turning.
- Scope: as Arena 2. Any changed file outside the allowed paths, a rename, another agent's log, or
  a protected file means 0 points.

The minimum protocol is checked before scoring; an incomplete input set exits with code 2.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path

from sim.twin.scenarios import ALL_SCENARIOS

ALLOWED = ("ros2_yolo_ws/scripts/", "tests/")
PROTECTED = ("ros2_yolo_ws/scripts/MAIN/Control/zlac_joystick_bridge.py",)
BRIDGE_MODES = ("fixed", "diff_drive")
IDENTITY = ("crossing", "side_by_side", "side_by_side_same", "head_on", "stand_aside")
LAG_SCENARIOS = ("straight", "stop_and_go", "curve_left")
GAZEBO_MIN = {"curve_left": 2, "side_by_side": 2, "side_by_side_same": 2, "stand_aside": 2}
MIN_TWIN_REPEATS = 3
MIN_VISIBLE_SHARE = 0.9


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
    want = sorted((sc, m) for sc in ALL_SCENARIOS for m in BRIDGE_MODES)
    seeds = []
    for i, run in enumerate(twin_runs):
        got = sorted((r.get("scenario"), r.get("bridge_mode")) for r in run)
        if got != want:
            missing = sorted(set(want) - set(got))
            extra = sorted(set(got) - set(want))
            problems.append(f"twin repeat {i}: missing {missing}, unexpected {extra}, duplicates {len(got) - len(set(got))}")
        run_seeds = {r.get("seed") for r in run}
        if any(not isinstance(x, int) or isinstance(x, bool) for x in run_seeds):
            problems.append(f"twin repeat {i}: every row needs an integer seed, got {sorted(map(str, run_seeds))}")
        elif len(run_seeds) != 1:
            problems.append(f"twin repeat {i}: expected one seed, got {sorted(map(str, run_seeds))}")
        seeds.extend(run_seeds)
    if len(set(seeds)) != len(seeds):
        problems.append(f"twin repeats reuse a seed: {sorted(map(str, seeds))}")
    for sc, n in GAZEBO_MIN.items():
        got = sum(r.get("scenario") == sc and r.get("bridge_mode") == "fixed" for r in gazebo_runs)
        if got < n:
            problems.append(f"{got} Gazebo {sc}/fixed runs, need at least {n}")
    return problems


def passes(r: dict) -> bool:
    return (bool(r.get("target_in_camera_fov_end")) and r["final_gap_m"] <= 1.5 and not r["contact"]
            and r.get("target_visible_share", 0.0) >= MIN_VISIBLE_SHARE)


def score(twin_runs: list, gazebo_runs: list) -> dict:
    twin = [r for run in twin_runs for r in run]
    fixed = [r for r in twin if r["bridge_mode"] == "fixed"] + [r for r in gazebo_runs if r["bridge_mode"] == "fixed"]

    ident = [r for r in fixed if r["scenario"] in IDENTITY]
    ident_pass = sum(passes(r) for r in ident)
    visible = statistics.fmean(r.get("target_visible_share", 0.0) for r in ident) if ident else 0.0
    identity = (30 * ident_pass / len(ident) + 20 * visible) if ident else 0.0
    per_scenario = {sc: f"{sum(passes(r) for r in ident if r['scenario'] == sc)}/{sum(r['scenario'] == sc for r in ident)}"
                    for sc in IDENTITY}

    lag_points, lag_detail = [], {}
    for sc in LAG_SCENARIOS:
        meds = [r["median_gap_m"] for r in twin if r["scenario"] == sc and r["bridge_mode"] == "fixed"]
        if not meds:
            lag_detail[sc] = "missing"
            continue
        m = statistics.fmean(meds)
        lag_points.append(max(0.0, (20 / 3) * (1 - abs(m - 0.5) / 1.5)))
        lag_detail[sc] = round(m, 3)
    curve = [r for r in fixed if r["scenario"] == "curve_left"]
    curve_fail = sum(not r.get("target_in_camera_fov_end") or r["final_gap_m"] > 1.5 for r in curve)
    following = sum(lag_points) + (10 * (1 - curve_fail / len(curve)) if curve else 0.0)

    checks = []
    every = twin + list(gazebo_runs)
    if any(r["contact"] for r in every):
        checks.append("contact in at least one run")
    if any(r["scenario"] == "target_loss" and (r.get("stop_latency_s") is None or r["stop_latency_s"] > 1.5)
           for r in every):
        checks.append("target_loss did not stop within 1.5 s")
    turns = [r for r in every if r["scenario"] == "curve_left"]  # twin on both bridges, plus Gazebo
    if turns and not all(r["turned"] for r in turns):
        checks.append("curve_left did not turn in every run")
    behaviour = max(0, 20 - 5 * len(checks))

    return {"points": round(identity + following + behaviour, 2), "max_points": 100,
            "identity": {"points": round(identity, 2), "runs": len(ident), "passed": ident_pass,
                         "mean_visible_share": round(visible, 3), "passed_per_scenario": per_scenario},
            "following": {"points": round(following, 2), "mean_median_gap_m": lag_detail,
                          "curve_left_runs": len(curve), "curve_left_failures": curve_fail},
            "behaviour": {"points": behaviour, "failed_checks": checks},
            "twin_repeats": len(twin_runs), "gazebo_runs": len(gazebo_runs)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--twin", nargs="+", type=Path, required=True)
    ap.add_argument("--gazebo", nargs="+", type=Path, required=True)
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
