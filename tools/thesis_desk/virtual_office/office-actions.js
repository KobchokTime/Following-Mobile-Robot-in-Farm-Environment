(() => {
  const side = document.querySelector(".side");
  const style = document.createElement("style");
  style.textContent = ".office-action-result{border-top:1px solid var(--line);padding:10px 0;font-size:12px;line-height:1.55}.office-action-result summary{cursor:pointer;font-weight:600}.office-action-result p{margin:5px 0;white-space:pre-wrap;overflow-wrap:anywhere}.action button:disabled{opacity:.55;cursor:wait}.action button.active{border-color:#287e70;background:#12332e;color:#a9f5db}";
  document.head.append(style);
  const panel = document.createElement("section");
  panel.className = "card";
  panel.setAttribute("aria-label", "งานจริงและการประชุมของ agent");
  panel.innerHTML = `<h2>งานจริงและการประชุม</h2>
    <p class="muted">พักผ่อนให้เฉพาะ agent ที่ว่างเดินวน งานที่โต๊ะและการประชุมจะอยู่ที่เดิมจนจบ ปุ่มนั่งเริ่มตรวจโปรเจกต์ ส่วนปุ่มประชุมให้ agent ว่างสูงสุด 3 คนถกแผนผ่าน Codex บัญชี ChatGPT</p>
    <div id="officeActions" aria-live="polite">กำลังอ่านสถานะ…</div>`;
  side.append(panel);
  const output = panel.querySelector("#officeActions");
  const restButton = document.querySelector("#walk");
  const seatButton = document.querySelector("#seat");
  const meetingButton = document.querySelector("#meeting");
  const names = { natee: "Natee", min: "Min", palm: "Palm", fah: "Fah", boss: "Boss",
    ploy: "Ploy", tee: "Tee", june: "June", krit: "Krit", mew: "Mew", art: "Art", dao: "Dao" };
  const labels = { running: "กำลังทำงาน", completed: "เสร็จ", paused: "พักตามโควตา",
    failed: "ไม่ผ่าน", interrupted: "หยุดกลางคัน" };
  const sceneState = new Map();
  const expanded = new Map();
  let restRequested = false;
  let refreshVersion = 0;
  try { restRequested = sessionStorage.getItem("officeRestRequested") === "1"; } catch {}
  restButton.classList.toggle("active", restRequested);
  restButton.setAttribute("aria-pressed", String(restRequested));
  restButton.title = "ให้ agent ที่ว่างเดินพักผ่อน กดอีกครั้งเพื่อหยุด";

  function syncScene(actions, busyAgentIds = []) {
    const desired = new Map();
    const running = actions.filter((item) => item.state === "running");
    for (const action of running)
      for (const id of action.agents) desired.set(id, action.kind);
    const busy = new Set(busyAgentIds);
    const meeting = running.find((action) => action.kind === "meeting");
    let meetingChanged = false;
    for (const id of Object.keys(names)) {
      const next = desired.get(id) || (busy.has(id) ? "chat" : restRequested ? "rest" : "idle");
      const prior = sceneState.get(id);
      if (next === prior) continue;
      if (next === "seat" || next === "chat") window.officeSeat?.([id]);
      else if (next === "meeting") meetingChanged = true;
      else if (next === "rest") window.officeRest?.([id]);
      else if (prior) window.officeIdle?.([id]);
      sceneState.set(id, next);
    }
    if (meetingChanged) window.officeMeeting?.(meeting.agents);
  }

  function text(parent, tag, content, className) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = content;
    parent.append(element);
    return element;
  }

  function render(actions) {
    output.replaceChildren();
    if (!actions.length) {
      text(output, "p", "ยังไม่ได้เริ่มงานหรือประชุม", "muted");
      return;
    }
    for (const action of actions.slice(0, 5)) {
      const card = document.createElement("details");
      card.className = "office-action-result";
      card.open = expanded.has(action.id) ? expanded.get(action.id) :
        action.state === "running" || action === actions[0];
      card.addEventListener("toggle", () => { if (card.isConnected) expanded.set(action.id, card.open); });
      const time = new Date(action.createdAt).toLocaleString("th-TH", {
        timeZone: "Asia/Bangkok", dateStyle: "short", timeStyle: "short",
      });
      text(card, "summary", `${action.kind === "seat" ? "งานที่โต๊ะ" : "ประชุม"} · ${labels[action.state] || action.state}`);
      text(card, "p", `${action.agents.map((id) => names[id] || id).join(", ")} · ${time}`, "muted");
      text(card, "p", action.summary || "", "muted");
      for (const result of action.results || []) {
        const status = result.checkExit === 0 && !result.timedOut ? "ผ่าน" : "ไม่ผ่าน";
        text(card, "p", `${names[result.agent] || result.agent}: ${result.label} · ${status}`);
        text(card, "p", result.analysis || "", "muted");
        if (/^[0-9a-f-]{36}-(?:krit|mew|boss)\.txt$/i.test(result.logName || "")) {
          const link = text(card, "a", "อ่านผลรันดิบ ↗");
          link.href = `/api/office/logs/${result.logName}`;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
        }
      }
      if (action.plan) text(card, "p", action.plan);
      if (action.turns?.length) {
        const details = document.createElement("details");
        text(details, "summary", `อ่านบทสนทนา ${action.turns.length} คน`);
        for (const turn of action.turns)
          text(details, "p", `${turn.name} (${turn.role}): ${turn.answer}`, "muted");
        card.append(details);
      }
      output.append(card);
    }
  }

  async function refresh() {
    const version = ++refreshVersion;
    try {
      const response = await fetch("/api/office/actions", { cache: "no-store" });
      if (!response.ok) throw new Error("อ่านสถานะงานไม่ได้");
      const { actions, busyAgents = [] } = await response.json();
      if (version !== refreshVersion) return null;
      render(actions);
      syncScene(actions, busyAgents);
      const active = actions.filter((action) => action.state === "running");
      seatButton.disabled = active.some((action) => action.kind === "seat");
      meetingButton.disabled = active.some((action) => action.kind === "meeting");
      return Object.keys(names).filter((id) => !busyAgents.includes(id));
    } catch {
      if (version !== refreshVersion) return null;
      output.textContent = "อ่านสถานะงานจากเซิร์ฟเวอร์ไม่ได้";
      return null;
    }
  }

  async function start(kind) {
    refreshVersion++;
    const button = kind === "seat" ? seatButton : meetingButton;
    button.disabled = true;
    try {
      const response = await fetch(`/api/office/${kind}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "เริ่มงานไม่ได้");
      if (!data.alreadyRunning) {
        if (kind === "seat") window.officeSeat?.(data.action.agents);
        else window.officeMeeting?.(data.action.agents);
        for (const id of data.action.agents) sceneState.set(id, kind);
        const message = kind === "seat" ? "เริ่มตรวจโปรเจกต์จริง" : "agent ที่ว่างเริ่มประชุม";
        window.showToast?.(message);
        window.addOfficeLog?.(`${message}: ${data.action.agents.map((id) => names[id] || id).join(", ")}`);
      }
      await refresh();
    } catch (error) {
      window.showToast?.(error.message);
      window.addOfficeLog?.(`เริ่มงานไม่สำเร็จ: ${error.message}`);
      await refresh();
    }
  }

  restButton.addEventListener("click", async () => {
    restRequested = !restRequested;
    try { sessionStorage.setItem("officeRestRequested", restRequested ? "1" : "0"); } catch {}
    restButton.classList.toggle("active", restRequested);
    restButton.setAttribute("aria-pressed", String(restRequested));
    const idle = await refresh();
    if (idle === null) return window.showToast?.("อ่านสถานะ agent ไม่ได้");
    const message = restRequested ? `agent ว่าง ${idle.length} คนกำลังพักผ่อน` : "จบเวลาพักผ่อน";
    window.showToast?.(message);
    window.addOfficeLog?.(message);
  });

  seatButton.addEventListener("click", () => { void start("seat"); });
  meetingButton.addEventListener("click", () => { void start("meeting"); });
  void refresh();
  setInterval(refresh, 5_000);
})();
