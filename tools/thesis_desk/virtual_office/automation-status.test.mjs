import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { formatAutomationJob } from "./automation-status.mjs";

test("review-ready job shows its branch and successful offline check", () => {
  const display = formatAutomationJob({
    lane: "evidence-delivery", state: "review-ready", branch: "codex/qa/office/example",
    checkExit: 0, checkTimedOut: false, summary: "รอคนรีวิว",
  }, "Boss", "28/10/69 15:45");
  assert.match(display.heading, /Boss.*รอรีวิว/);
  assert.deepEqual(display.details, [
    "สาขา: codex/qa/office/example", "ตรวจออฟไลน์ผ่าน (exit 0)", "รอคนรีวิว",
  ]);
});

test("failed job exposes its recorded reason and failed check", () => {
  const display = formatAutomationJob({
    lane: "office-experience", state: "failed", branch: "codex/thesis-desk-office/example",
    checkExit: 1, summary: "ไฟล์ที่แก้เกินขอบเขต",
  }, "Mew", "28/10/69 21:00");
  assert.match(display.heading, /Mew.*ล้มเหลว/);
  assert.deepEqual(display.details, [
    "สาขา: codex/thesis-desk-office/example", "ตรวจออฟไลน์ไม่ผ่าน (exit 1)",
    "ไฟล์ที่แก้เกินขอบเขต",
  ]);
});

test("failed preparation without a check does not claim a check result", () => {
  const display = formatAutomationJob({ lane: "office-experience", state: "failed",
    checkExit: null, summary: "สร้าง checkout ไม่สำเร็จ" }, "Mew", "28/10/69 21:00");
  assert.deepEqual(display.details, ["สร้าง checkout ไม่สำเร็จ"]);
});

test("automation endpoint includes recorded check result and failure reason", async () => {
  const stateRoot = await mkdtemp(join(tmpdir(), "office-status-"));
  const previousRoot = process.env.OFFICE_WORKTREE_ROOT;
  try {
    process.env.OFFICE_WORKTREE_ROOT = stateRoot;
    await mkdir(join(stateRoot, ".office-state"));
    await writeFile(join(stateRoot, ".office-state", "events.jsonl"), [
      JSON.stringify({ jobId: "dashboard-dirty-provenance", state: "failed",
        summary: "สร้าง checkout ไม่สำเร็จ", at: "2026-10-28T08:00:00Z" }),
      JSON.stringify({ jobId: "dashboard-dirty-provenance-v2", state: "review-ready",
        branch: "codex/qa/office/example", checkExit: 0, checkTimedOut: false,
        summary: "รอคนรีวิว", at: "2026-10-28T08:45:00Z" }),
    ].join("\n") + "\n");
    const { handleRequest } = await import(`./server.mjs?status-test=${Date.now()}`);
    let status, body;
    await handleRequest({ method: "GET", url: "/api/automation" }, {
      writeHead(code) { status = code; },
      end(data) { body = JSON.parse(data); },
    });
    assert.equal(status, 200);
    const failed = body.jobs.find((job) => job.id === "dashboard-dirty-provenance");
    const reviewed = body.jobs.find((job) => job.id === "dashboard-dirty-provenance-v2");
    assert.equal(failed.summary, "สร้าง checkout ไม่สำเร็จ");
    assert.equal(reviewed.branch, "codex/qa/office/example");
    assert.equal(reviewed.checkExit, 0);
    assert.equal(reviewed.checkTimedOut, false);
  } finally {
    if (previousRoot === undefined) delete process.env.OFFICE_WORKTREE_ROOT;
    else process.env.OFFICE_WORKTREE_ROOT = previousRoot;
    await rm(stateRoot, { recursive: true, force: true });
  }
});
