(() => {
  const side = document.querySelector(".side");
  const style = document.createElement("style");
  style.textContent = ".office-action-result{border-top:1px solid var(--line);padding:10px 0;font-size:12px;line-height:1.55}.office-action-result summary{cursor:pointer;font-weight:600}.office-action-result p{margin:5px 0;white-space:pre-wrap;overflow-wrap:anywhere}.action button:disabled{opacity:.55;cursor:wait}";
  document.head.append(style);
  const panel = document.createElement("section");
  panel.className = "card";
  panel.setAttribute("aria-label", "งานจริงและการประชุมของ agent");
  panel.innerHTML = `<h2>งานจริงและการประชุม</h2>
    <p class="muted">ปุ่มนั่งเริ่มตรวจโปรเจกต์ในเครื่องและบันทึกผล ปุ่มประชุมเลือก agent ที่ว่างสูงสุด 3 คนมาถกแผนผ่าน Codex บัญชี ChatGPT</p>
    <div id="officeActions" aria-live="polite">กำลังอ่านสถานะ…</div>`;
  side.append(panel);
  const output = panel.querySelector("#officeActions");
  const seatButton = document.querySelector("#seat");
  const meetingButton = document.querySelector("#meeting");
  const names = { natee: "Natee", min: "Min", palm: "Palm", fah: "Fah", boss: "Boss",
    ploy: "Ploy", tee: "Tee", june: "June", krit: "Krit", mew: "Mew", art: "Art", dao: "Dao" };
  const labels = { running: "กำลังทำงาน", completed: "เสร็จ", paused: "พักตามโควตา",
    failed: "ไม่ผ่าน", interrupted: "หยุดกลางคัน" };
  const sceneState = new Map();
  const expanded = new Map();

  function syncScene(actions) {
    const desired = new Map();
    for (const action of actions.filter((item) => item.state === "running"))
      for (const id of action.agents) desired.set(id, action.kind);
    for (const id of Object.keys(names)) {
      const next = desired.get(id);
      const prior = sceneState.get(id);
      if (next === prior) continue;
      if (next === "seat") window.officeSeat?.([id]);
      else if (next === "meeting") window.officeMeeting?.([id]);
      else if (prior) window.officeWalk?.([id]);
      if (next) sceneState.set(id, next);
      else sceneState.delete(id);
    }
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
    try {
      const response = await fetch("/api/office/actions", { cache: "no-store" });
      if (!response.ok) throw new Error("อ่านสถานะงานไม่ได้");
      const { actions } = await response.json();
      render(actions);
      syncScene(actions);
      const active = actions.filter((action) => action.state === "running");
      seatButton.disabled = active.some((action) => action.kind === "seat");
      meetingButton.disabled = active.some((action) => action.kind === "meeting");
    } catch {
      output.textContent = "อ่านสถานะงานจากเซิร์ฟเวอร์ไม่ได้";
    }
  }

  async function start(kind) {
    const button = kind === "seat" ? seatButton : meetingButton;
    button.disabled = true;
    try {
      const response = await fetch(`/api/office/${kind}`, { method: "POST" });
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

  seatButton.addEventListener("click", () => { void start("seat"); });
  meetingButton.addEventListener("click", () => { void start("meeting"); });
  void refresh();
  setInterval(refresh, 5_000);
})();
