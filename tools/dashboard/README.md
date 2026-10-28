# Follower Test Bench dashboard: source and live data

- **Published dashboard:** https://claude.ai/artifact/HTGBVGXXgFjr4S39zD1qA1
  - It is a claude.ai "Dashboard" artifact.
  - The page and the dataset records live in the artifact's own store.
  - The dataset files are uploaded blobs.
- **This folder is the repository copy,** so the work does not depend on one Claude session.

| Path | What it is |
|---|---|
| `index.html` | The page (store document `files/index.html`, version 24 when copied, 2026-10-28). One file holds every tab. |
| `datasets.json` | A snapshot of the store's `datasets/<id>` records: title, description, source (blob URL), `updated`. |
| `live/gen_live.py` | Builds the five live-monitor datasets from twin run folders. |
| `live/registry.json` | The experiments the live tab shows, and the runs each one expects. |

## Who can change what

- **Only Claude can write the published dashboard.** It needs Claude's artifact tools (`ArtifactData`,
  `Artifact` asset upload); Codex has no equivalent.
- **Anyone can change the files here.** Claude publishes from a commit that has been merged into
  `integration-hub`.
- **To publish a page change:**
  1. Edit `index.html` here.
  2. Claude writes it to `files/index.html` with `ArtifactData set`, pinned to the store version it read.
  3. Then check `data/users/me/check` in the store.
- **To publish data:**
  1. Run `gen_live.py`.
  2. Claude uploads each output as an asset.
  3. Then one `ArtifactData update` points `datasets/<id>.source.url` at it, and old blobs are deleted.

## Making the live data

```sh
python3 tools/dashboard/live/gen_live.py --runs-root <dir> --out <out_dir>
```

- `--runs-root` is the folder that each registry `dir` is relative to. Claude's session used its
  scratchpad, which is not in the repository; the twin run folders are too big to commit.
- **Run folders** are written by `python3 -m sim.twin.run_scenario --out sim_runs/<tag>`, inside the
  `sim/docker` image. Each has `<tag>/<scenario>_mps/{world.log, score.json, state.jsonl, *.log}`.
- **A run's status:**
  - `pass` / `fail` once `score.json` exists, using the pass rule below;
  - `running` while only `world.log` exists;
  - `queued` otherwise.
- **Pass rule:** `target_in_camera_fov_end` and `final_gap_m <= 1.5` and not `contact` and
  `target_visible_share >= 0.9`. It is the same rule as `experiments/sim/scripts/collect_runs.py`.

## Schema

All times are UTC ISO 8601 (`YYYY-MM-DDTHH:MM:SSZ`). The page shows them in Thai time.

### `live/registry.json`: a list of experiments

| Field | Type | Meaning |
|---|---|---|
| `id` | str | Unique, `[a-z0-9_]` |
| `title` | str | Thai title shown on the page |
| `code` | str | Commit or branch the runs used |
| `dir` | str | Run folder, relative to `--runs-root` |
| `started_utc` | str | When the experiment started (used for the ETA) |
| `order` | int | Higher numbers are newer; the page lists them newest first |
| `live` | bool | At most one experiment is `true`. Its tracks go in `live_tracks` at 2 Hz; the others go in `past_tracks` at 1 Hz |
| `purpose`, `compare`, `result` | str | Thai text for the "การทดลองนี้ทดสอบอะไร" card; `result` is empty until written |
| `stopped` | bool, optional | Marks an abandoned experiment |
| `runs` | list | `{tag, scenario, seed, variant, light}`: `tag` is the run folder; `variant` and `light` (`ปกติ` / `สมจริง`) group the grid |

- Set names such as `identity` or `solo` are expanded to one entry per scenario (`sim.twin.scenarios.SCENARIO_SETS`).
- `(tag, scenario)` must be unique within an experiment.

### `live_experiments.json`: one row per experiment

- **Copied from the registry:** `experiment` (= `id`), `title`, `code`, `order`, `started_utc`, `purpose`,
  `compare`, `result`.
- **Counts (int):**
  - `total` = number of expected runs;
  - `done` = `passed` + `failed`;
  - `running`.
- **Status and timing:**
  - `status`: `queued` | `running` | `done` | `stopped`;
  - `last_finished_utc`: str, or null;
  - `eta_min`: float minutes, or null when the experiment is done or has no finished run yet;
  - `checked_utc`: when the file was made.

### `live_runs.json`: one row per expected run

| Field | Type | Meaning |
|---|---|---|
| `run` | str | `<experiment>|<tag>|<scenario>`; unique, used as the table's row key |
| `experiment`, `scenario`, `seed`, `variant`, `light` | | From the registry |
| `status` | str | `queued` \| `running` \| `pass` \| `fail` |
| `final_gap_m` | float \| null | Rounded to 0.01 |
| `visible_share` | float \| null | 0–1, rounded to 0.001 |
| `contact`, `in_view_end` | bool \| null | |
| `max_bearing_deg` | float \| null | Peak absolute target bearing |
| `published`, `published_other` | int \| null | `/synced_target` publications and how many were another person's box. Only runs on code with `world_node`'s attribution (`claude/robot/lateral-gate-2`) have them |
| `started_utc`, `finished_utc` | str \| null | From the mtimes of `world.log` and `score.json` |

- **Null rules:**
  - every score field is null unless `status` is `pass` or `fail`;
  - `started_utc` is null for a queued run;
  - `finished_utc` is null unless the run is done.

### `live_tracks.json` and `past_tracks.json`: positions for the replay

- **One row per sample.** `live_tracks` is at 2 Hz; `past_tracks` is at 1 Hz.
- **Fields:** `run` (as above), `t` (s), and robot pose `rx`, `ry` (m, world frame), `ryaw` (deg) and `v`
  (m/s).
- **Target:** `tx`, `ty`, `gap` (m, range − 0.2) and `tb` (deg). All four are null if the target is not in
  the state.
- **First other person:** `ox`, `oy`, or null.
- **Size limit:** each file must stay under 8 MB (the dashboard's limit). `past_tracks` is the one to
  watch.

### `live_scenarios.json`: one row per scenario used by any experiment

- **Fields:**
  - `scenario`;
  - `doc` (Thai);
  - `duration_s`;
  - `people` (count);
  - `paths`: a JSON string of `[{name, target, wp: [[t, x, y], ...]}]`;
  - `notes`: a JSON string of `{blackouts, hidden, shade, clothing}`.
- **When the checked-out code lacks the scenario,** `paths` is `"[]"` and `duration_s` is null.

## Splitting the page by tab (planned)

- `index.html` is one file, so two people editing different tabs would conflict.
- The plan:
  - move each tab's drawing code into `tabs/<tab>.js`;
  - the dashboard type loads `<script src>` from other `files/<name>` documents;
  - then each tab can have its own owner and branch.
