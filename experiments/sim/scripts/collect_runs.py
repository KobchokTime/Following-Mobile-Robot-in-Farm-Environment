"""Collect twin score rows without losing the evidence needed to recount them.

Usage: python3 experiments/sim/scripts/collect_runs.py <out_dir> > rows.json

Existing score fields are retained. Every row also includes a SHA-256 of score.json
and nullable run provenance. A runner can write <out_dir>/<run>/run-provenance.json::

    {
      "score_sha256": "<64 lowercase hex characters>",
      "image_id": "sha256:<64 hex characters>",
      "image_digest": "sha256:<64 hex characters>",
      "code_revision": "<full Git commit SHA>",
      "effective_ros_params": {"target_gate": "true"}
    }

The collector verifies only the score hash binding and metadata format. Image
identity, code revision, and effective parameters are declarations until a
runner or node log independently verifies them. It does not infer runtime
values from requested ros_params or inspect a Docker image. Use
--require-provenance for new runs with complete declarations; the default
still accepts historical runs, marking absent metadata as missing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path


HEX64 = re.compile(r"[0-9a-f]{64}\Z")
GIT_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
DIGEST = re.compile(r"(?:[^\s@]+@)?sha256:[0-9a-f]{64}\Z")


def passed(score: dict) -> bool:
    return (bool(score.get("target_in_camera_fov_end"))
            and score["final_gap_m"] <= 1.5
            and not score["contact"]
            and score.get("target_visible_share", 0) >= 0.9)


def _optional_digest(value: object, field: str, path: Path) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not DIGEST.fullmatch(value):
        raise ValueError(f"{path}: {field} must be an immutable sha256 digest")
    return value


def _effective_params(value: object, path: Path) -> dict | list[str] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not key or not isinstance(item, (str, int, float, bool)):
                raise ValueError(f"{path}: effective_ros_params must map names to scalar values")
            if isinstance(item, float) and not math.isfinite(item):
                raise ValueError(f"{path}: effective_ros_params has a non-finite value")
        return value
    if isinstance(value, list) and all(isinstance(item, str) and ":=" in item for item in value):
        return value
    raise ValueError(f"{path}: effective_ros_params must be a mapping or NAME:=VALUE list")


def provenance(score_path: Path, root: Path, score_hash: str, require: bool) -> dict:
    manifest_path = score_path.parent.parent / "run-provenance.json"
    empty = {"image_id": None, "image_digest": None, "code_revision": None,
             "effective_ros_params": None, "provenance_status": "missing", "provenance_source": None}
    if not manifest_path.is_file():
        if require:
            raise ValueError(f"{score_path}: missing run-provenance.json")
        return empty

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError(f"{manifest_path}: expected a JSON object")
    declared_hash = manifest.get("score_sha256")
    if not isinstance(declared_hash, str) or not HEX64.fullmatch(declared_hash):
        raise ValueError(f"{manifest_path}: score_sha256 must be 64 lowercase hex characters")
    if declared_hash != score_hash:
        raise ValueError(f"{manifest_path}: score_sha256 does not match {score_path.name}")

    image_id = _optional_digest(manifest.get("image_id"), "image_id", manifest_path)
    image_digest = _optional_digest(manifest.get("image_digest"), "image_digest", manifest_path)
    code_revision = manifest.get("code_revision")
    if code_revision is not None and (not isinstance(code_revision, str) or not GIT_SHA.fullmatch(code_revision)):
        raise ValueError(f"{manifest_path}: code_revision must be a full Git commit SHA")
    effective = _effective_params(manifest.get("effective_ros_params"), manifest_path)
    status = "metadata_complete" if (image_id or image_digest) and code_revision and effective else "partial"
    if require and status != "metadata_complete":
        raise ValueError(f"{manifest_path}: --require-provenance needs image, code, and nonempty effective ROS parameters")
    return {"image_id": image_id, "image_digest": image_digest,
            "code_revision": code_revision, "effective_ros_params": effective,
            "provenance_status": status, "provenance_source": manifest_path.relative_to(root).as_posix()}


def collect(root: Path, require_provenance: bool = False) -> list[dict]:
    rows = []
    for score_path in sorted(root.glob("*/*_mps/score.json")):
        raw = score_path.read_bytes()
        score = json.loads(raw)
        score_hash = hashlib.sha256(raw).hexdigest()
        row = dict(run=score_path.parent.parent.name, scenario=score["scenario"], seed=score["seed"],
                   pass_=passed(score), contact=bool(score["contact"]),
                   final_gap_m=round(score["final_gap_m"], 3),
                   target_visible_share=round(score.get("target_visible_share", 0), 3),
                   max_abs_target_bearing_deg=round(score["max_abs_target_bearing_deg"], 1),
                   ros_params=score.get("ros_params", []), realism=bool(score.get("realism")),
                   target_in_camera_fov_end=bool(score.get("target_in_camera_fov_end")),
                   score_sha256=score_hash)
        row.update(provenance(score_path, root, score_hash, require_provenance))
        rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--require-provenance", action="store_true", help="fail unless every run has complete declared metadata")
    args = parser.parse_args(argv)
    try:
        rows = collect(args.out_dir, args.require_provenance)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    json.dump(rows, sys.stdout, indent=0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
