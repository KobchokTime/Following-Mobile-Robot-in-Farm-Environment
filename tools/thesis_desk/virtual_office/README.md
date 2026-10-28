# Virtual Office for the follower project

The scene contains 12 characters and preserves the original desks, camera controls, movement, seating and meeting behavior. Their chat roles now match the follower project. The Team Lead can consult up to three specialists per request. Each browser session and specialist keeps its own conversation state in server memory.

## Run

Use Node.js 20 or newer and a Codex CLI signed in with ChatGPT. No API key is needed. In PowerShell:

```powershell
codex login status
node .\tools\thesis_desk\virtual_office\server.mjs
```

Open `http://127.0.0.1:8765`. Agent requests use your Codex plan allowance and usage limits. The server runs Codex CLI in read-only, ephemeral mode. Team requests consume several Codex turns. Opening `index.html` directly shows the 3D demo, but the agent chat requires the local server. The scene itself loads Three.js from a CDN, so it needs internet access.

This copy of the server has no API-key backend. Set `PORT` before starting the server if 8765 is occupied.

The Team Lead delegates chat calls to specialists. Chat requests answer questions and do not edit repository files. A team request can consume five Codex calls.

## Work queue

`work-queue.json` records three independent dashboard lanes and the next handoff. The page reads it through `GET /api/work-queue` and displays its `recordedAt` timestamp. This is a dated snapshot. Update it only after checking PRs, branch heads and evidence; do not present it as a live status feed. Claude publishes the dashboard artifact after integration.

## Automatic feature jobs

`automation-jobs.json` contains bounded, reviewed tasks assigned to Office
characters. The existing Codex heartbeat checks plan usage and calls the runner
once per cycle when usage is available. The runner creates one isolated local Git
clone per job, caps concurrent Codex processes at three and never starts two jobs from
the same lane. It invokes `codex exec` using the signed-in ChatGPT account,
with a workspace sandbox and no API-key environment variables. Each job has a
15-minute default deadline, an allowed file scope and the offline
`scripts/check.py` gate. A failed or interrupted job is not retried under the
same ID. Branches remain uncommitted and unmerged for review.

The runner stores append-only events and raw local output under the sibling
`office-agent-worktrees/.office-state/` directory by default. Set
`OFFICE_WORKTREE_ROOT` to the same absolute path for the runner and web server
if you want another location. `GET /api/automation` and the Office page show
the latest event for each job. Status is local to this PC; it is not a live
Claude artifact feed.

To inspect the next cycle manually, run
`node tools/thesis_desk/virtual_office/automation-runner.mjs --dry-run`.
The heartbeat sets `OFFICE_USAGE_CHECKED_AT` only after checking Codex's plan
usage, then runs the same command with `--run`. A PC that is off or disconnected
cannot run model jobs. The runner does not contact Claude, push branches,
publish artifacts or use a quota reset.

## Robot project dashboard

The section below the 3D office summarizes the Claude Follower Test Bench that was inspected on 28 October 2026. Its 27/30, 30/30, 27/30 and 120/120 figures are a dated snapshot of simulation and unit-test results, not a live connection to Claude or a hardware result. The criteria tab shows the four pass conditions; the agent tab shows live status only for this local office session. Use the source link in the page for the latest experiment progress.
