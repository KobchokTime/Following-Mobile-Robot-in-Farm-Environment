# Robot backup quarantine

Audit date: 2026-07-22

This manifest keeps the recovered robot backup visible without committing broken,
generated, unrelated, or oversized content. Nothing listed here was deleted from the
local backup.

## Included in the recovery branch

- `ros2_yolo_ws/scripts/`: 29 Python programs passed syntax parsing.
- `ros2_yolo_ws/scripts/log/synced_20251111_123335.csv`: readable experiment data
  with 3,528 rows.
- `yolov8n_openvino_model/`: exported YOLOv8n OpenVINO model and metadata.

## Quarantined locally

| Path | Reason | Release condition |
| --- | --- | --- |
| `ros2_rplidar_ws/` | Embedded Git repository points to `saintwings/ros2_rplidar_ws`; 46 source files are zero bytes and its working tree reports 63 modified/deleted files. | Recover zero-byte files, remove generated artifacts, build on the target ROS 2 system, and import it without nested Git metadata. |
| `openvino_env/` | Re-creatable Python environment, approximately 3.6 GB. | Replace with a dependency lock or installation instructions. |
| `ros2_ws_OLD/`, `ydlidar_ros2_ws_OLD/` | Historical workspaces with generated output and unclear authority. | Compare against the active workspace and retain only unique source/configuration. |
| `rplidar_ws/`, `ydlidar_ws/` | Mostly generated ROS build/install/log artifacts. | Recover source-only packages if they are still required. |
| `YDLidar-SDK/`, `ydlidar_ros2_driver-master/` | Vendor source/build copies without pinned provenance. | Record upstream URL and version; use a submodule or dependency documentation if needed. |
| `dashboard/` | Separate website repository with its own Git history. | Keep published independently. |
| `Aerothai/` | Unrelated project backup. | Move to its own repository. |
| videos and ROS bags | Large binary evidence files. | Store in release/object storage with an index and checksum, not normal Git history. |

## Validation performed

- Python syntax parsing: 29 passed, 0 failed.
- Experiment CSV schema: `cx, cy, dist_m, sector, dt_ms, stamp`.
- CSV audit: mean synchronization delay 49.09 ms, median 49.19 ms,
  p95 91.62 ms, and `cx`/sector Pearson correlation 0.9727.
- Full ROS 2 build/run was not possible on this Windows host because WSL 2 and
  hardware virtualization are disabled.

Treat all recovered results as historical evidence until raw-data provenance,
configuration, and a reproducible analysis command are documented.

