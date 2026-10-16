# Orientation experiment evidence

This folder is the durable evidence boundary for target-orientation experiments. It is intentionally usable without the robot and requires only the Python standard library.

## Per-run checklist

1. Save the raw frames or video outside version control (or in approved storage).
2. Create one CSV using the headers in `labels.example.csv`.
3. Keep the camera/model settings as a JSON config file.
4. Validate the CSV against `protocol.json`.
5. Evaluate it and save the output as `metrics.json`.
6. Create a manifest that hashes every evidence file and records the code revision.

Robot Console stores each labeled capture under `experiments/orientation/runs/<run-id>`
with `raw.jpg`, `overlay.jpg`, `prediction.json` and `record.json`. Export only
complete labeled runs to a fresh CSV before evaluation:

```powershell
python tools/export_orientation_runs.py --output experiments/orientation/labels-YYYYMMDD.csv
```

The exporter reports skipped unlabeled/incomplete runs and refuses to overwrite
an existing CSV. Keep these skipped runs in the evidence archive; do not silently
discard failed captures. The `confidence` field from the current pose baseline
is an **uncalibrated heuristic score**, not a probability.

Example commands:

```powershell

py -3 tools\evaluate_orientation.py validate experiments\orientation\run-001\labels.csv --protocol experiments\orientation\protocol.json
py -3 tools\evaluate_orientation.py evaluate experiments\orientation\run-001\labels.csv --protocol experiments\orientation\protocol.json --output experiments\orientation\run-001\metrics.json
py -3 tools\evaluate_orientation.py manifest --protocol experiments\orientation\protocol.json --labels experiments\orientation\run-001\labels.csv --run-id orientation-20260916-001 --artifact raw_frames_or_video=experiments\orientation\run-001\frames.mp4 --artifact config=experiments\orientation\run-001\config.json --artifact metrics_json=experiments\orientation\run-001\metrics.json --output experiments\orientation\run-001\manifest.json
```

`evaluate` reports a `performance_verdict` of `PASS` only when every threshold in the protocol passes, including the minimum total samples and support for every label. A manifest with all required artifacts but no recoverable source snapshot is marked `ARTIFACTS_PRESENT_SOURCE_UNVERIFIED`, not reproducible. Supply `--artifact source_manifest=<run-dir>/manifests/source-code.json` and `--artifact source_archive=<run-dir>/manifests/source-code.zip` from a verified hardware run to get `SOURCE_SNAPSHOT_VERIFIED`. The manifest hashes the evaluator source and marks a Git revision as `+dirty` if uncommitted or untracked changes exist. Record the exact inference model and environment in the config; a verified source archive alone does not prove a model, dependency, or physical experiment can be reproduced. Neither verdict should be replaced by a manual spreadsheet edit.
