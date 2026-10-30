import assert from "node:assert/strict";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { agentOutcomePassed, changedFiles, changedPathsAllowed, changesMatchMode, checksPassed, run, selectJobs } from "./automation-queue.mjs";

test("limits assignments to three independent lanes and active capacity", () => {
  const jobs = [
    { id: "a", lane: "one", ready: true }, { id: "b", lane: "one", ready: true },
    { id: "c", lane: "two", ready: true }, { id: "d", lane: "three", ready: true },
    { id: "e", lane: "four", ready: true },
  ];
  assert.deepEqual(selectJobs(jobs, []).map((job) => job.id), ["a", "c", "d"]);
  assert.deepEqual(selectJobs(jobs, [{ jobId: "a", lane: "one", state: "assigned" }])
    .map((job) => job.id), ["c", "d"]);
  assert.deepEqual(selectJobs(jobs, [{ jobId: "a", lane: "one", state: "failed" }])
    .map((job) => job.id), ["b", "c", "d"]);
  assert.deepEqual(selectJobs(jobs, [], 2).map((job) => job.id), ["a", "c"]);
});

test("rejects edits outside the assigned scope", () => {
  assert.equal(changedPathsAllowed(["tests/example.py"], ["tests/"]), true);
  assert.equal(changedPathsAllowed(["tests/example.py", "src/following_robot/controller.py"], ["tests/"]), false);
  assert.equal(changedPathsAllowed(["tests/../src/controller.py"], ["tests/"]), false);
  assert.equal(changedPathsAllowed(["C:\\robot\\motor.py"], ["tests/"]), false);
  assert.equal(changedPathsAllowed(["tests_evil/example.py"], ["tests/"]), false);
});

test("ignored source files are included in scope review while Office temp is excluded", async () => {
  const folder = await mkdtemp(join(dirname(fileURLToPath(import.meta.url)), ".office-git-test-"));
  try {
    const init = await run("git", ["init", "-q"], { cwd: folder });
    assert.equal(init.code, 0, init.stderr);
    await writeFile(join(folder, ".gitignore"), "hidden.txt\n.office-tmp/\n");
    await writeFile(join(folder, "hidden.txt"), "unexpected edit\n");
    await mkdir(join(folder, ".office-tmp"));
    await writeFile(join(folder, ".office-tmp", "output.txt"), "temporary\n");
    const changed = await changedFiles(folder);
    assert.equal(changed.includes("hidden.txt"), true);
    assert.equal(changed.some((path) => path.startsWith(".office-tmp/")), false);
    assert.equal(changedPathsAllowed(changed, ["tools/thesis_desk/virtual_office/"]), false);
  } finally { await rm(folder, { recursive: true, force: true }); }
});

test("read-only assignments cannot become review-ready with edits in allowed paths", () => {
  const changed = ["tests/allowed_test.py"];
  assert.equal(changedPathsAllowed(changed, ["tests/"]), true);
  assert.equal(changesMatchMode("read-only", changed), false);
  assert.equal(changesMatchMode("read-only", []), true);
  assert.equal(changesMatchMode("workspace-write", changed), true);
  assert.equal(changesMatchMode("workspace-write", []), false);
});

test("manual code jobs require a successful agent exit before review-ready", () => {
  assert.equal(agentOutcomePassed({ code: 0, timedOut: false }), true);
  assert.equal(agentOutcomePassed({ code: 1, timedOut: false }), false);
  assert.equal(agentOutcomePassed({ code: 0, timedOut: true }), false);
  assert.equal(agentOutcomePassed({ code: null, timedOut: false, spawnError: "ENOENT" }), false);
});

test("a required focused check failure blocks review-ready", () => {
  assert.equal(checksPassed([{ code: 0, timedOut: false }]), true);
  assert.equal(checksPassed([{ code: 1, timedOut: false }]), false);
  assert.equal(checksPassed([{ code: 0, timedOut: true }]), false);
});

test("a missing check executable resolves as a failed check", async () => {
  const result = await run("office-check-command-does-not-exist", [], { timeoutMs: 1000 });
  assert.equal(result.code, null);
  assert.equal(result.spawnError, "ENOENT");
  assert.equal(checksPassed([result]), false);
});
