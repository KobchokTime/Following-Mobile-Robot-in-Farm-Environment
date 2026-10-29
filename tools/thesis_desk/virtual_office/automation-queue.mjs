import { spawn } from "node:child_process";
import { appendFile, mkdir, open, readFile, unlink, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "../../..");
const queueFile = join(here, "automation-jobs.json");
const checkoutRoot = resolve(process.env.OFFICE_WORKTREE_ROOT || join(dirname(repo), "office-agent-worktrees"));
const stateDir = join(checkoutRoot, ".office-state");
const eventsFile = join(stateDir, "events.jsonl");
const lockFile = join(stateDir, "queue.lock");

export function selectJobs(jobs, events, limit = 3) {
  const latest = new Map(events.map((event) => [event.jobId, event]));
  const active = [...latest.values()].filter((event) => event.state === "assigned");
  const lanes = new Set(active.map((event) => event.lane));
  const cap = Math.max(0, Math.min(Number(limit) || 0, 3) - active.length);
  const selected = [];
  for (const job of jobs) {
    if (!job.ready || latest.has(job.id) || lanes.has(job.lane) || selected.length >= cap) continue;
    lanes.add(job.lane);
    selected.push(job);
  }
  return selected;
}

export function changedPathsAllowed(paths, allowedPaths) {
  return paths.every((path) => {
    const normalized = path.replaceAll("\\", "/");
    return !isAbsolute(path) && !normalized.split("/").includes("..") &&
      allowedPaths.some((prefix) => normalized.startsWith(prefix));
  });
}

export function checksPassed(checks) {
  return checks.every((check) => check.code === 0 && !check.timedOut);
}

export function changesMatchMode(mode, changed) {
  return mode === "read-only" ? changed.length === 0 : changed.length > 0;
}

function validateJob(job) {
  if (!/^[a-z0-9][a-z0-9-]{2,50}$/.test(job.id) ||
      !/^[a-z0-9][a-z0-9-]{2,50}$/.test(job.lane) ||
      !/^[a-z]+$/.test(job.agent) ||
      !["read-only", "workspace-write"].includes(job.mode) ||
      !Array.isArray(job.allowedPaths) || !job.allowedPaths.length ||
      job.allowedPaths.some((path) => !/^[a-z0-9_/-]+\/$/.test(path) || path.includes("..")) ||
      (job.focusedNodeTests !== undefined &&
        (!Array.isArray(job.focusedNodeTests) || job.focusedNodeTests.length > 8 ||
          job.focusedNodeTests.some((path) => typeof path !== "string" ||
            !/^[a-z0-9_/-]+\.test\.mjs$/.test(path) ||
            !changedPathsAllowed([path], job.allowedPaths)))) ||
      typeof job.task !== "string" || job.task.length < 30 ||
      typeof job.acceptance !== "string" || job.acceptance.length < 15 ||
      !/^codex\/[a-z0-9/-]+$/.test(job.branchPrefix)) {
    throw new Error(`Invalid job ${job.id || "unknown"}`);
  }
}

async function loadQueue() {
  const queue = JSON.parse(await readFile(queueFile, "utf8"));
  if (!Array.isArray(queue.jobs)) throw new Error("Missing jobs");
  queue.jobs.forEach(validateJob);
  if (new Set(queue.jobs.map((job) => job.id)).size !== queue.jobs.length) throw new Error("Duplicate job ID");
  return queue;
}

async function events() {
  try {
    return (await readFile(eventsFile, "utf8")).split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }
}

async function record(event) {
  await appendFile(eventsFile, JSON.stringify({ at: new Date().toISOString(), ...event }) + "\n", "utf8");
}

export async function run(command, args, { cwd = repo, timeoutMs = 60_000, env = process.env } = {}) {
  return new Promise((done) => {
    let child;
    try { child = spawn(command, args, { cwd, env, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] }); }
    catch (error) {
      done({ code: null, stdout: "", stderr: error.message, timedOut: false,
        spawnError: error.code || error.name });
      return;
    }
    let stdout = "", stderr = "", timedOut = false;
    const timer = setTimeout(() => { timedOut = true; child.kill(); }, timeoutMs);
    child.stdout.on("data", (chunk) => { stdout = (stdout + chunk).slice(-32_000); });
    child.stderr.on("data", (chunk) => { stderr = (stderr + chunk).slice(-32_000); });
    child.on("error", (error) => {
      clearTimeout(timer);
      done({ code: null, stdout, stderr: `${stderr}\n${error.message}`, timedOut,
        spawnError: error.code || error.name });
    });
    child.on("close", (code) => { clearTimeout(timer); done({ code, stdout, stderr, timedOut, spawnError: null }); });
  });
}

async function git(args, cwd = repo) {
  const result = await run("git", args, { cwd });
  if (result.code !== 0 || result.timedOut) throw new Error(`git ${args[0]} failed: ${result.stderr.slice(-500)}`);
  return result.stdout.trim();
}

async function withLock(action) {
  await mkdir(stateDir, { recursive: true });
  const lock = await open(lockFile, "wx");
  try { return await action(); }
  finally { await lock.close(); await unlink(lockFile); }
}

function checkedUsage() {
  const checked = Date.parse(process.env.OFFICE_USAGE_CHECKED_AT || "");
  if (!Number.isFinite(checked) || Math.abs(Date.now() - checked) > 15 * 60_000)
    throw new Error("Check Codex plan usage first and set OFFICE_USAGE_CHECKED_AT to current ISO time");
}

function safeCheckout(id, stamp) {
  const path = resolve(checkoutRoot, `${id}-${stamp}`);
  if (!path.startsWith(checkoutRoot + sep) || relative(repo, path) === "") throw new Error("Unsafe checkout path");
  return path;
}

async function prepare() {
  checkedUsage();
  return withLock(async () => {
    const queue = await loadQueue();
    if (await git(["status", "--porcelain"])) throw new Error("Office source checkout is dirty");
    const baseCommit = await git(["rev-parse", "HEAD"]);
    const selected = selectJobs(queue.jobs, await events(), queue.maxConcurrent);
    const assignments = [];
    for (const job of selected) {
      const stamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
      const branch = `${job.branchPrefix}/${job.id}-${stamp}`;
      const checkout = safeCheckout(job.id, stamp);
      try {
        await git(["clone", "--local", "--no-hardlinks", repo, checkout]);
        await git(["switch", "-c", branch, baseCommit], checkout);
        const tempDir = join(checkout, ".office-tmp");
        await mkdir(tempDir, { recursive: true });
        await appendFile(join(checkout, ".git", "info", "exclude"), "\n.office-tmp/\n", "utf8");
        const assignment = {
          jobId: job.id, lane: job.lane, agent: job.agent, role: job.role,
          branch, baseCommit, checkout, tempDir, mode: job.mode,
          allowedPaths: job.allowedPaths, task: job.task, acceptance: job.acceptance,
          maxMinutes: Math.min(Math.max(Number(job.maxMinutes) || 15, 1), 30),
        };
        await record({ jobId: job.id, lane: job.lane, agent: job.agent,
          state: "assigned", branch, baseCommit, checkout, summary: "มอบหมายงานให้ agent แล้ว" });
        assignments.push(assignment);
      } catch (error) {
        await record({ jobId: job.id, lane: job.lane, agent: job.agent,
          state: "failed", summary: String(error.message || error) });
      }
    }
    return { assignments };
  });
}

async function changedFiles(checkout) {
  const outputs = await Promise.all([
    git(["diff", "--name-only", "-z"], checkout),
    git(["diff", "--cached", "--name-only", "-z"], checkout),
    git(["ls-files", "--others", "--exclude-standard", "-z"], checkout),
  ]);
  return [...new Set(outputs.flatMap((output) => output.split("\0").filter(Boolean)))];
}

async function finish(jobId) {
  return withLock(async () => {
    const queue = await loadQueue();
    const job = queue.jobs.find((item) => item.id === jobId);
    if (!job) throw new Error("Unknown job");
    const history = (await events()).filter((event) => event.jobId === jobId);
    const latest = history.at(-1);
    const assignment = history.findLast((event) => event.state === "assigned");
    if (!["assigned", "failed"].includes(latest?.state) || !assignment?.checkout ||
        !assignment.branch || !assignment.baseCommit) throw new Error("Job has no checkout to verify");
    const checkout = resolve(assignment.checkout);
    if (!checkout.startsWith(checkoutRoot + sep)) throw new Error("Unsafe checkout path");
    const changed = await changedFiles(checkout);
    const headCommit = await git(["rev-parse", "HEAD"], checkout);
    const scopeValid = changedPathsAllowed(changed, job.allowedPaths);
    const headUnchanged = headCommit === assignment.baseCommit;
    const modeValid = changesMatchMode(job.mode, changed);
    const tempDir = join(checkout, ".office-tmp");
    const env = { ...process.env, TEMP: tempDir, TMP: tempDir, TMPDIR: tempDir };
    const check = await run(process.env.OFFICE_PYTHON || "python", ["scripts/check.py"], {
      cwd: checkout, timeoutMs: 300_000, env,
    });
    const checkLog = join(stateDir, `${jobId}-${Date.now()}-check.txt`);
    await writeFile(checkLog, `checkout: ${checkout}\ncommand: scripts/check.py\nexit: ${check.code}\ntimed out: ${check.timedOut}\nspawn error: ${check.spawnError || "none"}\n\nstdout:\n${check.stdout}\n\nstderr:\n${check.stderr}\n`, { flag: "wx" });
    const focusedChecks = [];
    for (const path of job.focusedNodeTests || []) {
      const result = await run("node", ["--test", path], { cwd: checkout, timeoutMs: 120_000, env });
      const log = join(stateDir, `${jobId}-${Date.now()}-${focusedChecks.length}-node.txt`);
      await writeFile(log, `checkout: ${checkout}\ncommand: node --test ${path}\nexit: ${result.code}\ntimed out: ${result.timedOut}\nspawn error: ${result.spawnError || "none"}\n\nstdout:\n${result.stdout}\n\nstderr:\n${result.stderr}\n`, { flag: "wx" });
      focusedChecks.push({ path, code: result.code, timedOut: result.timedOut,
        spawnError: result.spawnError, log });
    }
    const ok = scopeValid && headUnchanged && modeValid && check.code === 0 && !check.timedOut &&
      checksPassed(focusedChecks);
    const focusedFailure = focusedChecks.find((item) => item.code !== 0 || item.timedOut);
    const result = {
      jobId, lane: job.lane, agent: job.agent, state: ok ? "review-ready" : "failed",
      branch: assignment.branch, baseCommit: assignment.baseCommit, headCommit, checkout, changed,
      scopeValid, headUnchanged, modeValid, checkExit: check.code, checkTimedOut: check.timedOut,
      checkSpawnError: check.spawnError, checkLog,
      focusedChecks,
      summary: ok ? "มีงานและเช็กออฟไลน์ผ่าน รอคนรีวิว" :
        !scopeValid ? "ไฟล์ที่แก้อยู่นอกขอบเขตงาน" :
        !headUnchanged ? "HEAD ของ clone เปลี่ยนจากฐานที่มอบหมาย" :
        !modeValid ? (job.mode === "read-only" ? "งานอ่านอย่างเดียวมีไฟล์เปลี่ยน" :
          "งานเขียนไม่มีไฟล์เปลี่ยน") :
        check.spawnError ? `Python check เริ่มไม่ได้ (${check.spawnError})` :
        check.code !== 0 || check.timedOut ? `Python check ไม่ผ่าน (exit ${check.code})` :
        focusedFailure.spawnError ? `Node test เริ่มไม่ได้: ${focusedFailure.path} (${focusedFailure.spawnError})` :
        `Node test ไม่ผ่าน: ${focusedFailure.path} (exit ${focusedFailure.code})`,
    };
    await record(result);
    return result;
  });
}

export async function main(args = process.argv.slice(2)) {
  if (args.includes("--dry-run")) {
    const queue = await loadQueue();
    return { selected: selectJobs(queue.jobs, await events(), queue.maxConcurrent).map((job) => job.id),
      checkoutRoot };
  }
  if (args.includes("--prepare")) return prepare();
  if (args.includes("--finish")) {
    const index = args.indexOf("--job");
    if (index < 0 || !args[index + 1]) throw new Error("Missing --job ID");
    return finish(args[index + 1]);
  }
  throw new Error("Use --dry-run, --prepare or --finish --job ID");
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  main().then((result) => console.log(JSON.stringify(result))).catch((error) => {
    console.error(error.message || error);
    process.exitCode = 1;
  });
}
