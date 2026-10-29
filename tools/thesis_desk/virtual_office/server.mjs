import { createServer } from "node:http";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";
import { spawn, spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { run as runCheck } from "./automation-queue.mjs";
import { createModelGate, createOfficeWorkflow } from "./office-workflow.mjs";

const root = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(root, "../../..");
const automationRoot = resolve(process.env.OFFICE_WORKTREE_ROOT || join(dirname(repoRoot), "office-agent-worktrees"));
const officeStateDir = join(automationRoot, ".office-state");
const port = Number(process.env.PORT || 8765);
export function loggedInWithChatGPT(result) {
  return result.status === 0 && /Logged in using ChatGPT/i.test(`${result.stdout || ""}\n${result.stderr || ""}`);
}

export function codexChildEnv(env) {
  const childEnv = { ...env };
  for (const key of ["OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_ADMIN_KEY", "OPENAI_BASE_URL"])
    delete childEnv[key];
  return childEnv;
}

const codexReady = loggedInWithChatGPT(spawnSync("codex", ["login", "status"], { encoding: "utf8", timeout: 6000 }));
const quotaMessage = "Codex จำกัดคำขอชั่วคราว (429) โปรดลองอีกครั้งภายหลัง";
let modelRateLimited = false;
const agents = [
  ["natee", "Natee", "Integration", "จัดลำดับงาน ตรวจ HANDOFF และ DISCUSSION และประสานการรวม branch"],
  ["min", "Min", "Experiment", "อ่านเกณฑ์ทดลอง seed และผลของแต่ละรอบจากหลักฐานที่บันทึกไว้"],
  ["palm", "Palm", "Simulation", "ตรวจ twin และ Gazebo แบบออฟไลน์พร้อมหลักฐานการรัน"],
  ["fah", "Fah", "Planning", "วางลำดับ feature แยกสายงานและติดตามจุดติดขัด"],
  ["boss", "Boss", "Evidence", "ตรวจแหล่งที่มา เวลา commit และความครบถ้วนของหลักฐาน"],
  ["ploy", "Ploy", "Metrics", "ตรวจตัวเลขผ่านเกณฑ์ สรุปผลตามฉากและ seed"],
  ["tee", "Tee", "ROS", "อ่านโครงสร้าง ROS และระบุจุดที่ต้องตรวจโดยผู้ใช้บนหุ่นจริง"],
  ["june", "June", "Safety Audit", "ทบทวนความเสี่ยงก่อนรวม controller, identity, fusion หรือ motor bridge"],
  ["krit", "Krit", "QA", "กำหนดเกณฑ์ผ่าน รันเช็กออฟไลน์ และอ่านผล CI"],
  ["mew", "Mew", "Dashboard", "ตรวจแท็บและการแสดงข้อมูลจากหลักฐานจริง"],
  ["art", "Art", "Automation", "ตรวจงาน heartbeat โควตา และคิวงานโดยไม่ใช้ API key"],
  ["dao", "Dao", "Handoff", "สรุปงานที่รอรีวิว งานที่รวมแล้ว และผู้รับช่วงต่อ"],
].map(([id, name, role, focus]) => ({ id, name, role, focus }));

const conversations = new Map();
const teamConversations = new Map();
const codexContexts = new Map();
const activeChatAgents = new Set();
const teamAgent = { id: "team", name: "Team Lead", role: "หัวหน้าทีม agent", focus: "รับโจทย์ เลือกผู้เชี่ยวชาญ และสรุปผล" };
const reply = (res, status, data) => {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" });
  res.end(JSON.stringify(data));
};
async function readJson(req) {
  let body = "";
  for await (const chunk of req) {
    body += chunk;
    if (body.length > 12000) throw new Error("ข้อความยาวเกินกำหนด");
  }
  return JSON.parse(body);
}

function specialistInstructions(agent) {
  return `คุณคือ ${agent.name} ตำแหน่ง ${agent.role} ในสำนักงานเสมือน ตอบภาษาไทยตามบทบาทของคุณ งานหลักคือ: ${agent.focus} ให้คำตอบสั้น ชัดเจน และบอกเมื่อข้อมูลไม่พอ ห้ามอ้างว่าทำงานภายนอกหรือส่งต่อให้เพื่อนร่วมทีมแล้วถ้ายังไม่ได้ทำจริง`;
}

async function runCodex(instructions, input, previous) {
  const history = codexContexts.get(previous) || [];
  const context = history.slice(-6).map((turn) => `${turn.role}: ${turn.text}`).join("\n");
  const prompt = `${instructions}\n\nตอบเฉพาะคำตอบสุดท้ายเป็นข้อความ ห้ามแก้ไฟล์หรือเรียกใช้เครื่องมือที่เปลี่ยนข้อมูล\n\n${context ? `บทสนทนาก่อนหน้า:\n${context}\n\n` : ""}โจทย์ล่าสุด:\n${input}`;
  const answer = await new Promise((resolveAnswer, reject) => {
    const child = spawn("codex", ["exec", "--sandbox", "read-only", "--ephemeral", "--ignore-user-config", "--skip-git-repo-check", "--color", "never", "-C", root, "-"], {
      cwd: root,
      env: codexChildEnv(process.env),
      windowsHide: true,
      stdio: ["pipe", "pipe", "pipe"],
    });
    let stdout = "", stderr = "";
    const timer = setTimeout(() => child.kill(), 120000);
    child.stdout.on("data", (chunk) => { stdout += chunk; if (stdout.length > 40000) child.kill(); });
    child.stderr.on("data", (chunk) => { stderr += chunk; if (stderr.length > 40000) child.kill(); });
    child.on("error", (error) => { clearTimeout(timer); reject(error); });
    child.on("close", (code) => {
      clearTimeout(timer);
      const text = stdout.trim();
      if (code === 0 && text) resolveAnswer(text);
      else reject(new Error(stderr.slice(-500).trim() || "Codex ตอบกลับไม่ได้"));
    });
    child.stdin.end(prompt);
  });
  const id = randomUUID();
  codexContexts.set(id, [...history, { role: "user", text: input }, { role: "assistant", text: answer }]);
  if (codexContexts.size > 300) codexContexts.delete(codexContexts.keys().next().value);
  return { id, answer };
}

const runModel = createModelGate({ run: runCodex, isLimited: () => modelRateLimited,
  classify: classifyModelError, markLimited: () => { modelRateLimited = true; } });

async function runSeatAction(action) {
  await mkdir(officeStateDir, { recursive: true });
  const tempDir = await mkdtemp(join(officeStateDir, "seat-check-"));
  const env = { ...codexChildEnv(process.env), TEMP: tempDir, TMP: tempDir, TMPDIR: tempDir };
  const tasks = {
    krit: { command: process.env.OFFICE_PYTHON || "python", args: ["scripts/check.py"],
      label: "ตรวจ Python offline ทั้งโครงการ", timeoutMs: 300_000 },
    mew: { command: "node", args: ["--test", "tools/thesis_desk/virtual_office/automation-queue.test.mjs",
      "tools/thesis_desk/virtual_office/server.test.mjs",
      "tools/thesis_desk/virtual_office/office-workflow.test.mjs"], label: "ตรวจระบบ Office ด้วย Node", timeoutMs: 120_000 },
    boss: { command: "git", args: ["log", "-1", "--format=%H%n%cI%n%s"],
      label: "ตรวจ commit ต้นทางพร้อมเวลา", timeoutMs: 30_000 },
  };
  const checks = await Promise.all(action.agents.map(async (id) => {
    const task = tasks[id];
    const result = await runCheck(task.command, task.args, { cwd: repoRoot,
      timeoutMs: task.timeoutMs, env });
    const logName = `${action.id}-${id}.txt`;
    await writeFile(join(officeStateDir, logName),
      `branch checkout: ${repoRoot}\ncommand: ${task.command} ${task.args.join(" ")}\nexit: ${result.code}\ntimed out: ${result.timedOut}\nspawn error: ${result.spawnError || "none"}\n\nstdout:\n${result.stdout}\n\nstderr:\n${result.stderr}\n`,
      { flag: "wx" });
    return { agent: id, label: task.label, code: result.code,
      timedOut: result.timedOut, logName,
      evidence: `${result.stdout}\n${result.stderr}`.slice(-2400) };
  }));
  const results = [];
  let limited = false;
  let modelFailed = !codexReady;
  for (const check of checks) {
    const agent = agents.find((item) => item.id === check.agent);
    let analysis = "ไม่ได้เรียกโมเดล: Codex ยังไม่พร้อม";
    if (codexReady && !modelRateLimited) {
      try {
        const result = await runModel(specialistInstructions(agent),
          `ตรวจผลการรันจริงจาก checkout นี้เท่านั้น: ${check.label}\nexit=${check.code}, timeout=${check.timedOut}\n${check.evidence}\nสรุปผลและขั้นต่อไปสั้น ๆ ห้ามอ้างว่าแก้ไฟล์หรือรันคำสั่งอื่นแล้ว`);
        analysis = result.answer;
      } catch (error) {
        const failure = classifyModelError(error);
        if (failure.status === 429) { modelRateLimited = true; limited = true; }
        else modelFailed = true;
        analysis = failure.error;
      }
    } else if (modelRateLimited) {
      limited = true;
      analysis = quotaMessage;
    }
    results.push({ agent: check.agent, label: check.label, checkExit: check.code,
      timedOut: check.timedOut, logName: check.logName, analysis });
  }
  const checksPassed = results.every((item) => item.checkExit === 0 && !item.timedOut);
  return { ok: checksPassed && !limited && !modelFailed,
    state: limited || !codexReady ? "paused" : checksPassed && !modelFailed ? "completed" : "failed",
    results, summary: limited ? "ตรวจออฟไลน์แล้ว แต่ Codex ถึงขีดจำกัด โปรดดูผลที่บันทึกไว้" :
      !codexReady ? "ตรวจออฟไลน์แล้ว แต่ Codex ยังไม่พร้อมประเมินผล" :
      modelFailed ? "ตรวจออฟไลน์แล้ว แต่ agent ประเมินผลไม่สำเร็จ" :
      checksPassed ? "agent ตรวจโปรเจกต์จริงและบันทึกผลแล้ว" : "มีการตรวจที่ไม่ผ่าน โปรดดูผลที่บันทึกไว้" };
}

async function runMeetingAction(action) {
  const head = await runCheck("git", ["rev-parse", "--short", "HEAD"], { cwd: repoRoot });
  if (head.code !== 0) throw new Error("Cannot read repository revision");
  const discussion = await readFile(join(repoRoot, "DISCUSSION.md"), "utf8");
  const t15Start = discussion.lastIndexOf("## T15");
  const t16Start = discussion.lastIndexOf("## T16");
  const t15 = t15Start < 0 ? "ไม่มีบันทึก T15" : discussion.slice(t15Start, t16Start < 0 ? undefined : t16Start);
  const t16 = t16Start < 0 ? "ไม่มีบันทึก T16" : discussion.slice(t16Start);
  const previous = (await officeWorkflow.list()).find((item) => item.kind === "seat" &&
    ["completed", "failed", "paused"].includes(item.state));
  const context = `นี่คือ snapshot ใน checkout ${head.stdout.trim()} ณ ${new Date().toISOString()}\n` +
    `T15 ล่าสุด:\n${t15.slice(-1600)}\nT16 ล่าสุด:\n${t16.slice(-2200)}\n` +
    `ผลตรวจล่าสุด: ${previous?.summary || "ยังไม่มี"}\n` +
    (previous?.results?.map((result) => `${result.agent}: ${result.label}; exit=${result.checkExit}; ` +
      `timeout=${result.timedOut}; log=/api/office/logs/${result.logName}; ` +
      `assessment=${String(result.analysis || "").slice(0, 600)}`).join("\n") || "") + "\n" +
    "เสนอแผนสำหรับ Follower Test Bench และ Virtual Office โดยยึดหลักฐานที่มี ระบุงาน 1–3 งาน เจ้าของงาน และเกณฑ์ผ่าน ห้ามอ้างว่าลงมือทำหรือรวม branch แล้ว";
  const turns = [];
  for (const id of action.agents) {
    if (modelRateLimited) return { ok: false, state: "paused", turns,
      summary: quotaMessage };
    const agent = agents.find((item) => item.id === id);
    try {
      const result = await runModel(specialistInstructions(agent),
        `${context}\n\nความเห็นก่อนหน้า:\n${turns.map((turn) => `${turn.name}: ${turn.answer}`).join("\n\n") || "ยังไม่มี"}\n` +
        (turns.length ? "โต้แย้งหรือปรับข้อเสนอที่มี แล้วสรุปความเห็นของคุณพร้อมเกณฑ์ตรวจ" :
          "เสนอแผนตั้งต้นพร้อมเหตุผลและเกณฑ์ตรวจ"));
      turns.push({ agent: id, name: agent.name, role: agent.role, answer: result.answer });
    } catch (error) {
      const failure = classifyModelError(error);
      if (failure.status === 429) modelRateLimited = true;
      return { ok: false, state: failure.status === 429 ? "paused" : "failed", turns,
        summary: failure.error };
    }
  }
  return { ok: true, turns, plan: turns.at(-1)?.answer || "", summary:
    `ประชุม ${turns.length} agent เสร็จและบันทึกแผนแล้ว; ยังไม่ได้เริ่มงานตามแผน` };
}

const officeWorkflow = createOfficeWorkflow({
  eventFile: join(officeStateDir, "office-actions.jsonl"),
  runSeat: runSeatAction, runMeeting: runMeetingAction,
  getExternalBusy: () => [...activeChatAgents],
});

export function officeLogName(value) {
  return /^[0-9a-f-]{36}-(?:krit|mew|boss)\.txt$/i.test(value);
}

export async function readMessage(req, res) {
  let payload;
  try { payload = await readJson(req); }
  catch { reply(res, 400, { error: "รูปแบบข้อความไม่ถูกต้องหรือยาวเกินกำหนด" }); return null; }
  if (payload === null || typeof payload !== "object" || Array.isArray(payload) ||
      typeof payload.message !== "string" || typeof payload.session !== "string") {
    reply(res, 400, { error: "ข้อความหรือ session ไม่ถูกต้อง" });
    return null;
  }
  const message = payload.message.trim();
  const session = payload.session.trim();
  if (!message || message.length > 4000 || !/^[a-zA-Z0-9-]{8,80}$/.test(session)) {
    reply(res, 400, { error: "ข้อความหรือ session ไม่ถูกต้อง" });
    return null;
  }
  return { message, session };
}

export function classifyModelError(error) {
  const details = String(error?.message || "");
  if (error?.status === 429 || /(?:last status|status):\s*429\b|\b429 Too Many Requests\b/i.test(details))
    return { status: 429, error: quotaMessage };
  if (error?.name === "AbortError")
    return { status: 504, error: "agent ตอบช้าเกินกำหนด" };
  return { status: 502, error: "agent ตอบกลับไม่ได้ โปรดลองอีกครั้ง" };
}

function modelError(res, error) {
  const failure = classifyModelError(error);
  if (failure.status === 429) modelRateLimited = true;
  return reply(res, failure.status, { error: failure.error });
}

export function teamDelegates(results) {
  const limited = results.find((result) => result.status === "rejected" &&
    classifyModelError(result.reason).status === 429);
  if (limited) throw limited.reason;
  const delegates = results.filter((result) => result.status === "fulfilled")
    .map((result) => result.value);
  if (!delegates.length) throw new Error("ผู้เชี่ยวชาญตอบกลับไม่ได้");
  return delegates;
}

async function askAgent(req, res, agent) {
  if (!codexReady) return reply(res, 503, { error: "Codex CLI ยังไม่ได้ล็อกอินด้วย ChatGPT" });
  if (modelRateLimited) return reply(res, 429, { error: quotaMessage });
  if (activeChatAgents.has(agent.id))
    return reply(res, 409, { error: "agent คนนี้กำลังทำงานอยู่" });
  activeChatAgents.add(agent.id);
  try {
    if ((await officeWorkflow.busyAgents()).has(agent.id))
      return reply(res, 409, { error: "agent คนนี้กำลังทำงานอยู่" });
    const payload = await readMessage(req, res);
    if (!payload) return;
    const { message, session } = payload;
    const key = `${session}:${agent.id}`;
    const result = await runModel(specialistInstructions(agent), message, conversations.get(key));
    conversations.set(key, result.id);
    return reply(res, 200, { agent: agent.id, answer: result.answer });
  } catch (error) {
    return modelError(res, error);
  } finally {
    activeChatAgents.delete(agent.id);
  }
}

async function askTeam(req, res) {
  if (!codexReady) return reply(res, 503, { error: "Codex CLI ยังไม่ได้ล็อกอินด้วย ChatGPT" });
  if (modelRateLimited) return reply(res, 429, { error: quotaMessage });
  if (activeChatAgents.has("team")) return reply(res, 409, { error: "หัวหน้าทีมกำลังตอบโจทย์อยู่" });
  activeChatAgents.add("team");
  try {
    const payload = await readMessage(req, res);
    if (!payload) return;
    const { message, session } = payload;
    const teamKey = `${session}:team`;
    const directory = agents.map((a) => `${a.id}: ${a.role} — ${a.focus}`).join("\n");
    const routing = await runModel(
      `คุณคือหัวหน้าทีมสำนักงานเสมือน เลือกผู้เชี่ยวชาญที่จำเป็น 1 ถึง 3 คนจากรายชื่อนี้:\n${directory}\nตอบเพียงรหัส agent คั่นด้วยจุลภาค ห้ามใส่คำอธิบายหรือรหัสอื่น`,
      message,
      teamConversations.get(teamKey),
    );
    const selected = [...new Set(routing.answer.toLowerCase().match(/[a-z]+/g) || [])]
      .map((id) => agents.find((a) => a.id === id))
      .filter(Boolean).slice(0, 3);
    if (!selected.length) selected.push(agents[0]);
    const busy = await officeWorkflow.busyAgents();
    const free = selected.filter((agent) => !busy.has(agent.id) && !activeChatAgents.has(agent.id));
    if (!free.length) return reply(res, 409, { error: "ผู้เชี่ยวชาญที่เลือกกำลังทำงานอยู่" });
    free.forEach((agent) => activeChatAgents.add(agent.id));
    const results = await Promise.allSettled(free.map(async (agent) => {
      const key = `${session}:${agent.id}`;
      try {
        const result = await runModel(specialistInstructions(agent), message, conversations.get(key));
        conversations.set(key, result.id);
        return { id: agent.id, name: agent.name, role: agent.role, answer: result.answer };
      } finally { activeChatAgents.delete(agent.id); }
    }));
    const delegates = teamDelegates(results);
    const notes = delegates.map((d) => `${d.name} (${d.role}): ${d.answer}`).join("\n\n");
    const summary = await runModel(
      "คุณคือหัวหน้าทีมสำนักงานเสมือน สรุปเฉพาะคำตอบของผู้เชี่ยวชาญที่ตอบจริงตามรายชื่อที่ให้เป็นภาษาไทยอย่างชัดเจน ระบุข้อเห็นต่างและข้อมูลที่ยังขาด ห้ามเพิ่มชื่อหรือบทบาทผู้เชี่ยวชาญที่ไม่ได้อยู่ในรายชื่อ ถ้าขาดบทบาทให้บอกว่าไม่มีบทบาทนั้นในทีม ห้ามอ้างว่ามีการลงมือทำภายนอก",
      `โจทย์: ${message}\n\nผู้เชี่ยวชาญที่ตอบจริง:\n${notes}`,
      routing.id,
    );
    teamConversations.set(teamKey, summary.id);
    return reply(res, 200, { agent: "team", answer: summary.answer, delegates });
  } catch (error) {
    return modelError(res, error);
  } finally {
    activeChatAgents.delete("team");
  }
}

export async function handleRequest(req, res) {
  const url = new URL(req.url, "http://localhost");
  const logRequest = url.pathname.match(/^\/api\/office\/logs\/([^/]+)$/);
  if (req.method === "GET" && logRequest) {
    if (!officeLogName(logRequest[1])) return reply(res, 404, { error: "ไม่พบบันทึกงาน" });
    try {
      const content = await readFile(join(officeStateDir, logRequest[1]), "utf8");
      res.writeHead(200, { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" });
      return res.end(content);
    } catch { return reply(res, 404, { error: "ไม่พบบันทึกงาน" }); }
  }
  if (req.method === "GET" && url.pathname === "/api/office/actions") {
    const actions = await officeWorkflow.list();
    const busyAgents = await officeWorkflow.busyAgents();
    for (const id of activeChatAgents) busyAgents.add(id);
    return reply(res, 200, { actions, busyAgents: [...busyAgents] });
  }
  if (req.method === "POST" && ["/api/office/seat", "/api/office/meeting"].includes(url.pathname)) {
    if (req.headers.origin && req.headers.origin !== `http://127.0.0.1:${port}`)
      return reply(res, 403, { error: "คำขอไม่ได้มาจาก Office ในเครื่อง" });
    if (url.pathname.endsWith("/meeting") && !codexReady)
      return reply(res, 503, { error: "Codex CLI ยังไม่ได้ล็อกอินด้วย ChatGPT" });
    if (url.pathname.endsWith("/meeting") && modelRateLimited)
      return reply(res, 429, { error: quotaMessage });
    const started = url.pathname.endsWith("/seat") ? await officeWorkflow.startSeat() :
      await officeWorkflow.startMeeting();
    return started.error ? reply(res, 409, { error: started.error }) :
      reply(res, 202, { action: started.action, alreadyRunning: started.alreadyRunning });
  }
  if (req.method === "GET" && url.pathname === "/api/automation") {
    try {
      const queue = JSON.parse(await readFile(join(root, "automation-jobs.json"), "utf8"));
      let events = [];
      try {
        events = (await readFile(join(automationRoot, ".office-state", "events.jsonl"), "utf8"))
          .split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
      } catch (error) {
        if (error.code !== "ENOENT") throw error;
      }
      const latest = new Map(events.map((event) => [event.jobId, event]));
      return reply(res, 200, {
        maxConcurrent: Math.min(Number(queue.maxConcurrent) || 0, 3),
        jobs: queue.jobs.map((job) => {
          const event = latest.get(job.id);
          return {
            id: job.id, lane: job.lane, agent: job.agent,
            state: event?.state || (job.ready ? "ready" : "paused"),
            at: event?.at || null, branch: event?.branch || null,
            summary: event?.summary || null,
          };
        }),
      });
    } catch {
      return reply(res, 500, { error: "อ่านสถานะงานอัตโนมัติไม่ได้" });
    }
  }
  if (req.method === "GET" && url.pathname === "/api/work-queue") {
    try {
      const queue = JSON.parse(await readFile(join(root, "work-queue.json"), "utf8"));
      return reply(res, 200, queue);
    } catch {
      return reply(res, 500, { error: "อ่านคิวงานไม่ได้" });
    }
  }
  if (req.method === "GET" && url.pathname === "/api/agents")
    return reply(res, 200, { agents: [teamAgent, ...agents], ready: codexReady && !modelRateLimited,
      reason: modelRateLimited ? quotaMessage : null, backend: "codex", model: "Codex ผ่าน ChatGPT" });
  const match = url.pathname.match(/^\/api\/agents\/([a-z]+)\/messages$/);
  if (req.method === "POST" && match) {
    if (match[1] === "team") return askTeam(req, res);
    const agent = agents.find((item) => item.id === match[1]);
    return agent ? askAgent(req, res, agent) : reply(res, 404, { error: "ไม่พบ agent" });
  }
  const files = { "/": ["index.html", "text/html"], "/index.html": ["index.html", "text/html"], "/agent-chat.js": ["agent-chat.js", "text/javascript"], "/work-queue.js": ["work-queue.js", "text/javascript"], "/office-actions.js": ["office-actions.js", "text/javascript"] };
  if (req.method !== "GET" || !files[url.pathname]) return reply(res, 404, { error: "ไม่พบหน้า" });
  try {
    const [name, type] = files[url.pathname];
    const content = await readFile(join(root, name));
    res.writeHead(200, { "Content-Type": `${type}; charset=utf-8`, "Cache-Control": "no-store" });
    res.end(content);
  } catch {
    reply(res, 500, { error: "อ่านไฟล์เว็บไม่ได้" });
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1]))
  createServer((req, res) => {
    Promise.resolve(handleRequest(req, res)).catch(() => {
      if (!res.headersSent) reply(res, 500, { error: "เซิร์ฟเวอร์ประมวลผลคำขอไม่ได้" });
      else res.destroy();
    });
  }).listen(port, "127.0.0.1", () => console.log(`Virtual Office: http://127.0.0.1:${port}`));
