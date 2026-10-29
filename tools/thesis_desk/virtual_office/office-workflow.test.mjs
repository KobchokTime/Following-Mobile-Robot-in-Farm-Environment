import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { test } from "node:test";
import { createModelGate, createOfficeWorkflow, selectIdle } from "./office-workflow.mjs";

async function removeTestFolder(folder) {
  if (dirname(resolve(folder)) !== resolve(tmpdir())) throw new Error("Unexpected test folder");
  await rm(folder, { recursive: true, force: true });
}

test("an active seat round leaves only idle agents for a real meeting", async () => {
  const folder = await mkdtemp(join(tmpdir(), "office-flow-"));
  const eventFile = join(folder, "events.jsonl");
  let finishSeat;
  const seatGate = new Promise((resolve) => { finishSeat = resolve; });
  try {
    const flow = createOfficeWorkflow({ eventFile,
      runSeat: async () => { await seatGate; return { ok: true, results: [{ agent: "krit", checkExit: 0 }] }; },
      runMeeting: async () => ({ ok: true, plan: "ตรวจ PR พร้อมเกณฑ์ผ่าน" }),
    });
    const seat = await flow.startSeat();
    assert.deepEqual(seat.action.agents, ["krit", "mew", "boss"]);
    assert.equal(seat.action.state, "running");
    assert.equal((await flow.startSeat()).alreadyRunning, true);
    const meeting = await flow.startMeeting();
    assert.deepEqual(meeting.action.agents, ["natee", "fah", "dao"]);
    assert.equal(meeting.action.agents.some((id) => seat.action.agents.includes(id)), false);
    finishSeat();
    for (let attempt = 0; attempt < 50; attempt++) {
      const actions = await flow.list();
      if (actions.every((action) => action.state !== "running")) break;
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
    const actions = await flow.list();
    assert.equal(actions.find((action) => action.kind === "seat").state, "completed");
    assert.equal(actions.find((action) => action.kind === "meeting").plan, "ตรวจ PR พร้อมเกณฑ์ผ่าน");
    const recorded = (await readFile(eventFile, "utf8")).trim().split("\n").map(JSON.parse);
    assert.equal(recorded.filter((action) => action.state === "running").length, 2);
    assert.equal(recorded.filter((action) => action.state === "completed").length, 2);
  } finally {
    finishSeat();
    await removeTestFolder(folder);
  }
});

test("running work is marked interrupted after a server restart", async () => {
  const folder = await mkdtemp(join(tmpdir(), "office-restart-"));
  const eventFile = join(folder, "events.jsonl");
  try {
    await writeFile(eventFile, JSON.stringify({ id: "old", kind: "seat", agents: ["krit"],
      state: "running", createdAt: "2026-10-29T00:00:00Z" }) + "\n");
    const flow = createOfficeWorkflow({ eventFile, runSeat: async () => ({ ok: true }),
      runMeeting: async () => ({ ok: true }) });
    assert.equal((await flow.list())[0].state, "interrupted");
    assert.deepEqual(selectIdle(["krit", "mew"], await flow.list()), ["krit", "mew"]);
  } finally {
    await removeTestFolder(folder);
  }
});

test("a 429 prevents queued agent turns from starting", async () => {
  let calls = 0;
  let limited = false;
  const gate = createModelGate({
    run: async () => { calls++; throw new Error("last status: 429 Too Many Requests"); },
    isLimited: () => limited,
    classify: (error) => ({ status: error.status === 429 || error.message.includes("429") ? 429 : 502 }),
    markLimited: () => { limited = true; },
  });
  const first = gate("first");
  const second = gate("second");
  await assert.rejects(first, /429/);
  await assert.rejects(second, (error) => error.status === 429);
  assert.equal(calls, 1);
});

test("meeting excludes an agent occupied by direct chat", async () => {
  const folder = await mkdtemp(join(tmpdir(), "office-chat-busy-"));
  try {
    const flow = createOfficeWorkflow({ eventFile: join(folder, "events.jsonl"),
      getExternalBusy: () => ["natee", "krit"],
      runSeat: async () => ({ ok: true }), runMeeting: async () => ({ ok: true }),
    });
    assert.deepEqual((await flow.startSeat()).action.agents, ["mew", "boss"]);
    assert.deepEqual((await flow.startMeeting()).action.agents, ["fah", "dao", "min"]);
    for (let attempt = 0; attempt < 50; attempt++) {
      if ((await flow.list()).every((action) => action.state === "completed")) break;
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
    assert.equal((await flow.list()).every((action) => action.state === "completed"), true);
  } finally {
    await removeTestFolder(folder);
  }
});

test("a failed event append does not poison later Office actions", async () => {
  const folder = await mkdtemp(join(tmpdir(), "office-write-retry-"));
  const eventFile = join(folder, "events.jsonl");
  try {
    const flow = createOfficeWorkflow({ eventFile,
      runSeat: async () => ({ ok: true }), runMeeting: async () => ({ ok: true }),
    });
    await flow.list();
    await mkdir(eventFile);
    await assert.rejects(flow.startSeat());
    await rm(eventFile, { recursive: true });
    const started = await flow.startSeat();
    assert.equal(started.action.state, "running");
    for (let attempt = 0; attempt < 50; attempt++) {
      if ((await flow.list())[0]?.state === "completed") break;
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
    assert.equal((await flow.list())[0].state, "completed");
  } finally {
    await removeTestFolder(folder);
  }
});
