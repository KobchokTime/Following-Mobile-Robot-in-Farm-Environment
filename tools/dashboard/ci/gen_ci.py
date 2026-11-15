#!/usr/bin/env python3
"""Build the Follower Test Bench ci_runs dataset from GitHub Actions REST JSON."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

DEFAULT_OWNER = "KobchokTime"
DEFAULT_REPO = "Following-Mobile-Robot-in-Farm-Environment"
DEFAULT_WORKFLOW = "twin.yml"


def utc_iso(value: str | None) -> str | None:
    """Normalize a GitHub timestamp; missing optional timestamps stay missing."""
    if not value:
        return None
    if not isinstance(value, str):
        raise ValueError(f"timestamp must be a string: {value!r}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid UTC timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include an offset: {value!r}")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def api_url(owner: str, repo: str, workflow: str, per_page: int) -> str:
    for label, value in (("owner", owner), ("repo", repo), ("workflow", workflow)):
        if not value or "/" in value or "\\" in value or value in {".", ".."}:
            raise ValueError(f"invalid {label}: {value!r}")
    if not 1 <= per_page <= 100:
        raise ValueError("--limit must be between 1 and 100")
    return (f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}"
            f"/actions/workflows/{quote(workflow)}/runs?per_page={per_page}&page=1")


def fetch_runs(url: str) -> tuple[dict, str]:
    request = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "follower-test-bench-ci-snapshot",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"GitHub API returned HTTP {exc.code}; no output was written") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f"GitHub API unavailable: {exc}; no output was written") from exc
    return payload, datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _display(value: object, *, max_length: int | None = None) -> str:
    result = str(value).strip() if value is not None else ""
    return result[:max_length] if result and max_length else result or "—"


def _result(run: dict) -> str:
    # A rerun may retain the previous conclusion while it is queued or running.
    # Only a completed run with an explicit success conclusion may turn green.
    if run.get("status") != "completed":
        return "running"
    conclusion = run.get("conclusion")
    return conclusion.strip().lower() if isinstance(conclusion, str) and conclusion.strip() else "unknown"


def make_rows(payload: dict | list, *, source_api_url: str, fetched_utc: str | None,
              generated_utc: str, limit: int = 60) -> list[dict]:
    """Return a stable oldest-to-newest list compatible with drawCI()."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    runs = payload.get("workflow_runs") if isinstance(payload, dict) else payload
    if not isinstance(runs, list):
        raise ValueError("input must be a GitHub workflow_runs object or a list of runs")
    fetched_utc = utc_iso(fetched_utc)
    generated_utc = utc_iso(generated_utc)
    selected: dict[int, dict] = {}
    for raw in runs:
        if not isinstance(raw, dict):
            raise ValueError("every workflow run must be an object")
        number = raw.get("run_number")
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise ValueError(f"run_number must be a positive integer: {number!r}")
        attempt = raw.get("run_attempt", 1)
        if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
            raise ValueError(f"run_attempt must be a positive integer: {attempt!r}")
        row = {
            "run": number,
            "run_id": raw.get("id"),
            "attempt": attempt,
            "branch": _display(raw.get("head_branch")),
            "commit": _display(raw.get("head_sha"), max_length=8),
            "trigger": _display(raw.get("event")),
            "started_utc": utc_iso(raw.get("run_started_at") or raw.get("created_at")),
            "updated_utc": utc_iso(raw.get("updated_at")),
            "status": _display(raw.get("status")),
            "conclusion": raw.get("conclusion"),
            "result": _result(raw),
            "source_url": _display(raw.get("html_url")),
            "source_api_url": source_api_url,
            "fetched_utc": fetched_utc,
            "generated_utc": generated_utc,
        }
        # GitHub reruns keep the run number. The page keys rows by that number,
        # so retain the newest attempt regardless of API or input ordering.
        previous = selected.get(number)
        if previous is None or (attempt, row["updated_utc"] or "", str(row["run_id"] or "")) > (
            previous["attempt"], previous["updated_utc"] or "", str(previous["run_id"] or "")
        ):
            selected[number] = row
    latest = sorted(selected, reverse=True)[:limit]
    return [selected[number] for number in sorted(latest)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="saved GitHub Actions workflow-runs REST JSON")
    source.add_argument("--fetch", action="store_true", help="GET public GitHub Actions API, without credentials")
    parser.add_argument("--output", type=Path, required=True, help="write a ci_runs.json array")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW)
    parser.add_argument("--limit", type=int, default=60, help="latest runs to keep (1–100; default 60)")
    parser.add_argument("--fetched-at", help="UTC time when --input was originally fetched, if known")
    args = parser.parse_args(argv)
    try:
        url = api_url(args.owner, args.repo, args.workflow, args.limit)
        if args.fetch:
            if args.fetched_at:
                raise ValueError("--fetched-at is only valid with --input")
            payload, fetched_utc = fetch_runs(url)
        else:
            payload = json.loads(args.input.read_text(encoding="utf-8"))
            fetched_utc = args.fetched_at
        generated_utc = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        rows = make_rows(payload, source_api_url=url, fetched_utc=fetched_utc,
                         generated_utc=generated_utc, limit=args.limit)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"gen_ci: {exc}\n")
    print(f"Wrote {len(rows)} workflow runs to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
