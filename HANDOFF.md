# Handoff

Live state of the shared work. Edit this file **only on `integration-hub`**. The rules are in
[`AGENTS.md`](AGENTS.md). Action history lives in `logs/claude.md` and `logs/codex.md`,
and review threads in [`DISCUSSION.md`](DISCUSSION.md).

## Integration lock

- **Current owner:** none
- **Status:** ready
- **Files being edited:** none
- **Last updated:** 2026-10-20 by Claude Code

## Branches

| Branch | State |
|---|---|
| `main` | Initial commit only. It receives `integration-hub` through a PR once the user approves. |
| `integration-hub` | Has everything integrated so far: the robot recovery, Thesis Desk, the quest sources, the agent workflow and the GUI smoke-test results. `scripts/check.py` passes. |
| `claude/workspace` | Same as `integration-hub`. No feature in progress. |
| `codex/workspace` | Same as `integration-hub`. No feature in progress. |
| *To delete* | `integration/robot-thesis-desk`, `codex/robot-backup-quarantine` and `codex/thesis-desk`. They are fully merged, but the cloud session's git proxy cannot delete branches. The user deletes them on GitHub, or Codex runs `git push origin --delete ...` from Windows. |

## Models on `integration-hub`

- Claude Code: Claude Opus 5.5, through the `.claude/agents/integration.md` subagent (`model: opus`).
- Codex: **Sol 6**. *Action for Codex:* set the exact model ID in your own config, then
  confirm it in `DISCUSSION.md` thread T1.

## Open items

1. **T1** in `DISCUSSION.md`: Codex reviews the branch restructure and role setup.
2. Optional UI fixes for the `thesis-desk` role, found in the Xvfb smoke test:
   - The Research Desk dialog ignores ESC and stays open after switching to Test Field.
   - The tracker's top bar overflows a 1440 px wide screen.
3. Not yet verified: rendering on the user's real Windows GPU, and the real robot checks
   (ROS graph, camera, LiDAR, motor, E-stop).
4. `integration-hub` → `main` (draft PR KobchokTime/Following-Mobile-Robot-in-Farm-Environment#2): needs every thread resolved and the user's approval.

## Next step

Codex: sync `codex/workspace` with `integration-hub` and review T1 on `integration-hub` using Sol 6.
Then decide with the user whether to take open item 2 as `codex/thesis-desk/<topic>`.
