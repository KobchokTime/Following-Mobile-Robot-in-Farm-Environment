"""Validate the five live JSON datasets before publishing Follower Test Bench.

Usage: python scripts/validate_dashboard_live.py <output-dir> [--registry PATH]

This checks the published schema and cross-file consistency. It cannot prove that
the underlying twin run, image, or code revision produced a reported score.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "tools/dashboard/live/registry.json"
DATASETS = ("live_experiments", "live_runs", "live_tracks", "past_tracks", "live_scenarios")
MAX_BYTES = 8_000_000
ID_RE = re.compile(r"[a-z0-9_]+\Z")
UTC_RE = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
DONE = ("pass", "fail")
SCORE_FIELDS = ("final_gap_m", "visible_share", "contact", "in_view_end", "max_bearing_deg",
                "published", "published_other")


def _load(path: Path, errors: list[str], limit: bool = False):
    try:
        if limit and path.stat().st_size > MAX_BYTES:
            errors.append(f"{path.name}: exceeds {MAX_BYTES} bytes")
            return None
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
        if value is None:
            errors.append(f"{path.name}: expected a JSON list, got null")
        return value
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"{path}: cannot read JSON: {exc}")
        return None


def _required(row: dict, names: tuple[str, ...], where: str, errors: list[str]) -> bool:
    missing = [name for name in names if name not in row]
    if missing:
        errors.append(f"{where}: missing {', '.join(missing)}")
    return not missing


def _integer(value) -> bool:
    return type(value) is int and value >= 0


def _number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _timestamp(value) -> bool:
    if not isinstance(value, str) or not UTC_RE.fullmatch(value):
        return False
    try:
        dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        return True
    except ValueError:
        return False


def _registry(rows, errors: list[str]) -> tuple[dict, dict, set]:
    experiments, expected, scenarios = {}, {}, set()
    if not isinstance(rows, list):
        errors.append("registry: expected a list")
        return experiments, expected, scenarios
    live_count = 0
    for i, exp in enumerate(rows):
        where = f"registry[{i}]"
        if not isinstance(exp, dict) or not _required(exp, ("id", "title", "code", "dir", "started_utc", "order", "live", "runs"), where, errors):
            errors.append(f"{where}: expected an experiment object with required fields")
            continue
        eid = exp["id"]
        if not isinstance(eid, str) or not ID_RE.fullmatch(eid):
            errors.append(f"{where}: invalid id")
            continue
        if eid in experiments:
            errors.append(f"{where}: duplicate experiment {eid}")
            continue
        experiments[eid] = exp
        for name in ("title", "code", "dir"):
            if not isinstance(exp[name], str) or not exp[name]:
                errors.append(f"{where}: {name} must be nonempty text")
        for name in ("purpose", "compare", "result"):
            if name in exp and not isinstance(exp[name], str):
                errors.append(f"{where}: {name} must be text")
        if not _timestamp(exp["started_utc"]):
            errors.append(f"{where}: invalid started_utc")
        if type(exp["order"]) is not int or type(exp["live"]) is not bool:
            errors.append(f"{where}: order/live have wrong types")
        live_count += exp["live"] is True
        if not isinstance(exp["runs"], list):
            errors.append(f"{where}: runs must be a list")
            continue
        for j, run in enumerate(exp["runs"]):
            at = f"{where}.runs[{j}]"
            if not isinstance(run, dict) or not _required(run, ("tag", "scenario", "seed", "variant", "light"), at, errors):
                errors.append(f"{at}: expected a run object with required fields")
                continue
            if any(not isinstance(run[k], str) or not run[k] for k in ("tag", "scenario", "variant", "light")) or not _integer(run["seed"]):
                errors.append(f"{at}: invalid tag/scenario/seed/variant/light")
                continue
            key = f"{eid}|{run['tag']}|{run['scenario']}"
            if key in expected:
                errors.append(f"{at}: duplicate run key {key}")
            expected[key] = (exp, run)
            scenarios.add(run["scenario"])
    if live_count > 1:
        errors.append("registry: more than one live experiment")
    return experiments, expected, scenarios


def _run_rows(rows, expected: dict, errors: list[str]) -> dict:
    by_key = {}
    if not isinstance(rows, list):
        errors.append("live_runs: expected a list")
        return by_key
    fields = ("run", "experiment", "scenario", "seed", "variant", "light", "status", *SCORE_FIELDS,
              "started_utc", "finished_utc")
    for i, row in enumerate(rows):
        where = f"live_runs[{i}]"
        if not isinstance(row, dict) or not _required(row, fields, where, errors):
            errors.append(f"{where}: expected a complete run row")
            continue
        key = row["run"]
        if not isinstance(key, str):
            errors.append(f"{where}: run must be text")
            continue
        if key in by_key:
            errors.append(f"{where}: duplicate run key {key}")
            continue
        by_key[key] = row
        if key not in expected:
            errors.append(f"{where}: unknown run key {key}")
            continue
        exp, source = expected[key]
        for field, want in (("experiment", exp["id"]), ("scenario", source["scenario"]),
                            ("seed", source["seed"]), ("variant", source["variant"]), ("light", source["light"])):
            if type(row[field]) is not type(want) or row[field] != want:
                errors.append(f"{where}: {field} differs from registry")
        status = row["status"]
        if status not in ("queued", "running", "pass", "fail"):
            errors.append(f"{where}: invalid status")
            continue
        for name in ("started_utc", "finished_utc"):
            if row[name] is not None and not _timestamp(row[name]):
                errors.append(f"{where}: invalid {name}")
        if status == "queued" and row["started_utc"] is not None:
            errors.append(f"{where}: queued run has started_utc")
        if status == "running" and row["started_utc"] is None:
            errors.append(f"{where}: running run lacks started_utc")
        if (status in DONE) != (row["finished_utc"] is not None):
            errors.append(f"{where}: finished_utc does not match status")
        if status not in DONE:
            if any(row[name] is not None for name in SCORE_FIELDS):
                errors.append(f"{where}: unfinished run has score fields")
            continue
        for name in ("final_gap_m", "visible_share", "max_bearing_deg"):
            if not _number(row[name]) or row[name] < 0:
                errors.append(f"{where}: invalid {name}")
        if _number(row["visible_share"]) and not 0 <= row["visible_share"] <= 1:
            errors.append(f"{where}: visible_share outside [0,1]")
        for name in ("contact", "in_view_end"):
            if type(row[name]) is not bool:
                errors.append(f"{where}: {name} must be boolean")
        for name in ("published", "published_other"):
            if row[name] is not None and not _integer(row[name]):
                errors.append(f"{where}: {name} must be a nonnegative integer or null")
        if _integer(row["published"]) and _integer(row["published_other"]) and row["published_other"] > row["published"]:
            errors.append(f"{where}: published_other exceeds published")
        if status == "pass" and (row["contact"] is True or row["in_view_end"] is False or
                                 (_number(row["final_gap_m"]) and row["final_gap_m"] > 1.505) or
                                 (_number(row["visible_share"]) and row["visible_share"] < 0.8995)):
            errors.append(f"{where}: pass contradicts displayed score")
    for key in expected.keys() - by_key.keys():
        errors.append(f"live_runs: missing expected run {key}")
    return by_key


def _experiment_rows(rows, registry: dict, runs: dict, errors: list[str]) -> None:
    if not isinstance(rows, list):
        errors.append("live_experiments: expected a list")
        return
    seen = set()
    for i, row in enumerate(rows):
        where = f"live_experiments[{i}]"
        fields = ("experiment", "title", "code", "order", "started_utc", "purpose", "compare", "result",
                  "total", "done", "passed", "failed", "running", "status", "last_finished_utc",
                  "eta_min", "checked_utc")
        if not isinstance(row, dict) or not _required(row, fields, where, errors):
            errors.append(f"{where}: expected a complete experiment row")
            continue
        eid = row["experiment"]
        if not isinstance(eid, str) or eid not in registry:
            errors.append(f"{where}: unknown experiment {eid}")
            continue
        if eid in seen:
            errors.append(f"{where}: duplicate experiment {eid}")
            continue
        seen.add(eid)
        exp = registry[eid]
        for name, want in (("title", exp["title"]), ("code", exp["code"]),
                           ("order", exp.get("order", 0)), ("started_utc", exp["started_utc"]),
                           ("purpose", exp.get("purpose", "")), ("compare", exp.get("compare", "")),
                           ("result", exp.get("result", ""))):
            if type(row[name]) is not type(want) or row[name] != want:
                errors.append(f"{where}: {name} differs from registry")
        for name in ("last_finished_utc", "checked_utc"):
            if row[name] is not None and not _timestamp(row[name]):
                errors.append(f"{where}: invalid {name}")
        if row["checked_utc"] is None:
            errors.append(f"{where}: missing checked_utc")
        if row["eta_min"] is not None and (not _number(row["eta_min"]) or row["eta_min"] < 0):
            errors.append(f"{where}: invalid eta_min")
        own = [r for r in runs.values() if r.get("experiment") == eid]
        counts = {name: sum(r.get("status") == name for r in own) for name in ("pass", "fail", "running")}
        expected_counts = {"total": len(exp["runs"]), "done": counts["pass"] + counts["fail"],
                           "passed": counts["pass"], "failed": counts["fail"], "running": counts["running"]}
        for name, want in expected_counts.items():
            if not _integer(row[name]) or row[name] != want:
                errors.append(f"{where}: {name} is {row[name]}, expected {want}")
        status = ("done" if expected_counts["done"] == expected_counts["total"] else
                  "running" if expected_counts["done"] or expected_counts["running"] else "queued")
        if exp.get("stopped") and status != "done":
            status = "stopped"
        if row["status"] != status:
            errors.append(f"{where}: status is {row['status']}, expected {status}")
        finished = [r["finished_utc"] for r in own if r.get("finished_utc") and _timestamp(r["finished_utc"])]
        if row["last_finished_utc"] != (max(finished) if finished else None):
            errors.append(f"{where}: last_finished_utc differs from runs")
        if (not expected_counts["done"] or status == "done") and row["eta_min"] is not None:
            errors.append(f"{where}: eta_min should be null")
    for eid in registry.keys() - seen:
        errors.append(f"live_experiments: missing experiment {eid}")


def _tracks(rows, name: str, expected: dict, runs: dict, errors: list[str]) -> None:
    if not isinstance(rows, list):
        errors.append(f"{name}: expected a list")
        return
    last_time = {}
    fields = ("run", "t", "rx", "ry", "ryaw", "v", "tx", "ty", "gap", "tb", "ox", "oy")
    for i, row in enumerate(rows):
        where = f"{name}[{i}]"
        if not isinstance(row, dict) or not _required(row, fields, where, errors):
            errors.append(f"{where}: expected a complete track row")
            continue
        key = row["run"]
        if not isinstance(key, str) or key not in expected:
            errors.append(f"{where}: unknown run reference {key}")
            continue
        exp, _ = expected[key]
        if (name == "live_tracks") != (exp.get("live") is True):
            errors.append(f"{where}: track is in the wrong live/past file")
        if key not in runs or runs[key].get("status") not in DONE:
            errors.append(f"{where}: track references an unfinished run")
        if not _number(row["t"]) or row["t"] < 0 or (key in last_time and row["t"] <= last_time[key]):
            errors.append(f"{where}: t must increase within each run")
        else:
            last_time[key] = row["t"]
        for field in ("rx", "ry", "ryaw", "v"):
            if not _number(row[field]):
                errors.append(f"{where}: invalid {field}")
        target = [row[field] for field in ("tx", "ty", "gap", "tb")]
        if any(x is None for x in target) != all(x is None for x in target) or any(x is not None and not _number(x) for x in target):
            errors.append(f"{where}: target position fields must be all null or finite numbers")
        if row["gap"] is not None and _number(row["gap"]) and row["gap"] < 0:
            errors.append(f"{where}: negative gap")
        if (row["ox"] is None) != (row["oy"] is None) or any(row[x] is not None and not _number(row[x]) for x in ("ox", "oy")):
            errors.append(f"{where}: other-person coordinates must be both null or finite numbers")


def _scenarios(rows, expected: set, errors: list[str]) -> None:
    if not isinstance(rows, list):
        errors.append("live_scenarios: expected a list")
        return
    seen = set()
    for i, row in enumerate(rows):
        where = f"live_scenarios[{i}]"
        if not isinstance(row, dict) or not _required(row, ("scenario", "doc", "duration_s", "people", "paths", "notes"), where, errors):
            errors.append(f"{where}: expected a complete scenario row")
            continue
        name = row["scenario"]
        if not isinstance(name, str):
            errors.append(f"{where}: scenario must be text")
            continue
        if name in seen:
            errors.append(f"{where}: duplicate scenario {name}")
        seen.add(name)
        if not isinstance(row["doc"], str) or not row["doc"]:
            errors.append(f"{where}: doc must be nonempty text")
        if row["duration_s"] is not None and (not _number(row["duration_s"]) or row["duration_s"] <= 0):
            errors.append(f"{where}: invalid duration_s")
        if not _integer(row["people"]):
            errors.append(f"{where}: invalid people count")
        for field, kind in (("paths", list), ("notes", dict)):
            try:
                value = json.loads(row[field]) if isinstance(row[field], str) else None
            except ValueError:
                value = None
            if not isinstance(value, kind):
                errors.append(f"{where}: {field} must encode a JSON {kind.__name__}")
    for name in expected - seen:
        errors.append(f"live_scenarios: missing scenario {name}")
    for name in seen - expected:
        errors.append(f"live_scenarios: unknown scenario {name}")


def validate(registry_path: Path, output_dir: Path) -> list[str]:
    """Return all detected schema and cross-file errors; no network or ROS needed."""
    errors = []
    registry_rows = _load(registry_path, errors)
    if registry_rows is None:
        return errors
    registry, expected, scenarios = _registry(registry_rows, errors)
    data = {name: _load(output_dir / f"{name}.json", errors, limit=True) for name in DATASETS}
    if any(value is None for value in data.values()):
        return errors
    runs = _run_rows(data["live_runs"], expected, errors)
    _experiment_rows(data["live_experiments"], registry, runs, errors)
    _tracks(data["live_tracks"], "live_tracks", expected, runs, errors)
    _tracks(data["past_tracks"], "past_tracks", expected, runs, errors)
    _scenarios(data["live_scenarios"], scenarios, errors)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = parser.parse_args(argv)
    errors = validate(args.registry, args.output_dir)
    for error in errors:
        print(f"[FAIL] {error}")
    if errors:
        print(f"{len(errors)} validation error(s)")
        return 1
    print("[PASS] five dashboard live datasets are internally consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
