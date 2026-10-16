# Following Mobile Robot in Farm Environment

Recovered research code and experimental evidence for a ROS 2 person-following
mobile robot using monocular vision and 2D LiDAR.

The first recovery commit intentionally contains only files that can be inspected
without importing generated environments or known-corrupt workspaces. See
[`quarantine/BACKUP_AUDIT.md`](quarantine/BACKUP_AUDIT.md) for the backup audit,
excluded paths, validation results, and release conditions.

## Offline validation

Run the recovery checks without ROS 2 or robot hardware:

```bash
python -m compileall -q ros2_yolo_ws/scripts tests
python -m unittest discover -s tests -v
```

The suite validates Python syntax, expected ROS topic wiring, the recovered CSV,
the OpenVINO export, and Follow-Stop controller behavior using safe message/ROS stubs.
Real ROS graph, camera, LiDAR, serial motor, and emergency-stop tests must still run
on the target Ubuntu/ROS 2 system before hardware operation.

## Thesis Desk

A local desktop quest tracker and Godot simulation prototype for managing the research workflow is available in [`tools/thesis_desk/`](tools/thesis_desk/README.md). Its robot tests are simulations and do not issue hardware commands.

## Working with AI agents

Claude Code and Codex share this repository. Read [`AGENTS.md`](AGENTS.md) for the rules and
[`HANDOFF.md`](HANDOFF.md) for the current state before starting work.
