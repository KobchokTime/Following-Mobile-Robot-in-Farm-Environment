import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { editPrompt, launchCodeJob, runEditingAgent } from "./office-code.mjs";

const assignment = { jobId: "office-ignored-scope-guard", agent: "mew", role: "thesis-desk",
  branch: "codex/thesis-desk-office/office-ignored-scope-guard-20261030120000",
  checkout: "C:\\isolated-clone", tempDir: "C:\\isolated-clone\\.office-tmp",
  maxMinutes: 15, allowedPaths: ["tools/thesis_desk/virtual_office/"],
  task: "Fix ignored path scope validation", acceptance: "A regression and offline checks pass" };

test("editing agent receives a scoped prompt and ordinary workspace-write sandbox", async () => {
  let invocation;
  function fakeSpawn(command, args, options) {
    invocation = { command, args, options };
    const child = new EventEmitter();
    child.stdout = new EventEmitter(); child.stderr = new EventEmitter();
    child.stdin = { end(prompt) { invocation.prompt = prompt; queueMicrotask(() => child.emit("close", 0)); } };
    child.kill = () => {};
    return child;
  }
  const result = await runEditingAgent(assignment, { PATH: "safe" }, fakeSpawn);
  assert.equal(result.code, 0);
  assert.equal(invocation.command, "codex");
  assert.deepEqual(invocation.args.slice(0, 4), ["exec", "--sandbox", "workspace-write", "--ephemeral"]);
  assert.equal(invocation.options.cwd, assignment.checkout);
  assert.equal(invocation.options.env.TEMP, assignment.tempDir);
  assert.match(invocation.prompt, /Do not commit, push, merge/);
  assert.match(editPrompt(assignment), /tools\/thesis_desk\/virtual_office\//);
  assert.equal(invocation.args.some((arg) => arg.includes("dangerously")), false);
});

test("seat coding reports review-ready only after a real edit and verifier success", async () => {
  const folder = await mkdtemp(join(tmpdir(), "office-code-test-"));
  const id = "11111111-1111-4111-8111-111111111111";
  const calls = [];
  try {
    const result = await launchCodeJob({ jobId: assignment.jobId, actionId: id, stateDir: folder,
      prepare: async (jobId) => { calls.push(["prepare", jobId]); return { assignments: [assignment] }; },
      runAgent: async () => { calls.push(["edit"]); return { code: 0, stdout: "changed", stderr: "", timedOut: false }; },
      finish: async (jobId, outcome) => { calls.push(["verify", jobId]); assert.equal(outcome.code, 0);
        return { state: "review-ready",
        changed: ["tools/thesis_desk/virtual_office/automation-queue.mjs"], checkExit: 0,
        scopeValid: true, headUnchanged: true }; },
    });
    assert.deepEqual(calls, [["prepare", assignment.jobId], ["edit"], ["verify", assignment.jobId]]);
    assert.equal(result.state, "completed");
    assert.equal(result.codeJob.changed.length, 1);
    assert.match(await readFile(join(folder, `${id}-code.txt`), "utf8"), /Codex exit: 0/);
  } finally { await rm(folder, { recursive: true, force: true }); }
});

test("a failing or rate-limited edit never claims review-ready even if offline checks pass", async () => {
  const folder = await mkdtemp(join(tmpdir(), "office-code-fail-"));
  try {
    const result = await launchCodeJob({ jobId: assignment.jobId,
      actionId: "22222222-2222-4222-8222-222222222222", stateDir: folder,
      prepare: async () => ({ assignments: [assignment] }),
      runAgent: async () => ({ code: 1, stdout: "", stderr: "last status: 429 Too Many Requests", timedOut: false }),
      finish: async (_id, outcome) => { assert.equal(outcome.code, 1);
        return { state: "failed", changed: ["tools/thesis_desk/virtual_office/x"],
          checkExit: 0, scopeValid: true, headUnchanged: true }; },
    });
    assert.equal(result.state, "paused");
    assert.equal(result.ok, false);
    assert.equal(result.codeJob.state, "failed");
  } finally { await rm(folder, { recursive: true, force: true }); }
});
