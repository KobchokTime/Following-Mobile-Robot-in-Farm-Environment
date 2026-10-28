# Parallel feature workflow for Follower Test Bench

This is the proposed operating contract for Codex, Claude Code, and the virtual office. The office currently offers chat only; its 12 characters are not persistent coding workers. A worker may start only after it has a bounded feature task, its own worktree, and an evidence path.

## Feature lanes

The nine dashboard tabs are views over four independent development lanes, not nine independent code owners.

| Lane | Dashboard tabs | Work area | Initial owner |
| --- | --- | --- | --- |
| Experiment operations | Live tracking, replay, Arena history | run manifests, raw tracks, experiment summaries | Claude's existing runner |
| Following and readiness | Solo following, field readiness | controller, simulation, hardware-day documentation | Codex implementation; separate safety audit |
| Identity and perception | Correct person, shirt colour, filter experiments | identity, colour evidence, perception/fusion | Claude implementation; separate safety audit |
| Evidence and delivery | Tests and CI, dashboard data publication | offline tests, evidence validation, generated dashboard data | Codex implementation; independent review |

One owner edits a shared module at a time. If two lanes need the same controller or fusion file, queue the second change until the first is reviewed and integrated. Each worker uses a feature branch and separate Git worktree based on a recorded base commit. The existing dirty `codex/robot-backup-quarantine` checkout is not a worker worktree.

## Handoff record

Every bounded job should publish one append-only record containing: job ID, lane, owner, branch, base and head commits, start/end times, task statement, changed files, test command and result, raw evidence paths, dashboard metric inputs, open risks, and reviewer verdict. Mark a result `verified` only with raw data, config, code/analysis script, protocol, and metric. A dashboard card must show the record's timestamp and source branch; missing data remains `unknown` rather than showing a stale green state.

Codex and Claude exchange task requests and results through these records and Git branches. Their chat windows are useful for discussion, but a chat assertion alone does not update the test bench. Use the existing `DISCUSSION.md` thread and `HANDOFF.md` lock on `integration-hub` for agree/object and integration. Publish only from a commit that has passed integration review.

Claude confirmed on 28 October 2026 that Follower Test Bench v2 is a single artifact `files/index.html` in the Claude artifact store, with `live_runs`, `live_experiments`, `live_tracks`, `past_tracks`, and `live_scenarios` datasets. The generator `gen.py` and `registry.json` live in that Claude session's scratchpad, not this repository. Claude owns exporting the generator and page to `tools/dashboard/` before parallel tab work can reliably update the same source. Codex cannot directly publish to the Claude artifact store; it prepares reviewed files and data for Claude to publish.

## Run cycle

1. A scheduler checks the queue, worktree status, usage availability, and dependencies.
2. It starts at most one bounded task per lane and caps concurrent model jobs. Each task has a clear acceptance test and deadline.
3. Workers write only in their assigned worktrees. No worker merges its own safety-critical change.
4. A test runner performs offline checks; an independent safety auditor reviews controller, identity switching, timestamp fusion, and motor/bridge paths.
5. The integration role accepts the reviewed branch, records the evidence, and asks Claude to publish the relevant dashboard tab from the merged commit.
6. On usage limits, failed checks, missing evidence, or an approval request, the lane pauses and reports its exact blocker. The scheduler can stay active while model work waits for quota reset.

This cycle uses existing Claude Code and Codex sign-ins. It does not require a paid API key. Plan usage is finite, so a 24/7 scheduler cannot guarantee 24/7 model activity. Local work also requires the PC to remain on and connected.

## Safety boundary

Offline simulation and tests are the default. Do not connect to the robot, enable motor output, bypass confirmation, use an SSH password, or change the fail-closed controller from an unattended job. Preserve the rules in `CLAUDE.md`: stale or uncertain input means zero command; safety cannot silently switch target identity; hardware evidence is append-only and distinct from simulation.

## First pilot

Use two bounded lanes first: Codex handles run provenance and dashboard data validation; Claude continues its lateral-gate experiment and exports its dashboard generator/source. Confirm that both branches can be reviewed and their records can be rendered without overwriting each other. Add the following/identity lanes after that succeeds and usage resets.

Pilot status on 28 October 2026:

- Codex opened draft [PR #3](https://github.com/KobchokTime/Following-Mobile-Robot-in-Farm-Environment/pull/3) to install NumPy for the offline CI check. The pre-fix check failed on an import error; the PR's check job passed.
- Codex opened draft [PR #4](https://github.com/KobchokTime/Following-Mobile-Robot-in-Farm-Environment/pull/4), stacked on #3, to retain per-run score hashes and declared provenance. The runner does not yet write these manifests, so old rows remain `missing`; a complete declaration is not independent image/runtime verification. Retarget #4 to `integration-hub` after #3 lands.
- Claude exported a repository snapshot of the artifact page, dataset records, live generator, and registry in `claude/dashboard/source` at `be8729c`. It is not yet integrated or published from a reviewed repository commit.
- Codex opened draft [PR #5](https://github.com/KobchokTime/Following-Mobile-Robot-in-Farm-Environment/pull/5) against Claude's source branch: a validator for the five live datasets plus an explicit UTF-8 generator fix. Local offline checks passed 147 tests; validation against Claude's completed run folders and artifact publication remain pending.
- The tests/CI tab still uses a 21 October CI snapshot, while the unit-test dataset is from 25 October. Treat these as dated snapshots until a verified update pipeline exists.
