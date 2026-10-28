(() => {
  const ids = ["natee", "min", "palm", "fah", "boss", "ploy", "tee", "june", "krit", "mew", "art", "dao"];
  const session = crypto.randomUUID();
  const card = document.createElement("section");
  card.className = "card";
  card.innerHTML = `<h2>คุยกับทีม agent</h2>
    <p class="muted" id="agentStatus">กำลังตรวจการเชื่อมต่อ…</p>
    <label class="muted" for="agentSelect">เลือกตัวละคร</label>
    <select id="agentSelect" style="width:100%;margin:6px 0 10px;padding:9px;background:#172235;color:#edf4ff;border:1px solid #344157;border-radius:9px"></select>
    <div id="agentMessages" role="log" aria-live="polite" style="height:150px;overflow:auto;padding:9px;background:#0c1525;border-radius:9px;font-size:12px;line-height:1.5"></div>
    <form id="agentForm" style="display:flex;gap:6px;margin-top:9px">
      <input id="agentInput" aria-label="ข้อความถึง agent" placeholder="ถามหรือตั้งงานให้ตัวละคร" maxlength="4000" required style="min-width:0;flex:1;padding:9px;background:#172235;color:#edf4ff;border:1px solid #344157;border-radius:9px">
      <button type="submit" style="padding:9px;border:1px solid #328898;background:#17616e;border-radius:9px">ส่ง</button>
    </form>`;
  document.querySelector(".side").append(card);
  const select = card.querySelector("#agentSelect");
  const status = card.querySelector("#agentStatus");
  const messages = card.querySelector("#agentMessages");
  const input = card.querySelector("#agentInput");
  const form = card.querySelector("#agentForm");
  let agents = [];

  function line(author, value) {
    const row = document.createElement("p");
    row.style.margin = "0 0 8px";
    const label = document.createElement("b");
    label.textContent = author + ": ";
    row.append(label, document.createTextNode(value));
    messages.append(row);
    messages.scrollTop = messages.scrollHeight;
  }

  async function loadAgents() {
    try {
      const response = await fetch("/api/agents");
      if (!response.ok) throw new Error("เซิร์ฟเวอร์ยังไม่พร้อม");
      const data = await response.json();
      agents = data.agents;
      select.replaceChildren(...agents.map((agent) => {
        const option = document.createElement("option");
        option.value = agent.id;
        option.textContent = `${agent.name} · ${agent.role}`;
        return option;
      }));
      status.textContent = data.ready ? `หัวหน้าทีมพร้อมมอบงาน · ${data.model}` :
        "ต้องล็อกอิน Codex CLI ด้วย ChatGPT ก่อน";
      window.dispatchEvent(new CustomEvent("office:agent-status", {
        detail: { ready: data.ready, message: status.textContent },
      }));
    } catch {
      status.textContent = "เปิดเว็บผ่าน http://127.0.0.1:8765 เพื่อเชื่อม agent";
      form.querySelector("button").disabled = true;
      window.dispatchEvent(new CustomEvent("office:agent-status", {
        detail: { ready: false, message: "ไม่พบเซิร์ฟเวอร์ agent" },
      }));
    }
  }

  window.addEventListener("office:select-person", (event) => {
    const index = Number(event.detail?.index);
    if (Number.isInteger(index) && ids[index]) {
      select.value = ids[index];
      const agent = agents.find((item) => item.id === ids[index]);
      if (agent) line("ระบบ", `เลือก ${agent.name} · ${agent.role}`);
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = input.value.trim();
    const agent = agents.find((item) => item.id === select.value);
    if (!message || !agent) return;
    window.dispatchEvent(new CustomEvent("office:agent-workflow", {
      detail: { state: "running", agent: agent.id },
    }));
    line("คุณ", message);
    input.value = "";
    input.disabled = true;
    form.querySelector("button").disabled = true;
    try {
      const response = await fetch(`/api/agents/${agent.id}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session, message }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "agent ตอบกลับไม่ได้");
      if (data.delegates?.length) {
        line("ระบบ", "หัวหน้าทีมส่งงานให้ " + data.delegates.map((d) => d.name).join(", "));
        for (const delegate of data.delegates) line(delegate.name, delegate.answer);
      }
      line(agent.name, data.answer);
      window.dispatchEvent(new CustomEvent("office:agent-workflow", {
        detail: { state: "completed", agent: agent.id, delegates: data.delegates || [] },
      }));
    } catch (error) {
      line("ระบบ", error.message);
      window.dispatchEvent(new CustomEvent("office:agent-workflow", {
        detail: { state: "error", agent: agent.id },
      }));
    } finally {
      input.disabled = false;
      form.querySelector("button").disabled = false;
      input.focus();
    }
  });
  loadAgents();
})();

(() => {
  // This is a dated reading of Claude's Follower Test Bench, not a live feed.
  const observedOn = "28 ต.ค. 2026";
  const source = "https://claude.ai/artifact/HTGBVGXXgFjr4S39zD1qA1";
  const styles = document.createElement("style");
  styles.textContent = `
    .project-board{margin-top:16px;border:1px solid var(--line);border-radius:18px;background:var(--panel);padding:18px}
    .project-board-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap}
    .project-board h2{font-size:18px;margin:0 0 5px}.project-board h3{font-size:14px;margin:0 0 12px}
    .project-board p{margin:0}.project-board .source{color:#8ac8ec;font-size:12px;text-decoration:underline;text-underline-offset:3px}
    .project-caveat{margin-top:12px!important;padding:10px 12px;background:#332719;border:1px solid #745a31;border-radius:10px;color:#f3d49c;font-size:12px;line-height:1.6}
    .project-tabs{display:flex;gap:8px;overflow-x:auto;margin:16px 0 14px}
    .project-tabs button{white-space:nowrap;background:#172235;border:1px solid #344157;border-radius:999px;padding:8px 13px;font-size:12px}
    .project-tabs button[aria-selected="true"]{background:#dceaf9;color:#08121d;border-color:#dceaf9;font-weight:700}
    .project-panel[hidden]{display:none}.project-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
    .project-kpi,.project-block{background:#0c1525;border:1px solid #283449;border-radius:12px;padding:14px}
    .project-kpi strong{display:block;font-size:26px;line-height:1.2;color:#dff7ee}.project-kpi span{display:block;margin-top:7px;font-size:11px;color:#aebfd2;line-height:1.5}
    .project-details{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
    .project-block{font-size:12px;line-height:1.7;color:#c8d6e5}.project-block ul{margin:0;padding-left:18px}.project-block li+li{margin-top:5px}
    .project-status{display:inline-flex;align-items:center;gap:7px;padding:5px 10px;border-radius:999px;border:1px solid #416a5d;background:#10231f;color:#86ddb9;font-size:11px}
    .project-status::before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor}
    .project-status[data-state="running"]{background:#312918;border-color:#76602c;color:#f2cb77}
    .project-status[data-state="error"]{background:#341d25;border-color:#80404c;color:#f19ca8}
    .project-status[data-state="offline"]{background:#202634;border-color:#46546b;color:#a7b6c8}
    .project-evidence{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
    .project-evidence div{display:flex;gap:10px;align-items:flex-start;padding:12px;background:#0c1525;border:1px solid #283449;border-radius:10px;font-size:12px;line-height:1.55}
    .project-evidence b{color:#79d7b4}.project-evidence span{color:#b9c9d9}
    @media(max-width:800px){.project-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.project-details{grid-template-columns:1fr}}
    @media(max-width:480px){.project-grid,.project-evidence{grid-template-columns:1fr}}
  `;
  document.head.append(styles);

  const board = document.createElement("section");
  board.className = "project-board";
  board.setAttribute("aria-label", "แดชบอร์ดโครงการหุ่นตามคนในฟาร์ม");
  board.innerHTML = `
    <div class="project-board-head">
      <div><h2>โครงการหุ่นตามคนในฟาร์ม</h2><p class="muted">สรุปหลักฐานจาก Follower Test Bench ของ Claude · สแนปช็อตที่ตรวจดู ${observedOn}</p></div>
      <a class="source" href="${source}" target="_blank" rel="noopener noreferrer">เปิดแดชบอร์ดต้นทาง ↗</a>
    </div>
    <p class="project-caveat">ตัวเลขด้านล่างมาจาก simulation (twin และ Gazebo) ยังไม่ใช่ผลทดสอบบนหุ่นจริง และหน้านี้ไม่ได้เชื่อมข้อมูลสดกับ Claude</p>
    <div class="project-tabs" role="tablist" aria-label="ข้อมูลโครงการ">
      <button type="button" role="tab" id="project-tab-overview" aria-controls="project-overview" aria-selected="true">ภาพรวมการทดลอง</button>
      <button type="button" role="tab" id="project-tab-criteria" aria-controls="project-criteria" aria-selected="false">เกณฑ์ผ่านและงานต่อ</button>
      <button type="button" role="tab" id="project-tab-team" aria-controls="project-team" aria-selected="false">สถานะทีม agent</button>
    </div>
    <div class="project-panel" id="project-overview" role="tabpanel" aria-labelledby="project-tab-overview">
      <div class="project-grid">
        <div class="project-kpi"><strong>27/30</strong><span>ตามคนเดียว · twin สมจริง · เลี้ยวแบบเดิม</span></div>
        <div class="project-kpi"><strong>30/30</strong><span>ตามคนเดียว · twin สมจริง · เลี้ยวตามมุม</span></div>
        <div class="project-kpi"><strong>27/30</strong><span>ตามคนเดียว · Gazebo</span></div>
        <div class="project-kpi"><strong>120/120</strong><span>unit tests ที่แสดงในแดชบอร์ดต้นทาง</span></div>
      </div>
      <div class="project-details">
        <div class="project-block"><h3>สิ่งที่ Claude กำลังทดลอง</h3><p>ทดสอบ gate ด้านข้างแบบเช็กความกำกวม เพื่อคงตัวติดตามเป้าหมายเมื่อมีคนอื่นเดินใกล้กัน ผลรอบนี้ยังเปลี่ยนระหว่างทำงาน จึงดูสถานะล่าสุดที่แดชบอร์ดต้นทาง</p></div>
        <div class="project-block"><h3>วิธีอ่านผล</h3><p>ผลตามคนเดียวใช้ 10 ท่าเดิน × 3 seed ต่อแบบ การผ่านหนึ่งรอบต้องครบทุกเกณฑ์ในแท็บถัดไป ตัวเลข 27/30 และ 30/30 เป็นคนละรูปแบบการเลี้ยว</p></div>
      </div>
    </div>
    <div class="project-panel" id="project-criteria" role="tabpanel" aria-labelledby="project-tab-criteria" hidden>
      <div class="project-evidence">
        <div><b>01</b><span>เป้าหมายยังอยู่ในภาพเมื่อจบรอบ</span></div>
        <div><b>02</b><span>ระยะห่างเมื่อจบรอบไม่เกิน 1.5 เมตร</span></div>
        <div><b>03</b><span>ไม่ชนสิ่งกีดขวางหรือคน</span></div>
        <div><b>04</b><span>เป้าหมายอยู่ในภาพอย่างน้อย 90% ของเวลา</span></div>
      </div>
      <div class="project-details">
        <div class="project-block"><h3>ขั้นต่อไป</h3><ul><li>ติดตามผลรอบ gate ด้านข้างที่ Claude กำลังรัน</li><li>ตรวจรอบที่ไม่ผ่านจาก replay และหลักฐานเส้นทาง</li><li>ทดสอบบนหุ่นจริงก่อนสรุปความพร้อมภาคสนาม</li></ul></div>
        <div class="project-block"><h3>ที่มาของหลักฐาน</h3><p>แดชบอร์ดต้นทางแยกผลตามฉาก seed รูปแบบการทดลอง และ replay ของแต่ละรอบ หน้านี้สรุปเฉพาะค่าฐานที่ตรวจดูได้ และระบุวันที่อ่านข้อมูลไว้เสมอ</p></div>
      </div>
    </div>
    <div class="project-panel" id="project-team" role="tabpanel" aria-labelledby="project-tab-team" hidden>
      <div class="project-details" style="margin-top:0">
        <div class="project-block"><h3>การเชื่อมต่อ agent</h3><p><span class="project-status" id="projectAgentStatus" data-state="offline">กำลังตรวจการเชื่อมต่อ</span></p><p id="projectAgentDetail" style="margin-top:10px">ข้อมูลนี้มาจากเซิร์ฟเวอร์สำนักงานในเครื่อง</p></div>
        <div class="project-block"><h3>งานในหน้าเว็บนี้</h3><p><strong id="projectAgentJobs">0 งาน</strong> ที่ส่งในรอบการเปิดหน้านี้</p><p id="projectAgentLast" style="margin-top:10px">ยังไม่มีคำตอบในรอบนี้</p></div>
      </div>
    </div>`;
  document.querySelector(".shell").append(board);

  const tabs = [...board.querySelectorAll('[role="tab"]')];
  function activate(index) {
    tabs.forEach((tab, i) => {
      const on = i === index;
      tab.setAttribute("aria-selected", String(on));
      board.querySelector(`#${tab.getAttribute("aria-controls")}`).hidden = !on;
    });
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activate(index));
    tab.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const next = (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
      activate(next);
      tabs[next].focus();
    });
  });

  const status = board.querySelector("#projectAgentStatus");
  const detail = board.querySelector("#projectAgentDetail");
  const jobs = board.querySelector("#projectAgentJobs");
  const last = board.querySelector("#projectAgentLast");
  let count = 0;
  window.addEventListener("office:agent-status", (event) => {
    const ready = Boolean(event.detail?.ready);
    status.dataset.state = ready ? "ready" : "offline";
    status.textContent = ready ? "พร้อมรับงาน" : "ยังไม่พร้อม";
    detail.textContent = event.detail?.message || "ไม่พบสถานะเซิร์ฟเวอร์";
  });
  window.addEventListener("office:agent-workflow", (event) => {
    const state = event.detail?.state;
    if (state === "running") {
      status.dataset.state = "running";
      status.textContent = "กำลังทำงาน";
      last.textContent = "ส่งโจทย์ให้ " + (event.detail.agent === "team" ? "หัวหน้าทีม" : "ผู้เชี่ยวชาญ");
    } else if (state === "completed") {
      count += 1;
      jobs.textContent = `${count} งาน`;
      status.dataset.state = "ready";
      status.textContent = "ตอบแล้ว";
      last.textContent = event.detail.delegates?.length ? `หัวหน้าทีมรับคำตอบจาก ${event.detail.delegates.length} ผู้เชี่ยวชาญ` : "ผู้เชี่ยวชาญตอบกลับแล้ว";
    } else if (state === "error") {
      status.dataset.state = "error";
      status.textContent = "ขัดข้อง";
      last.textContent = "ส่งงานไม่สำเร็จ ดูรายละเอียดในช่องสนทนา";
    }
  });
})();
