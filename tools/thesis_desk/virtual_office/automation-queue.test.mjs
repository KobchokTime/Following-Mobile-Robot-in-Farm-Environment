import assert from "node:assert/strict";
import { test } from "node:test";
import { changedPathsAllowed, selectJobs } from "./automation-queue.mjs";

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
