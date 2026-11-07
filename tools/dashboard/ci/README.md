# CI data for Follower Test Bench

`gen_ci.py` prepares the `ci_runs` dataset consumed by the **เทสต์และ CI** tab. It uses
only Python's standard library. The default source is the public GitHub Actions
`twin.yml` workflow in `KobchokTime/Following-Mobile-Robot-in-Farm-Environment`.

Fetch one current page without a token or paid API:

```sh
python tools/dashboard/ci/gen_ci.py --fetch --output /tmp/ci_runs.json
```

Or convert a previously saved response from the GitHub REST endpoint:

```sh
python tools/dashboard/ci/gen_ci.py --input /path/to/workflow-runs.json \
  --fetched-at 2026-10-28T03:00:00Z --output /tmp/ci_runs.json
```

The input must be the JSON response from
`GET /repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs`, or its
`workflow_runs` array. `--fetched-at` is optional for an offline file; omit it
when the original fetch time is unknown. `--limit` selects the latest 1–100 run
numbers (default 60). A rerun keeps its run number, so the latest attempt wins.
Output is sorted oldest to newest, as the page expects. `started_utc` comes from
`run_started_at`, falling back to `created_at`. Each row records its GitHub
`source_url`, the API query, `fetched_utc` (null if unknown), and `generated_utc`.

The page recognizes `success` (green), `running` (gray), and other results
(red). The generator marks a run `success` **only** if its GitHub status is
`completed` and its conclusion is `success`; queued or in-progress reruns stay
gray even if GitHub still reports an earlier success conclusion. Missing branch,
commit or event fields are shown as `—`; a missing start time stays null.

This command creates a local snapshot. It does **not** update the published
Claude dashboard, the `datasets.json` record, or `unit_tests`. Claude must upload
the new JSON and update the published `ci_runs` dataset before viewers see it.
The committed `ci_runs.json` is a dated example fetched at
`2026-10-28T04:29:32Z`; check its per-row `fetched_utc` before using it.
The tab currently does not display `fetched_utc`; a green historical run must
not be read as proof that the current branch is green. Public GitHub API access
may be unavailable from some networks and is rate-limited; the `--input` path
works offline.

Run offline tests:

```sh
python -m unittest discover -s tests -p test_dashboard_ci.py -v
```

GitHub's [workflow runs endpoint](https://docs.github.com/en/rest/actions/workflow-runs)
permits unauthenticated reads of public resources. See its
[rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
before scheduling refreshes.
