"""Score a twin run from its JSONL state log. Standard library only.

Every metric is computed from the simulator's ground truth, not from what the
robot believed. The metrics are descriptive; whether they pass is a research
decision, so this module does not apply thresholds.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path
from typing import Iterable, List, Optional

from .world import PERSON_RADIUS_M

CONTACT_M = 2 * PERSON_RADIUS_M  # robot centre to person centre, rough robot half-width + person radius
STOPPED_MPS = 0.02


def load(path: Path) -> List[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _first(rows: Iterable[dict], pred) -> Optional[dict]:
    return next((r for r in rows if pred(r)), None)


def score(rows: List[dict], target_distance_m: float = 0.5) -> dict:
    if not rows:
        return {"samples": 0}
    target = next(n for n, p in rows[0]["people"].items() if p["is_target"])
    gap = [r["people"][target]["range_m"] - PERSON_RADIUS_M for r in rows]
    bearing = [r["people"][target]["bearing_deg"] for r in rows]
    speed = [r["robot"]["v"] for r in rows]
    moving = [r for r in rows if abs(r["robot"]["v"]) > STOPPED_MPS]
    min_person = min(p["range_m"] for r in rows for p in r["people"].values())

    result = {
        "samples": len(rows),
        "duration_s": rows[-1]["t"] - rows[0]["t"],
        "distance_travelled_m": math.hypot(rows[-1]["robot"]["x"], rows[-1]["robot"]["y"]),
        "final_gap_m": gap[-1],
        "median_gap_m": statistics.median(gap),
        "max_gap_m": max(gap),
        "gap_target_m": target_distance_m,
        "time_moving_s": len(moving) * (rows[1]["t"] - rows[0]["t"]) if len(rows) > 1 else 0.0,
        "max_speed_mps": max(speed),
        "min_speed_mps": min(speed),
        "max_abs_target_bearing_deg": max(abs(b) for b in bearing),
        "final_target_bearing_deg": bearing[-1],
        "target_in_camera_fov_end": abs(bearing[-1]) <= 35.0,
        "min_person_range_m": min_person,
        "contact": min_person < CONTACT_M,
        "max_abs_rpm": max(max(abs(r["robot"]["rpm_left"]), abs(r["robot"]["rpm_right"])) for r in rows),
        "turned": any(abs(r["robot"]["w"]) > 1e-3 for r in rows),
    }

    # Share of the run (after the 3 s start) with the target in the camera's view and within 2 m.
    # Ground-truth visibility: it shows the robot stayed with the target, not what a tracker believed.
    later = [i for i, r in enumerate(rows) if r["t"] >= 3.0]
    if later:
        result["target_visible_share"] = sum(abs(bearing[i]) <= 35.0 and gap[i] <= 2.0 for i in later) / len(later)
    others = [n for n in rows[0]["people"] if n != target]
    if others:
        result["min_other_range_m"] = min(r["people"][n]["range_m"] for r in rows for n in others)

    start = _first(rows, lambda r: r["blackout"])
    if start is not None:
        after = [r for r in rows if r["t"] >= start["t"]]
        stop = _first(after, lambda r: abs(r["robot"]["v"]) <= STOPPED_MPS)
        result["blackout_start_s"] = start["t"]
        result["stop_latency_s"] = None if stop is None else stop["t"] - start["t"]
        result["distance_during_blackout_m"] = sum(
            abs(r["robot"]["v"]) * (rows[1]["t"] - rows[0]["t"]) for r in after if r["blackout"])
    return result


def main(argv: List[str]) -> int:
    rows = load(Path(argv[1]))
    print(json.dumps(score(rows), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
