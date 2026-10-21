# Codex Arena 3 entry

- **Base:** frozen rules at `08a7ac8` (`arena: freeze Arena 3 rules and scorer`).
- **Change:** `sync_fusion_node.py` locks onto a person in the existing 0.5–1.0 m initial range,
  then gates detections by camera bearing and LiDAR range continuity. When clothing chroma is
  present, it also rejects a large Cb/Cr mismatch. Chroma is smoothed after accepted matches.
- **Compatibility:** detection parsing keeps `[cx, cy, sector]` messages valid and reads optional
  `cb, cr` only when both extra values are present. Target selection is in the shared fusion path
  used by the twin and robot; it does not rely on `ros2_yolo_live.py` for selection.
- **Tests:** `tests/test_target_selection.py` covers initial lock, geometry association, chroma
  mismatch, shade shift, and legacy/extended detection formats. `python3 scripts/check.py` passed.
- **Full protocol not run:** the root overlay has 0 bytes available and Docker's data root is on
  that full filesystem; this Python environment also has no `rclpy` installation for running the
  twin directly. No twin or Gazebo scores are claimed; the judge must run the full protocol.
