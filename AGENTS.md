# Agent Guide (Codex + Claude Code)

This repository is worked on by **Codex** and **Claude Code**, sometimes one after the
other on the same day. Both read this file (`CLAUDE.md` points here). Follow it so either
agent can pick up the work at any moment without asking what happened.

## Repository map

| Path | What it is |
|---|---|
| `ros2_yolo_ws/scripts/` | Recovered ROS 2 robot code: YOLO detection, LiDAR fusion, Follow-Stop controller, ZLAC motor bridge |
| `yolov8n_openvino_model/` | OpenVINO export of YOLOv8n |
| `tests/` | Offline tests with ROS/message stubs (no hardware) |
| `quarantine/BACKUP_AUDIT.md` | What was recovered from the backup, what was excluded and why |
| `tools/thesis_desk/` | Thesis quest tracker (Tkinter) and Godot 3D simulation game |
| `scripts/check.py` | The one command every agent runs before handing off |
| `HANDOFF.md` | **Live state**: who is working, what is in progress, what is next |

## Branch model

- `main` stays stable. Merge to it only when the user asks.
- `integration/robot-thesis-desk` is the shared working branch. Both agents start here.
- Feature work goes on a short-lived branch cut from the integration branch:
  - Codex: `codex/<topic>`
  - Claude Code: `claude/<topic>`
- Merge back into the integration branch with a merge commit (`--no-ff`). Never rebase,
  amend or force-push a branch the other agent may have pulled.
- Always `git fetch origin` and `git pull` before starting. The other agent may have pushed.

## Handoff protocol

**Start of a session**
1. `git fetch origin && git checkout integration/robot-thesis-desk && git pull`
2. Read `HANDOFF.md`. If *Current owner* is the other agent and *Status* is `in-progress`,
   do not touch the files listed under *Files being edited*. Ask the user first.
3. Set *Current owner* to yourself, *Status* to `in-progress`, commit
   (`handoff: claim <topic>`) and push. This is the lock. It lives in git, not on disk,
   so both agents can see it.

**During work**
- Keep `HANDOFF.md` current as work progresses. Log meaningful changes, decisions, checks and results, blockers, and the exact next step so the other agent can continue without relying on chat history.
- Commit small and often, and push every commit. Unpushed work cannot be handed off.
- Commit messages: imperative subject line. Prefix it with the area when that helps,
  for example `thesis-desk: ...`, `robot: ...`, `tests: ...`.

**End of a session, or whenever you might be interrupted**
1. Run `py -3 scripts/check.py` (Windows) or `python3 scripts/check.py`. It must exit 0.
2. Update `HANDOFF.md`: what you did, what is unfinished, the exact next step, and any
   check you could not run (for example Godot or real hardware).
3. Set *Status* to `ready` (anyone may continue) or `blocked` (with the reason).
4. Commit (`handoff: <summary>`) and push.

If a session ends without step 3, the next agent treats the claim as stale when the last
`handoff:` commit is more than 24 hours old, and notes that it took over.

## Safety rules (do not break)

- Never send motor or serial commands from tests or tools. Thesis Desk and the tests are
  simulation/read-only by design. Keep them that way.
- Do not move anything out of `quarantine/` scope or commit excluded workspaces
  (see `.gitignore` and `quarantine/BACKUP_AUDIT.md`).
- Do not commit large recordings (`*.bag`, `*.db3`, `*.mp4`) or secrets (`.env`).
- Never skip, disable or delete a failing test to get `scripts/check.py` green.

## Environment notes

- Codex usually runs on the user's Windows machine. It can run Godot (`tools/thesis_desk/.tools/godot/`,
  not in git) and Tkinter, and it can see local files that are not in the repo.
- Claude Code may run in a headless Linux cloud container. It cannot open GUI apps or
  Windows paths. Anything only on the Windows machine has to be committed before Claude can use it.
- Real ROS graph, camera, LiDAR, motor and E-stop checks happen only on the robot's
  Ubuntu/ROS 2 system, by the user.
