# Gate-decision traces for `side_step` (T14)

- **Code:** `d23e7b2`, with `make_debug_build.py` applied. The patch only adds logging.
- **Run:** `side_step` with realism, seeds 10 and 12. `true` means box ranges on, `false` means off.
- **Files:**
  - `*_gate.log` holds one line per camera box: time (s, wall clock), bearing `b` (deg), the range
    used `d`, the sector median `sec`, the predicted bearing and range `pb`/`pr`, the gate cost and
    `ok`;
  - `lidar-track` lines mark LiDAR out-of-view fixes;
  - `*_score.json` is the twin score.
- **Read with:** `experiments/sim/2026-10-27_box_range.md`, section "side_step with box ranges on vs off".
