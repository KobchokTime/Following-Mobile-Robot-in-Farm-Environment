# Dashboard data provenance

This page describes the repository generators for the Follower Test Bench dashboard. Their JSON outputs are **dated snapshots**, not live readings. The repository copy of the page and dataset metadata is in [`tools/dashboard/`](../tools/dashboard/README.md); Claude publishes the artifact separately after the source is integrated.

| Dataset | Input and generator | What the provenance fields mean |
|---|---|---|
| `ci_runs` | A saved GitHub Actions `twin.yml` workflow-runs response, or a public API fetch, through [`gen_ci.py`](../tools/dashboard/ci/gen_ci.py) | `branch`, abbreviated `commit`, and `source_url` come from each GitHub run. `fetched_utc` is when the API response was obtained (`null` if unknown for a saved file); `generated_utc` is when this JSON was made. A queued or running rerun stays `running` even if GitHub retains an earlier success conclusion. |
| `unit_tests` | The checkout's discovered `tests/` suite through [`generate_dashboard_unit_tests.py`](../scripts/generate_dashboard_unit_tests.py) | Every outcome carries the Git `branch`, full `commit`, `working_tree_dirty`, `run_utc`, and generator `source`. These describe the checkout and test execution at export time, not the present branch or a live test state. |
| `live_experiments`, `live_runs`, `live_tracks`, `past_tracks`, `live_scenarios` | Expected runs in [`registry.json`](../tools/dashboard/live/registry.json) plus twin run folders, through [`gen_live.py`](../tools/dashboard/live/gen_live.py) | `code` and `started_utc` on an experiment come from the registry; `checked_utc` is when the export was made. Run `started_utc` and `finished_utc` come from `world.log` and `score.json` file modification times. A `score.json` makes a run `pass` or `fail`, only `world.log` makes it `running`, and neither makes it `queued`. |

## Rebuild and check a snapshot

Run these from the repository root. Put `<out>` outside the checkout if you do not want generated files in Git status. Use the actual fetch time for an offline CI response; omit `--fetched-at` when it is unknown.

```sh
python tools/dashboard/ci/gen_ci.py --input <saved-workflow-runs.json> --fetched-at <actual-UTC-time> --output <out>/ci_runs.json
python scripts/generate_dashboard_unit_tests.py --output <out>/unit_tests.json
python tools/dashboard/live/gen_live.py --runs-root <runs-root> --out <out>
python scripts/validate_dashboard_live.py <out>
python scripts/check.py
```

For a current public CI fetch, use `python tools/dashboard/ci/gen_ci.py --fetch --output <out>/ci_runs.json`. This needs network access; `--input` works offline. The live generator expects each run's `world.log`, `score.json`, and `state.jsonl` under the registry's experiment directory and `<tag>/<scenario>_mps/`. Its five published JSON files are checked together by [`validate_dashboard_live.py`](../scripts/validate_dashboard_live.py), including registry references, status/count consistency, tracks, and file size. That structural check does not prove which simulator image or code produced a score.

## Reading the dashboard

The page displays snapshot times for CI and unit tests. A historical green CI tile proves that **that recorded run** completed successfully; it says nothing about a newer commit until a newer run is fetched and published. A `live_runs` result likewise reflects the exported run folder at `checked_utc`, not a continuous connection to a running twin. The registry's `code` field is a label supplied by the experiment record, not an independent Git attestation for each run.

[`datasets.json`](../tools/dashboard/datasets.json) is a repository snapshot of artifact-store records, including blob URLs and `updated` values. It is not synchronized automatically with the published artifact. After generation and validation, Claude uploads JSON assets and updates the artifact's `datasets/<id>.source.url`; until then the published page still reads the previous blobs. See the [dashboard source README](../tools/dashboard/README.md) and [CI generator README](../tools/dashboard/ci/README.md) for the publication and field details.
