# Arena 2 entry — Codex

**Branch:** `codex/robot/arena2-lag`  
**Frozen base:** `9b78f1f`  
**Scope:** `ros2_yolo_ws/scripts/MAIN/Control/follow_stop_node.py` and its offline regression test.

Raised the Follow-Stop `linear_gain` default from `0.55` to `5.0`. The existing proportional law
then asks for enough forward command to reach the bridge's existing 40 RPM cap as the target pulls
away, reducing the controller's low-speed steady-state lag. The drive bridge and its conversion
remain unchanged. Added an offline test asserting a confident target at 0.8 m produces the expected
0.9 linear command.

`python3 scripts/check.py` passed all 43 tests. I could not run the three-seed twin or two Gazebo
protocol: Docker image build failed while copying the robot scripts with `no space left on device`.
There is no self-score; the integration judge should run the frozen protocol after both entries are
submitted.
