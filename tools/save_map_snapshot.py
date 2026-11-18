#!/usr/bin/env python3
"""Snapshot the current LiDAR scan from the live viewer and save as JSON + PNG.

Usage:
    python tools/save_map_snapshot.py [--label TEXT] [--viewer http://127.0.0.1:8770]

Saves to experiments/hardware-runs/<run_id>/maps/ — creates the folder if needed.
Falls back to tools/maps/ when no run_id is given.
"""
import argparse
import json
import math
import os
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

VIEWER_URL = "http://127.0.0.1:8770"
DEFAULT_RUN = "20261107-site01"


def fetch_scan(base_url: str) -> dict:
    url = base_url.rstrip("/") + "/api/scan"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


def render_png(scan: dict, out_path: Path, label: str = "") -> None:
    if not HAS_MPL:
        print("  matplotlib not available — skipping PNG", file=sys.stderr)
        return
    ranges = scan["ranges"]
    angle_min = scan["angle_min"]
    angle_inc = scan["angle_increment"]
    fig, ax = plt.subplots(subplot_kw={"projection": "polar"}, figsize=(7, 7))
    fig.patch.set_facecolor("#07111d")
    ax.set_facecolor("#07111d")
    ax.tick_params(colors="#8da9c1")
    ax.spines["polar"].set_color("#28415c")
    for i, r in enumerate(ranges):
        if r is None:
            continue
        angle = angle_min + i * angle_inc
        # matplotlib polar: 0=right, +CCW; ROS: 0=forward, +CCW
        # rotate so 0 points up (forward)
        mpl_angle = math.pi / 2 - angle
        color = "#ff6666" if r < 0.45 else ("#6de2a5" if r < 1.5 else "#57a6ff")
        ax.plot(mpl_angle, r, ".", color=color, markersize=2.5, alpha=0.85)
    # Robot marker at origin
    ax.plot(0, 0, "^", color="#5cb4ff", markersize=10, zorder=5)
    ax.set_rmax(5.0)
    ax.set_rticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(["1m", "2m", "3m", "4m", "5m"], color="#8da9c1", fontsize=8)
    ax.grid(color="#233c56", linestyle="-", linewidth=0.6)
    title = f"LiDAR Snapshot  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    if label:
        title += f"\n{label}"
    ax.set_title(title, color="#eaf3ff", pad=14, fontsize=11)
    near_p = mpatches.Patch(color="#ff6666", label="< 0.45 m")
    mid_p = mpatches.Patch(color="#6de2a5", label="0.45–1.5 m")
    far_p = mpatches.Patch(color="#57a6ff", label="> 1.5 m")
    ax.legend(handles=[near_p, mid_p, far_p], loc="lower right",
              facecolor="#112136", edgecolor="#28415c", labelcolor="#eaf3ff", fontsize=8)
    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Snapshot LiDAR scan from live viewer")
    parser.add_argument("--label", default="", help="Short label for this snapshot")
    parser.add_argument("--viewer", default=VIEWER_URL, help="Live viewer base URL")
    parser.add_argument("--run", default=DEFAULT_RUN, help="Run ID under experiments/hardware-runs/")
    args = parser.parse_args()

    # Resolve output directory relative to repo root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    run_dir = repo_root / "experiments" / "hardware-runs" / args.run / "maps"
    run_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    slug = "_" + args.label.replace(" ", "_") if args.label else ""
    stem = f"scan_{ts}{slug}"

    print(f"Fetching scan from {args.viewer}/api/scan …", flush=True)
    data = fetch_scan(args.viewer)

    if not data.get("connected"):
        age = data.get("age_s")
        err = data.get("error", "unknown")
        print(f"WARNING: viewer says not connected (age={age}s, error={err!r})", file=sys.stderr)

    scan = data.get("scan")
    if scan is None:
        print("ERROR: no scan data available yet", file=sys.stderr)
        sys.exit(1)

    valid = sum(1 for r in scan["ranges"] if r is not None)
    print(f"  {len(scan['ranges'])} beams total, {valid} valid")

    # Save JSON
    json_path = run_dir / f"{stem}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"snapshot_time": time.time(), "label": args.label, "scan": scan}, f, indent=2)
    print(f"  JSON -> {json_path}")

    # Render PNG
    png_path = run_dir / f"{stem}.png"
    render_png(scan, png_path, label=args.label)
    if png_path.exists():
        print(f"  PNG  -> {png_path}")
    else:
        print("  PNG  -> skipped (matplotlib unavailable)")

    print("Done.")


if __name__ == "__main__":
    main()
