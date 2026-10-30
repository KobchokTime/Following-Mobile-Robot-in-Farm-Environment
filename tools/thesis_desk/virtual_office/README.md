# Virtual Office for the follower project

The scene contains 12 characters and preserves the original desks, camera controls, movement, seating and meeting behavior. Their chat roles now match the follower project. The Team Lead can consult up to three specialists per request. Each browser session and specialist keeps its own conversation state in server memory.

## Run

Use Node.js 20 or newer and a Codex CLI signed in with ChatGPT. No API key is needed. In PowerShell:

```powershell
codex login status
node .\tools\thesis_desk\virtual_office\server.mjs
```

Open `http://127.0.0.1:8765`. Agent requests use your Codex plan allowance and usage limits. Chat and meetings run Codex CLI in read-only, ephemeral mode; coding jobs are prepared for native Codex agents in separate clones. Team requests consume several Codex turns. Opening `index.html` directly shows the 3D demo, but agent actions require the local server. The scene itself loads Three.js from a CDN, so it needs internet access.

This copy of the server has no API-key backend. Set `PORT` before starting the server if 8765 is occupied.
The local server accepts requests only with a `127.0.0.1:<port>` or `localhost:<port>` Host.
POST requests must use `Content-Type: application/json` and, when an Origin is present, it must
match that Host. This prevents other websites from starting local agent work through the browser.

## Office controls that run work

- **พักผ่อน** toggles a continuous walk along the clear front aisle for agents who are idle according to the server. Agents assigned to desk work, a meeting or direct chat stay at their work position. When their task ends, they can join the break automatically while the toggle remains on in that browser tab. Meeting participants sit at the meeting table until their recorded meeting ends. The scene is restored from the server's running state after a reload.
- **จัดเข้าที่นั่ง · แก้โค้ด** prepares the first ready, bounded writing task assigned to an idle desk agent in `automation-jobs.json`. The server creates a separate local clone and branch and records an `assigned` event. The Codex heartbeat reads `automation-queue.mjs --pending`, starts a native Codex subagent in that checkout, and then calls `--finish --job ID`. The Office page keeps the character at the desk while the assignment is pending or running, and shows the branch, changed files, Python check and focused Node results when verification finishes. The button does not run a nested Codex CLI: on this host that child process is forced to read-only even when asked for `workspace-write`. A click can therefore wait until the next heartbeat, and a stopped PC cannot progress the assignment. Each catalog job is started once; add a new reviewed, scoped job for a later click. No API key, quota reset, commit, push, merge or hardware command is part of the button.
- **เริ่มประชุม** selects up to three agents who are not in a running Office work or meeting round. Participants take turns proposing, challenging and refining a plan using the same plan-authenticated Codex CLI. Meeting turns and the final proposal are recorded in `office-actions.jsonl` and shown on the page. The next meeting rotates to another idle group. A proposal is not an executed code change.

These buttons do not silently commit, push, merge or send hardware commands. A seat click assigns an isolated clone; a native agent makes any edits and the result remains for review. The page reports `running`, `completed`, `failed`, `paused` or `interrupted` from recorded events instead of treating a character animation as evidence of work. Restarting the server marks an unfinished round interrupted; the clone and check logs remain available for inspection.
Office chat and meeting turns are serialized for the single included-plan account. The Codex heartbeat checks included-plan usage before starting a queued coding assignment; a 429 pauses further model work.

The Team Lead delegates chat calls to specialists. Chat requests answer questions and do not edit repository files. A team request can consume five Codex calls.
If Codex returns a 429 limit response, the server pauses new chat requests and
shows the limit in the Office panel. Restart the server after included plan usage
becomes available again. The server never falls back to an API key.

## Work queue

`work-queue.json` records three independent dashboard lanes and the next handoff. The page reads it through `GET /api/work-queue` and displays its `recordedAt` timestamp. This is a dated snapshot. Update it only after checking PRs, branch heads and evidence; do not present it as a live status feed. Claude publishes the dashboard artifact after integration.

## Automatic feature jobs

`automation-jobs.json` contains bounded tasks assigned to Office characters.
The existing Codex heartbeat checks plan usage, then calls
`automation-queue.mjs --prepare`. This creates one isolated local Git clone
per job, with at most three active jobs and one job per lane. The heartbeat
starts native Codex subagents in those clones using the signed-in ChatGPT plan.
After a subagent finishes, `automation-queue.mjs --finish --job ID` verifies
the allowed file scope, unchanged base commit and offline `scripts/check.py`
gate. Jobs with `focusedNodeTests` must pass those Node tests as well. A failed
check or missing check executable is recorded as failed, and `--finish` can
recheck the same clone after repair. The result remains for independent review; no branch is committed,
pushed or merged by the queue.
Read-only assignments require zero changed files to become review-ready; writing assignments
require at least one changed file within their allowed paths.

The queue stores append-only events under the sibling
`office-agent-worktrees/.office-state/` directory by default. Set
`OFFICE_WORKTREE_ROOT` to the same absolute path for the runner and web server
if you want another location. `GET /api/automation` and the Office page show
the latest event for each job. Status is local to this PC; it is not a live
Claude artifact feed.

To inspect the next cycle manually, run
`node tools/thesis_desk/virtual_office/automation-queue.mjs --dry-run`.
The heartbeat sets `OFFICE_USAGE_CHECKED_AT` only after checking Codex's
plan usage. A PC that is off or disconnected cannot run model jobs. The queue
does not call an API, contact Claude, publish artifacts or use a quota reset.

## Robot project dashboard

The section below the 3D office summarizes the Claude Follower Test Bench that was inspected on 28 October 2026. Its 27/30, 30/30, 27/30 and 120/120 figures are a dated snapshot of simulation and unit-test results, not a live connection to Claude or a hardware result. The criteria tab shows the four pass conditions; the agent tab shows live status only for this local office session. Use the source link in the page for the latest experiment progress.
