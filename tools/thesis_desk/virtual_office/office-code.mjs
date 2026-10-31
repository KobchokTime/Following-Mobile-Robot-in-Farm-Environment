import { readFile } from "node:fs/promises";
import { basename, join } from "node:path";
import { prepareManual } from "./automation-queue.mjs";

const terminalStates = new Set(["review-ready", "failed", "paused"]);

export async function latestJobEvent(eventsFile, jobId) {
  const raw = await readFile(eventsFile, "utf8");
  const events = raw.split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
  return events.filter((event) => event.jobId === jobId).at(-1) || null;
}

export async function launchCodeJob({ jobId, stateDir, prepare = prepareManual,
  latest = () => latestJobEvent(join(stateDir, "events.jsonl"), jobId),
  wait = () => new Promise((resolve) => setTimeout(resolve, 3_000)) }) {
  const { assignments } = await prepare(jobId);
  if (assignments.length !== 1) return { state: "failed", summary: "ไม่มีงานแก้โค้ดที่พร้อมเริ่ม" };
  const assignment = assignments[0];
  for (;;) {
    const event = await latest();
    if (event && terminalStates.has(event.state)) {
      const ok = event.state === "review-ready" && (event.changed?.length || 0) > 0;
      return { ok, state: ok ? "completed" : event.state === "paused" ? "paused" : "failed",
        summary: ok ? "agent แก้โค้ดและผ่านเช็กออฟไลน์แล้ว รอคนรีวิว" :
          event.summary || "งานยังไม่ผ่าน โปรดดูผลตรวจ",
        codeJob: { id: jobId, agent: assignment.agent, branch: assignment.branch,
          checkout: assignment.checkout, changed: event.changed || [],
          checkExit: event.checkExit ?? null, scopeValid: event.scopeValid,
          headUnchanged: event.headUnchanged, state: event.state,
          checkLogName: event.checkLog ? basename(event.checkLog) : null,
          focusedChecks: event.focusedChecks || [] } };
    }
    await wait();
  }
}
