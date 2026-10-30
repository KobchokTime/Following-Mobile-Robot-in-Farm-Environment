import { appendFile, mkdir, readFile } from "node:fs/promises";
import { dirname } from "node:path";
import { randomUUID } from "node:crypto";

export const seatAgentIds = ["krit", "mew", "boss"];
export const meetingAgentIds = ["natee", "fah", "dao", "min", "palm", "ploy", "tee", "june", "art",
  "krit", "mew", "boss"];

export function selectIdle(ids, actions, limit = 3, offset = 0) {
  const busy = new Set(actions.filter((action) => action.state === "running")
    .flatMap((action) => action.agents));
  const ordered = [...ids.slice(offset), ...ids.slice(0, offset)];
  return ordered.filter((id) => !busy.has(id)).slice(0, limit);
}

export function createModelGate({ run, isLimited, classify, markLimited }) {
  let tail = Promise.resolve();
  return (...args) => {
    const request = tail.then(async () => {
      if (isLimited()) {
        const error = new Error("Codex rate limited");
        error.status = 429;
        throw error;
      }
      try { return await run(...args); }
      catch (error) {
        if (classify(error).status === 429) markLimited();
        throw error;
      }
    });
    tail = request.catch(() => {});
    return request;
  };
}

export function createOfficeWorkflow({ eventFile, runSeat, runMeeting, getExternalBusy = () => [] }) {
  const actions = new Map();
  const reservations = new Set();
  let initialized;
  let writeTail = Promise.resolve();
  let startTail = Promise.resolve();

  async function record(action) {
    const next = { ...action, updatedAt: new Date().toISOString() };
    writeTail = writeTail.catch(() => {}).then(async () => {
      await mkdir(dirname(eventFile), { recursive: true });
      await appendFile(eventFile, JSON.stringify(next) + "\n", "utf8");
    });
    await writeTail;
    actions.set(next.id, next);
    return next;
  }

  async function init() {
    if (!initialized) initialized = (async () => {
      try {
        const raw = await readFile(eventFile, "utf8");
        for (const line of raw.split(/\r?\n/).filter(Boolean)) {
          const action = JSON.parse(line);
          actions.set(action.id, action);
        }
      } catch (error) {
        if (error.code !== "ENOENT") throw error;
      }
      for (const action of [...actions.values()]) {
        if (action.state === "running") await record({ ...action, state: "interrupted",
          summary: "เซิร์ฟเวอร์หยุดก่อนงานจบ โปรดเริ่มใหม่" });
      }
    })();
    return initialized;
  }

  async function list() {
    await init();
    return [...actions.values()].sort((a, b) => b.createdAt.localeCompare(a.createdAt)).slice(0, 12);
  }

  async function busyAgents() {
    await init();
    return new Set([...reservations, ...[...actions.values()]
      .filter((action) => action.state === "running").flatMap((action) => action.agents)]);
  }

  async function perform(action, runner) {
    try {
      const result = await runner(action);
      await record({ ...action, ...result,
        state: ["completed", "failed", "paused"].includes(result.state) ? result.state :
          result.ok ? "completed" : "failed" });
    } catch (error) {
      try {
        await record({ ...action, state: error.status === 429 ? "paused" : "failed",
          summary: error.publicMessage || "งานไม่สำเร็จ โปรดดูบันทึกการรัน" });
      } catch (recordError) {
        console.error("Office action state could not be saved:", recordError);
      }
    }
  }

  async function start(kind, job = null) {
    const started = startTail.then(async () => {
      await init();
      const current = [...actions.values()];
      const active = current.find((action) => action.kind === kind && action.state === "running");
      if (active) return { action: active, alreadyRunning: true };
      const priorMeetings = current.filter((action) => action.kind === "meeting").length;
      if (kind === "seat" && job && (!seatAgentIds.includes(job.agent) || !job.id))
        return { error: "งานนี้ไม่มี agent ที่โต๊ะรับผิดชอบ" };
      const ids = kind === "seat" ? (job ? [job.agent] : seatAgentIds) : meetingAgentIds;
      const offset = kind === "meeting" ? (priorMeetings * 3) % ids.length : 0;
      const externalBusy = getExternalBusy();
      if (kind === "meeting" && externalBusy.includes("team"))
        return { error: "หัวหน้าทีมกำลังตอบโจทย์ โปรดลองประชุมอีกครั้ง" };
      const agents = selectIdle(ids, [...current,
        { state: "running", agents: [...externalBusy, ...reservations] }], 3, offset);
      if (kind === "meeting" && agents.length < 2)
        return { error: "มี agent ว่างไม่พอสำหรับประชุม" };
      if (!agents.length) return { error: "ไม่มี agent ว่างสำหรับงานนี้" };
      agents.forEach((id) => reservations.add(id));
      let action;
      try {
        action = await record({ id: randomUUID(), kind, agents, state: "running",
          ...(job ? { jobId: job.id } : {}),
          createdAt: new Date().toISOString(), summary: kind === "seat" ?
            job ? "เตรียม clone แยก รอ Codex agent รับงานแก้โค้ด" : "เริ่มตรวจโปรเจกต์จริงในเครื่อง" :
            "เริ่มประชุม agent ที่ว่าง" });
      } finally { agents.forEach((id) => reservations.delete(id)); }
      queueMicrotask(() => { void perform(action, kind === "seat" ? runSeat : runMeeting)
        .catch((error) => console.error("Office action failed:", error)); });
      return { action, alreadyRunning: false };
    });
    startTail = started.then(() => {}, () => {});
    return started;
  }

  return { list, busyAgents, startSeat: (job) => start("seat", job),
    startMeeting: () => start("meeting") };
}
