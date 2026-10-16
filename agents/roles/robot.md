# Role: robot

**Scope (may change):** `ros2_yolo_ws/`, `src/following_robot/`, `yolov8n_openvino_model/`.
Needs another role for: tests (`qa`) and experiment write-ups (`research`).

**Responsibilities:** perception (YOLO/OpenVINO, orientation, target identity), LiDAR fusion,
Follow-Stop control logic, and the ZLAC motor bridge.

**Rules**
- Code must still import and run offline with the stubs in `tests/`. Do not add hard
  dependencies on ROS 2 or hardware at import time.
- Any change to motion or control is gated by `docs/MOTION_SAFETY_GATE.md`. The default stays
  disarmed, with zero velocity when the target is lost.
- Never send motor or serial commands from this repo's tests or tools.

**Done when:** `scripts/check.py` passes, behavior changes have a test (ask `qa`), and the
log entry says what still needs testing on the real robot.
