import { spawn, spawnSync } from "node:child_process";
import { appendFile, mkdir, open, readFile, unlink, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "../../..");
const queueFile = join(here, "automation-jobs.json");
const worktreeRoot = resolve(process.env.OFFICE_WORKTREE_ROOT || join(dirname(repo), "office-agent-worktrees"));
const stateDir = join(worktreeRoot, ".office-state");
const eventsFile = join(stateDir, "events.jsonl");
const lockFile = join(stateDir, "runner.lock");
const maxOutput = 128_000;
let worktreeChain = Promise.resolve();
let eventChain = Promise.resolve();

export function selectJobs(jobs, events, limit = 3) {
  const seen = new Set(events.map((event) => event.jobId));
  const lanes = new Set();
  const cap = Math.max(0, Math.min(Number(limit) || 0, 3));
  return jobs.filter((job) => {
    if (!job.ready || seen.has(job.id) || lanes.has(job.lane) || lanes.size >= cap) return false;
    lanes.add(job.lane);
    return true;
  });
}

export function changedPathsAllowed(paths, allowedPaths) {
  return paths.every((path) => {
    const normalized = path.replaceAll("\\", "/");
    return !isAbsolute(path) && !normalized.split("/").includes("..") &&
      allowedPaths.some((prefix) => normalized.startsWith(prefix));
  });
}

function assertJob(job) {
  if (!/^[a-z0-9][a-z0-9-]{2,50}$/.test(job.id) ||
      !/^[a-z0-9][a-z0-9-]{2,50}$/.test(job.lane) ||
      !/^[a-z]+$/.test(job.agent) ||
      !["read-only", "workspace-write"].includes(job.mode) ||
      !Array.isArray(job.allowedPaths) || !job.allowedPaths.length ||
      job.allowedPaths.some((path) => !/^[a-z0-9_/-]+\/$/.test(path) || path.includes("..")) ||
      typeof job.task !== "string" || job.task.length < 30 || job.task.length > 5000 ||
      typeof job.acceptance !== "string" || job.acceptance.length < 15 ||
      !/^codex\/[a-z0-9/-]+$/.test(job.branchPrefix)) {
    throw new Error(`Invalid job: ${job.id || "unknown"}`);
  }
}

function modelEnvironment(tempDir) {
  const env = { ...process.env };
  for (const key of Object.keys(env)) {
    if (/^(OPENAI_|AZURE_OPENAI_|ANTHROPIC_|CODEX_API_KEY$)/i.test(key)) delete env[key];
  }
  if (tempDir) Object.assign(env, { TEMP: tempDir, TMP: tempDir, TMPDIR: tempDir });
  return env;
}

async function run(command, args, { cwd = repo, input = "", timeoutMs = 60_000, env = process.env } = {}) {
  return new Promise((done, fail) => {
    const child = spawn(command, args, { cwd, env, windowsHide: true, stdio: ["pipe", "pipe", "pipe"] });
    let stdout = "", stderr = "", timedOut = false;
    const timer = setTimeout(() => { timedOut = true; child.kill(); }, timeoutMs);
    child.stdout.on("data", (chunk) => { stdout = (stdout + chunk).slice(-maxOutput); });
    child.stderr.on("data", (chunk) => { stderr = (stderr + chunk).slice(-maxOutput); });
    child.on("error", (error) => { clearTimeout(timer); fail(error); });
    child.on("close", (code) => {
      clearTimeout(timer);
      done({ code, stdout, stderr, timedOut });
    });
    child.stdin.end(input);
  });
}

async function git(args, cwd = repo) {
  const result = await run("git", args, { cwd });
  if (result.code !== 0) throw new Error(`git ${args[0]} failed: ${result.stderr.slice(-1000)}`);
  return result.stdout.trim();
}

async function record(event) {
  const next = eventChain.then(() => appendFile(
    eventsFile, JSON.stringify({ at: new Date().toISOString(), ...event }) + "\n", "utf8",
  ));
  eventChain = next.catch(() => {});
  await next;
}

async function loadEvents() {
  try {
    return (await readFile(eventsFile, "utf8")).split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }
}

function promptFor(job, baseCommit, branch) {
  return `You are ${job.agent}, an Office specialist working on one bounded feature.
Task: ${job.task}
Acceptance: ${job.acceptance}
Assigned branch: ${branch}; base commit: ${baseCommit}.
Allowed changed paths: ${job.allowedPaths.join(", ")}.
Work only in this assigned worktree. Read AGENTS.md and the matching role file.
Do not edit outside allowed paths. Do not commit, push, merge, publish, or modify HANDOFF.md or DISCUSSION.md.
Do not connect to a real robot, camera, LiDAR or motor, and do not send motor commands.
Use offline checks only. Do not use an API key, paid credits, or a quota reset.
If blocked, explain exactly why in the final answer. Keep the final answer concise.`;
}

async function changedFiles(worktree) {
  const parts = await Promise.all([
    git(["diff", "--name-only", "-z"], worktree),
    git(["diff", "--cached", "--name-only", "-z"], worktree),
    git(["ls-files", "--others", "--exclude-standard", "-z"], worktree),
  ]);
  return [...new Set(parts.flatMap((part) => part.split("\0").filter(Boolean)))];
}

async function runJob(job, baseCommit) {
  const stamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
  const branch = `${job.branchPrefix}/${job.id}-${stamp}`;
  const worktree = resolve(worktreeRoot, `${job.id}-${stamp}`);
  if (!worktree.startsWith(worktreeRoot + sep) || relative(repo, worktree) === "") throw new Error("Invalid worktree path");
  const add = worktreeChain.then(async () => {
    await git(["clone", "--local", "--no-hardlinks", repo, worktree]);
    await git(["switch", "-c", branch, baseCommit], worktree);
  });
  worktreeChain = add.catch(() => {});
  await add;
  const tempDir = join(worktree, ".office-tmp");
  await mkdir(tempDir, { recursive: true });
  await appendFile(join(worktree, ".git", "info", "exclude"), "\n.office-tmp/\n", "utf8");
  await record({ jobId: job.id, lane: job.lane, agent: job.agent, state: "running", branch, baseCommit, worktree });
  let outcome;
  try {
    const result = await run("codex", [
      "exec", "--sandbox", job.mode, "--ephemeral", "--ignore-user-config",
      "-c", "approval_policy=never", "-c", "sandbox_workspace_write.network_access=false",
      "--color", "never", "-C", worktree, "-",
    ], {
      cwd: worktree, input: promptFor(job, baseCommit, branch),
      timeoutMs: Math.min(Math.max(Number(job.maxMinutes) || 15, 1), 30) * 60_000,
      env: modelEnvironment(tempDir),
    });
    const outputDir = join(stateDir, job.id);
    await mkdir(outputDir, { recursive: true });
    const outputPath = join(outputDir, `${stamp}.txt`);
    await writeFile(outputPath, `stdout:\n${result.stdout}\n\nstderr:\n${result.stderr}`, "utf8");
    const changed = await changedFiles(worktree);
    const headCommit = await git(["rev-parse", "HEAD"], worktree);
    const scoped = changedPathsAllowed(changed, job.allowedPaths);
    const unchangedHead = headCommit === baseCommit;
    const noUnexpectedEdit = job.mode !== "read-only" || changed.length === 0;
    const check = await run(process.env.OFFICE_PYTHON || "python", ["scripts/check.py"], {
      cwd: worktree, timeoutMs: 300_000, env: modelEnvironment(tempDir),
    });
    const ok = result.code === 0 && !result.timedOut && scoped && unchangedHead &&
      noUnexpectedEdit && check.code === 0 && !check.timedOut;
    outcome = {
      jobId: job.id, lane: job.lane, agent: job.agent, state: ok ? "review-ready" : "failed",
      branch, baseCommit, headCommit, worktree, changed, outputPath,
      codexExit: result.code, codexTimedOut: result.timedOut,
      checkExit: check.code, checkTimedOut: check.timedOut,
      scopeValid: scoped, headUnchanged: unchangedHead,
      summary: ok ? "งานเสร็จและเช็กออฟไลน์ผ่าน รอคนรีวิว" : "งานหรือเช็กไม่ผ่าน ดูหลักฐานใน worktree",
    };
  } catch (error) {
    outcome = { jobId: job.id, lane: job.lane, agent: job.agent, state: "failed", branch,
      baseCommit, worktree, summary: String(error.message || error) };
  }
  await record(outcome);
  return outcome;
}

export async function main(args = process.argv.slice(2)) {
  if (!args.includes("--run") && !args.includes("--dry-run")) throw new Error("Use --dry-run or --run");
  const queue = JSON.parse(await readFile(queueFile, "utf8"));
  if (!Array.isArray(queue.jobs)) throw new Error("Missing jobs");
  queue.jobs.forEach(assertJob);
  await mkdir(stateDir, { recursive: true });
  const selected = selectJobs(queue.jobs, await loadEvents(), queue.maxConcurrent);
  if (args.includes("--dry-run")) return { selected: selected.map((job) => job.id), worktreeRoot };
  const checked = Date.parse(process.env.OFFICE_USAGE_CHECKED_AT || "");
  if (!Number.isFinite(checked) || Math.abs(Date.now() - checked) > 15 * 60_000)
    throw new Error("Check Codex plan usage first; set OFFICE_USAGE_CHECKED_AT to the current ISO time");
  if (spawnSync("codex", ["login", "status"], { encoding: "utf8", timeout: 6000, env: modelEnvironment() }).status !== 0)
    throw new Error("Codex is not signed in with ChatGPT");
  const lock = await open(lockFile, "wx");
  try {
    const clean = await git(["status", "--porcelain"]);
    if (clean) throw new Error("Office source worktree is dirty");
    const baseCommit = await git(["rev-parse", "HEAD"]);
    const outcomes = await Promise.all(selected.map(async (job) => {
      try {
        return await runJob(job, baseCommit);
      } catch (error) {
        const failure = { jobId: job.id, lane: job.lane, agent: job.agent,
          state: "failed", summary: String(error.message || error) };
        await record(failure);
        return failure;
      }
    }));
    return { selected: selected.map((job) => job.id), outcomes };
  } finally {
    await lock.close();
    await unlink(lockFile);
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  main().then((result) => console.log(JSON.stringify(result))).catch((error) => {
    console.error(error.message || error);
    process.exitCode = 1;
  });
}
