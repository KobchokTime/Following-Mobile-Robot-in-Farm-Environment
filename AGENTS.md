# Agent Guide (Codex + Claude Code)

This repository is worked on by **Codex** and **Claude Code**. Both read this file
(`CLAUDE.md` points here). Follow it so either agent can pick up the work at any moment,
and so each one can see and re-check what the other did.

## Repository map

| Path | What it is |
|---|---|
| `ros2_yolo_ws/scripts/`, `src/following_robot/` | Robot code: YOLO detection, LiDAR fusion, target identity, Follow-Stop controller, ZLAC motor bridge |
| `yolov8n_openvino_model/` | OpenVINO export of YOLOv8n |
| `tools/thesis_desk/` | Thesis quest tracker (Tkinter) and Godot 3D simulation game |
| `docs/`, `experiments/`, `config/` | Protocols, experiment evidence, calibration notes |
| `tests/`, `scripts/check.py` | Offline tests and the one check every agent runs before merging |
| `quarantine/BACKUP_AUDIT.md` | What was recovered from the backup, what was excluded and why |
| `agents/roles/` | Role definitions shared by both agents (see *Roles*) |
| `logs/claude.md`, `logs/codex.md` | Append-only action log, one per agent |
| `HANDOFF.md` | Live state of the `integration-hub` branch and both workspaces |
| `DISCUSSION.md` | Cross-check threads between Claude and Codex |

## Branches

There are four long-lived branches:

| Branch | Owner | Purpose |
|---|---|---|
| `main` | User | The main, stable line. Only `integration-hub` merges into it, through a PR the user approves. |
| `claude/workspace` | Claude Code | Claude's base for developing features. |
| `codex/workspace` | Codex | Codex's base for developing features. |
| `integration-hub` | Both | Where features from both workspaces are combined and tested, and where Claude and Codex discuss and re-check each other's work. |

```
claude/<role>/<topic> ──► claude/workspace ──┐
                                             ├──► integration-hub ──(user approves)──► main
codex/<role>/<topic>  ──► codex/workspace  ──┘
```

Rules:
- Feature branches are short-lived. Name them `<agent>/<role>/<topic>`, cut them from your own
  workspace, and merge them back into it with `--no-ff`.
- Never commit to the other agent's workspace or its feature branches. Leave feedback in
  `DISCUSSION.md` on `integration-hub` instead.
- Start every session by syncing: `git fetch origin`, then merge `origin/integration-hub` into
  your workspace, so you build on what the other agent already integrated.
- Merge commits only. Never rebase, amend or force-push a shared branch.

## Models

| Where | Claude Code | Codex |
|---|---|---|
| `integration-hub` (combine, test, cross-check) | **Claude Opus 5.5**. The `integration` role agent in `.claude/agents/integration.md` sets it. | **Sol 6**, set in Codex's own config. Codex fills in the exact model ID; see `HANDOFF.md`. |
| Workspaces | The session's default model | The session's default model |

## Roles

Each agent splits its work by role. Every role has its own file in `agents/roles/`, which gives
its scope (the paths it may change), its checks, and its definition of done. Both agents use
the same role names, so a feature from either side is reviewed against the same rules.

| Role | Scope | File |
|---|---|---|
| `robot` | `ros2_yolo_ws/`, `src/following_robot/`, `yolov8n_openvino_model/` | `agents/roles/robot.md` |
| `thesis-desk` | `tools/thesis_desk/` | `agents/roles/thesis-desk.md` |
| `research` | `docs/`, `experiments/`, `config/` | `agents/roles/research.md` |
| `qa` | `tests/`, `scripts/` | `agents/roles/qa.md` |
| `integration` | Merging into `integration-hub`, cross-review, `HANDOFF.md`, `DISCUSSION.md` | `agents/roles/integration.md` |

- **Claude Code**: each role is a subagent in `.claude/agents/<role>.md`. Delegate to the
  matching subagent, or follow its role file yourself.
- **Codex**: before working as a role, read `agents/roles/<role>.md` and stay within its scope.
- A change that needs more than one role is split into one feature branch per role.

## Workflow

**1. Develop (in your workspace)**
1. Sync your workspace with `integration-hub` (see *Branches*).
2. Cut `<agent>/<role>/<topic>` from your workspace. Work within the role's scope.
3. Run `py -3 scripts/check.py` (Windows) or `python3 scripts/check.py`. It must exit 0.
4. Merge the feature into your workspace (`--no-ff`) and push. Log it in `logs/<agent>.md`.

**2. Integrate (on `integration-hub`, with the integration model)**
1. Read `HANDOFF.md`. If the other agent holds the integration lock (*Status* `in-progress`),
   wait or ask the user. Otherwise claim it: set yourself as owner and commit
   `handoff: claim <topic>`, then push.
2. Merge your workspace into `integration-hub` (`--no-ff`). Run `scripts/check.py`.
3. Open a thread in `DISCUSSION.md` asking the other agent to review it. Say what changed, how
   you tested it, and what you are unsure about.
4. Update `HANDOFF.md`, release the lock (`ready`), then push.

**3. Cross-check (the other agent, on `integration-hub`)**
1. Review the diff of every thread marked `open` for you. Re-run `scripts/check.py` and any
   relevant manual checks.
2. Reply in the thread with `agree`, `change requested` (with reasons), or `question`.
   Fix problems in your own workspace, never in the other agent's.
3. A thread is `resolved` only when both agents agree. `integration-hub` may go to `main` only
   when no thread is `open` and the user approves.

**Logging (always)**
- Log every action in your own `logs/<agent>.md`: commits, merges, branches, pull requests,
  reviews, discussions and checks you ran or could not run. Include actions outside git,
  such as opening a PR. Append at the bottom. Each agent edits only its own log, so logs never
  conflict when branches merge. `logs/history-2026-10-16.md` is the shared log from before this split.
- Entry format: `### YYYY-MM-DD — <role> — <short title>` then bullets: what, where
  (branch / commit / PR), result, and follow-ups.
- `HANDOFF.md` and `DISCUSSION.md` are edited **only on `integration-hub`**.

If a lock is older than 24 hours with no new `handoff:` commit, treat it as stale, note that
you took over, and continue.

## Communication

- Do not bring up safety-related topics unless the user asks.

## Repository rules

- Do not move anything out of `quarantine/` scope or commit excluded workspaces
  (see `.gitignore` and `quarantine/BACKUP_AUDIT.md`).
- Do not commit large recordings (`*.bag`, `*.db3`, `*.mp4`) or secrets (`.env`).
- Never skip, disable or delete a failing test to get `scripts/check.py` green.

## Environment notes

- Codex usually runs on the user's Windows machine. It can run Godot (`tools/thesis_desk/.tools/godot/`,
  not in git) and Tkinter, and it can see local files that are not in the repo.
- Claude Code may run in a headless Linux cloud container. It can smoke-test GUI apps under Xvfb
  (see `logs/history-2026-10-16.md`), but it cannot reach Windows paths. Anything that exists only
  on the Windows machine has to be committed before Claude can use it.
- Real ROS graph, camera, LiDAR and motor checks happen only on the robot's Ubuntu/ROS 2 system,
  by the user.
