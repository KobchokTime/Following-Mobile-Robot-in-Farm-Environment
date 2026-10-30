import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { latestJobEvent, launchCodeJob } from "./office-code.mjs";

const assignment = { jobId: "office-stale-lock-diagnostic", agent: "mew",
  branch: "codex/thesis-desk-office/office-stale-lock-diagnostic-20261030120000",
  checkout: "C:\\isolated-clone" };

test("a seat click prepares an isolated job and waits for actual verifier evidence", async () => {
  const folder = await mkdtemp(join(tmpdir(), "office-native-job-"));
  let reads = 0;
  try {
    const result = await launchCodeJob({ jobId: assignment.jobId, stateDir: folder,
      prepare: async (id) => { assert.equal(id, assignment.jobId);
        return { assignments: [assignment] }; },
      latest: async () => ++reads === 1 ? { state: "assigned" } :
        { state: "review-ready", changed: ["tools/thesis_desk/virtual_office/automation-queue.mjs"],
          checkExit: 0, branch: assignment.branch, checkLog: join(folder, "office-stale-lock-diagnostic-1793200000000-check.txt") },
      wait: async () => {},
    });
    assert.equal(reads, 2);
    assert.equal(result.state, "completed");
    assert.deepEqual(result.codeJob.changed, ["tools/thesis_desk/virtual_office/automation-queue.mjs"]);
    assert.equal(result.codeJob.checkLogName, "office-stale-lock-diagnostic-1793200000000-check.txt");
  } finally { await rm(folder, { recursive: true, force: true }); }
});

test("assigned without a verified diff never appears complete", async () => {
  const folder = await mkdtemp(join(tmpdir(), "office-native-fail-"));
  try {
    const result = await launchCodeJob({ jobId: assignment.jobId, stateDir: folder,
      prepare: async () => ({ assignments: [assignment] }),
      latest: async () => ({ state: "failed", changed: [], checkExit: 0,
        summary: "งานเขียนไม่มีไฟล์เปลี่ยน" }),
    });
    assert.equal(result.ok, false);
    assert.equal(result.state, "failed");
  } finally { await rm(folder, { recursive: true, force: true }); }
});

test("latest append-only queue event controls the displayed result", async () => {
  const folder = await mkdtemp(join(tmpdir(), "office-native-events-"));
  try {
    const path = join(folder, "events.jsonl");
    await writeFile(path, [
      { jobId: assignment.jobId, state: "assigned" },
      { jobId: "other", state: "failed" },
      { jobId: assignment.jobId, state: "review-ready", changed: ["tools/thesis_desk/virtual_office/x"] },
    ].map(JSON.stringify).join("\n") + "\n");
    assert.equal((await latestJobEvent(path, assignment.jobId)).state, "review-ready");
    assert.equal((await readFile(path, "utf8")).split("\n").filter(Boolean).length, 3);
  } finally { await rm(folder, { recursive: true, force: true }); }
});
