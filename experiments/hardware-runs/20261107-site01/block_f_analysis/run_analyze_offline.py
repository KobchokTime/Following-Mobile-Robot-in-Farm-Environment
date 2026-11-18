"""Run integration-hub tools/robot_day/analyze.py on a laptop copy of robot-day bags, without ROS 2.

Only read_bag() is swapped for a pure-Python rosbags reader; every statistic is analyze.py's own.
Recordings whose label parses as a ground-truth experiment are relabelled to `uncontrolled_<label>`
when listed in --untrusted-label-dirs, so they feed E2 only.

    python run_analyze_offline.py ANALYZE_PY DATA_ROOT --out report.json [--untrusted-label-dirs D ...]
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore

TYPESTORE = get_typestore(Stores.ROS2_HUMBLE)


def _plain(msg):
    if hasattr(msg, "data") and hasattr(msg.data, "tolist"):
        return SimpleNamespace(data=msg.data.tolist())
    return msg


def read_bag_rosbags(bag_dir: Path, topics):
    wanted = set(topics)
    with AnyReader([Path(bag_dir)], default_typestore=TYPESTORE) as reader:
        conns = [c for c in reader.connections if c.topic in wanted]
        out = {c.topic: [] for c in conns}
        for conn, t_ns, raw in reader.messages(connections=conns):
            out[conn.topic].append((t_ns * 1e-9, _plain(reader.deserialize(raw, conn.msgtype))))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("analyze_py", type=Path)
    ap.add_argument("data_root", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--untrusted-label-dirs", nargs="*", default=[])
    args = ap.parse_args()

    spec = importlib.util.spec_from_file_location("analyze", args.analyze_py)
    analyze = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analyze)
    analyze.read_bag = read_bag_rosbags

    untrusted = set(args.untrusted_label_dirs)
    recordings, skipped, relabelled = [], [], {}
    for manifest in sorted(args.data_root.rglob("recording.json")):
        run_dir = manifest.parent
        bag = run_dir / "recording"
        label = json.loads(manifest.read_text())["scenario"]
        if not (bag / "metadata.yaml").exists():
            skipped.append(run_dir.name)
            continue
        if run_dir.name in untrusted and analyze.parse_label(label)["exp"] != "other":
            relabelled[run_dir.name] = (label, f"uncontrolled_{label}")
            label = f"uncontrolled_{label}"
        recordings.append((label, bag))

    unlabelled = []
    for meta in sorted(args.data_root.rglob("metadata.yaml")):
        bag = meta.parent
        if (bag.parent / "recording.json").exists():
            continue
        label = bag.parent.name.split("Z_", 1)[-1]
        if analyze.parse_label(label)["exp"] != "other":
            label = f"unlabelled_{label}"
        unlabelled.append(str(bag.relative_to(args.data_root)))
        recordings.append((label, bag))

    report = analyze.analyse(recordings)
    report["_inputs"] = {
        "analyze_py": str(args.analyze_py.name),
        "bag_reader": "rosbags (pure Python) in place of rosbag2_py",
        "recordings": [{"label": l, "bag": str(b.relative_to(args.data_root))} for l, b in recordings],
        "skipped_no_bag": skipped,
        "bags_without_recording_json_labelled_by_folder": unlabelled,
        "relabelled_untrusted_ground_truth": relabelled,
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"recordings={len(recordings)} skipped={len(skipped)} relabelled={len(relabelled)} "
          f"e1={len(report['e1'])} e2={len(report['e2'])} e3={len(report['e3'])} e6={len(report['e6'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
