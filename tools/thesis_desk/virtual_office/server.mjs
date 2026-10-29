import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";
import { spawn, spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";

const root = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(root, "../../..");
const automationRoot = resolve(process.env.OFFICE_WORKTREE_ROOT || join(dirname(repoRoot), "office-agent-worktrees"));
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

const runModel = runCodex;

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
  if (/(?:last status|status):\s*429\b|\b429 Too Many Requests\b/i.test(details))
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
  const payload = await readMessage(req, res);
  if (!payload) return;
  const { message, session } = payload;
  const key = `${session}:${agent.id}`;
  try {
    const result = await runModel(specialistInstructions(agent), message, conversations.get(key));
    conversations.set(key, result.id);
    return reply(res, 200, { agent: agent.id, answer: result.answer });
  } catch (error) {
    return modelError(res, error);
  }
}

async function askTeam(req, res) {
  if (!codexReady) return reply(res, 503, { error: "Codex CLI ยังไม่ได้ล็อกอินด้วย ChatGPT" });
  if (modelRateLimited) return reply(res, 429, { error: quotaMessage });
  const payload = await readMessage(req, res);
  if (!payload) return;
  const { message, session } = payload;
  const teamKey = `${session}:team`;
  try {
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
    const results = await Promise.allSettled(selected.map(async (agent) => {
      const key = `${session}:${agent.id}`;
      const result = await runModel(specialistInstructions(agent), message, conversations.get(key));
      conversations.set(key, result.id);
      return { id: agent.id, name: agent.name, role: agent.role, answer: result.answer };
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
  }
}

export async function handleRequest(req, res) {
  const url = new URL(req.url, "http://localhost");
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
            checkExit: Number.isInteger(event?.checkExit) ? event.checkExit : null,
            checkTimedOut: event?.checkTimedOut === true,
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
  const files = { "/": ["index.html", "text/html"], "/index.html": ["index.html", "text/html"], "/agent-chat.js": ["agent-chat.js", "text/javascript"], "/work-queue.js": ["work-queue.js", "text/javascript"], "/automation-status.mjs": ["automation-status.mjs", "text/javascript"] };
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
