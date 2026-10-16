# Handoff

Live state shared by Codex and Claude Code. The protocol is in [`AGENTS.md`](AGENTS.md).
Update this file at the end of every session.

## Current

- **Current owner:** Codex
- **Status:** in-progress
- **Branch:** `integration/robot-thesis-desk`
- **Files being edited:** HANDOFF.md; eight quest-source files; Thesis Desk seed data
- **Last updated:** 2026-10-16 by Codex

## Last session — Claude Code, 2026-10-16

Done:
- Created `integration/robot-thesis-desk` from `main` and merged
  `codex/robot-backup-quarantine` and `codex/thesis-desk` into it (merge commits, history kept).
- Resolved the only conflict, `README.md`. It keeps the recovery README and adds a Thesis Desk section.
- Added `AGENTS.md`, `CLAUDE.md`, `HANDOFF.md` and `scripts/check.py`.
- Un-ignored `tools/thesis_desk/.vscode/`, which the robot branch's `.vscode/` rule would otherwise hide.
- `scripts/check.py`: compile passes, `thesis_data.json` is valid (18 tasks), 8/8 tests pass.

Not verified (needs the Windows machine):
- Thesis Desk Tkinter app and the Godot game were not launched. The cloud container has no display or Godot.

## Open items

1. **Missing quest sources (needs Codex or the user on Windows).** `thesis_data.json` cites
   8 files that exist only on the local machine. Commit them so the quest links work.
   `scripts/check.py` lists them as `[WARN]`:
   - `docs/EXECUTION_WORKFLOW.md`
   - `docs/MOTION_SAFETY_GATE.md`
   - `config/motor_wheel_calibration.md`
   - `experiments/camera/2026-09-20_camera_only_start.md`
   - `experiments/hardware/2026-09-20_connected_runtime_validation.md`
   - `experiments/identity/README.md`
   - `experiments/orientation/README.md`
   - `src/following_robot/target_identity.py`
2. **Smoke-test on Windows (Codex).** Run `run_thesis_tracker.bat` and `run_3d_game.bat` from
   this branch and note the result here.
3. **Merge to `main`.** Only once the user approves.

## Next step

Codex: pull this branch, do open items 1 and 2, then update this file.
