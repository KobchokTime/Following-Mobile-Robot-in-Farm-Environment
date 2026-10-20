# Codex — Arena 1: sector association

**Branch:** `codex/robot/arena-sector-association` from frozen base `d623baf`.

## Change

- Widened LiDAR sectorization from ±15° to ±35° to cover the camera's 70° horizontal field of view.
- Reversed distance, variance and angle arrays so sector indices follow camera image order (left to right).
- Started the existing edge turn at sector 2/6 rather than treating those sectors as straight ahead; one consistent observation is enough to issue a turn. This lets the follower react before its edge confidence falls below its movement threshold.
- Added offline tests for left/right LiDAR association and the early turn response.

## Arena result

Scored with seed 0 after running every scenario with both bridge modes: **99.44 / 100**.

- `curve_left` / `diff_drive`: turned, target remained in camera FOV, final gap **0.584 m**.
- No regression checks failed; no contact in any run and `target_loss` stop latency was **1.00 s** for both bridge modes.
- The initial sector-only change did not turn early enough. The controller edge threshold was then reduced; a targeted rerun and the full suite produced the result above.

The twin image was built with `INSTALL_MCAP=0` because package repositories were unreachable; MCAP is only needed for bag replay, not this run.

## Rules and fairness review

The fixed scenarios and common frozen base make this a repeatable internal comparison. I have no blocking objection to using these rules for this round. The score uses one deterministic seed and one turn scenario, so it is evidence about this task rather than a broad measure of agent quality. The judge should regenerate the summary for both entries, run the scorer independently, inspect the full changed-path list with rename detection disabled, and manually confirm the drive bridge was untouched. Those checks address the scorer's single-seed and scope-check limits without changing frozen rules mid-round.
