import { spawn } from "node:child_process";
import { writeFile } from "node:fs/promises";
import { basename, join } from "node:path";
import { finishManual, prepareManual } from "./automation-queue.mjs";

export function editPrompt(assignment) {
  return `You are the ${assignment.agent} agent working as the ${assignment.role} role in the follower project's Virtual Office.
Work only in this isolated checkout, on branch ${assignment.branch}. Read AGENTS.md and the matching role file first.
Task: ${assignment.task}
Acceptance: ${assignment.acceptance}
You may edit only these repository paths: ${assignment.allowedPaths.join(", ")}.
Do not commit, push, merge, edit another branch, use a paid API key, or connect to a real robot or motor.
Do not change HANDOFF.md, DISCUSSION.md, or logs. Keep existing tests enabled.
Make the code change and run focused offline checks. Report what changed and what passed.
If you cannot complete the task within this checkout and scope, explain the blocker and leave the diff for review.`;
}

export function runEditingAgent(assignment, env, spawnAgent = spawn) {
  return new Promise((resolve) => {
    const args = ["exec", "--sandbox", "workspace-write", "--ephemeral", "--ignore-user-config",
      "--color", "never", "-C", assignment.checkout, "-"];
    const child = spawnAgent("codex", args, { cwd: assignment.checkout,
      env: { ...env, TEMP: assignment.tempDir, TMP: assignment.tempDir, TMPDIR: assignment.tempDir },
      windowsHide: true, stdio: ["pipe", "pipe", "pipe"] });
    let stdout = "", stderr = "", timedOut = false, settled = false;
    const finish = (result) => { if (settled) return; settled = true; clearTimeout(timer); resolve(result); };
    const timer = setTimeout(() => { timedOut = true; child.kill(); }, assignment.maxMinutes * 60_000);
    child.stdout.on("data", (chunk) => { stdout = (stdout + chunk).slice(-64_000); });
    child.stderr.on("data", (chunk) => { stderr = (stderr + chunk).slice(-64_000); });
    child.on("error", (error) => finish({ code: null, stdout, stderr: `${stderr}\n${error.message}`,
      timedOut, spawnError: error.code || error.name }));
    child.on("close", (code) => finish({ code, stdout, stderr, timedOut, spawnError: null }));
    child.stdin.end(editPrompt(assignment));
  });
}

export async function launchCodeJob({ jobId, actionId, stateDir, runAgent,
  prepare = prepareManual, finish = finishManual }) {
  const { assignments } = await prepare(jobId);
  if (assignments.length !== 1) return { state: "failed", summary: "ไม่มีงานแก้โค้ดที่พร้อมเริ่ม" };
  const assignment = assignments[0];
  let agentResult;
  try { agentResult = await runAgent(assignment); }
  catch (error) { agentResult = { code: null, stdout: "", stderr: String(error.message || error),
    timedOut: false, spawnError: error.code || error.name, status: error.status }; }
  const logName = `${actionId}-code.txt`;
  let logSaved = true;
  try {
    await writeFile(join(stateDir, logName),
      `checkout: ${assignment.checkout}\nbranch: ${assignment.branch}\nCodex exit: ${agentResult.code}\ntimed out: ${agentResult.timedOut}\nspawn error: ${agentResult.spawnError || "none"}\n\nstdout:\n${agentResult.stdout}\n\nstderr:\n${agentResult.stderr}\n`,
      { flag: "wx" });
  } catch { logSaved = false; }
  const verified = await finish(jobId, agentResult);
  const limited = agentResult.status === 429 || /(?:last status|status):\s*429\b|\b429 Too Many Requests\b/i.test(
    `${agentResult.stdout}\n${agentResult.stderr}`);
  const ok = logSaved && agentResult.code === 0 && !agentResult.timedOut &&
    verified.state === "review-ready";
  return { state: limited ? "paused" : ok ? "completed" : "failed", ok,
    summary: limited ? "Codex ถึงขีดจำกัดบัญชี งานที่แก้ไว้ยังอยู่ใน clone" :
      ok ? "agent แก้โค้ดและผ่านเช็กออฟไลน์แล้ว รอคนรีวิว" :
        !logSaved ? "บันทึกการรัน agent ไม่สำเร็จ โปรดตรวจ clone" :
        `งานยังไม่ผ่าน: ${verified.summary || "Codex แก้โค้ดไม่สำเร็จ"}`,
    codeJob: { id: jobId, agent: assignment.agent, branch: assignment.branch,
      checkout: assignment.checkout, changed: verified.changed || [],
      checkExit: verified.checkExit, scopeValid: verified.scopeValid,
      headUnchanged: verified.headUnchanged, state: verified.state,
      logName: logSaved ? logName : null,
    checkLogName: verified.checkLog ? basename(verified.checkLog) : null,
    focusedChecks: verified.focusedChecks || [] } };
}
