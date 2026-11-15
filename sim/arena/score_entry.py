#!/usr/bin/env python3
"""Score an arena entry from a twin run summary. Standard library only.

    python3 -m sim.arena.score_entry sim_runs/summary.json \
        --baseline experiments/arena/baseline_2026-10-20.json [--base-ref REF --head-ref REF]

The rules are in `experiments/arena/2026-10-20_sector-association.md`. They were frozen before
any entry was written. Scoring:

- Task (60 points): in `curve_left` with the `diff_drive` bridge, the robot must turn (20),
  keep the target in the camera's field of view at the end (20), and bring the final gap
  close to the 0.5 m set-point (up to 20, linear down to 0 at 3.0 m of error).
- No regressions (40 points, 5 off per failed check). For every scenario × bridge:
  no contact; distance travelled at least 90 % of baseline (curve_left excluded, since it
  is expected to change); `target_loss` stop latency at most 1.5 s.
- Scope: with `--base-ref/--head-ref`, every changed file must be under the allowed paths,
  otherwise the entry is disqualified.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ALLOWED_PREFIXES = ("ros2_yolo_ws/scripts/", "tests/", "logs/", "experiments/arena/entries/")


def changed_files(base: str, head: str) -> list:
    out = subprocess.run(["git", "diff", "--name-only", f"{base}...{head}"],
                         check=True, capture_output=True, text=True).stdout
    return [line for line in out.splitlines() if line]


def score(summary: list, baseline: list) -> dict:
    runs = {(r["scenario"], r["bridge_mode"]): r for r in summary}
    base = {(r["scenario"], r["bridge_mode"]): r for r in baseline}
    detail, points = {}, 0.0

    task = runs.get(("curve_left", "diff_drive"))
    if task is None:
        detail["task"] = "missing curve_left/diff_drive run"
    else:
        turned = bool(task.get("turned"))
        in_fov = bool(task.get("target_in_camera_fov_end"))
        gap_err = abs(task["final_gap_m"] - 0.5)
        gap_pts = max(0.0, 20.0 * (1.0 - gap_err / 3.0))
        points += 20 * turned + 20 * in_fov + gap_pts
        detail["task"] = {"turned": turned, "target_in_fov_end": in_fov,
                          "final_gap_m": task["final_gap_m"], "gap_points": round(gap_pts, 2)}

    regressions = []
    for key, b in base.items():
        r = runs.get(key)
        name = "/".join(key)
        if r is None:
            regressions.append(f"{name}: missing")
            continue
        if r["contact"]:
            regressions.append(f"{name}: contact")
        if key[0] != "curve_left" and r["distance_travelled_m"] < 0.9 * b["distance_travelled_m"]:
            regressions.append(f"{name}: travelled {r['distance_travelled_m']:.2f} m "
                               f"< 90% of baseline {b['distance_travelled_m']:.2f} m")
        if key[0] == "target_loss" and (r.get("stop_latency_s") is None or r["stop_latency_s"] > 1.5):
            regressions.append(f"{name}: stop latency {r.get('stop_latency_s')}")
    points += max(0, 40 - 5 * len(regressions))
    detail["regressions"] = regressions
    return {"points": round(points, 2), "max_points": 100, "detail": detail}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("summary", type=Path)
    ap.add_argument("--baseline", type=Path, default=Path("experiments/arena/baseline_2026-10-20.json"))
    ap.add_argument("--base-ref")
    ap.add_argument("--head-ref", default="HEAD")
    args = ap.parse_args()

    result = score(json.loads(args.summary.read_text(encoding="utf-8")),
                   json.loads(args.baseline.read_text(encoding="utf-8"))["runs"])
    if args.base_ref:
        outside = [f for f in changed_files(args.base_ref, args.head_ref)
                   if not f.startswith(ALLOWED_PREFIXES)]
        result["out_of_scope_files"] = outside
        if outside:
            result["points"] = 0.0
            result["disqualified"] = "changed files outside the allowed paths"
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
