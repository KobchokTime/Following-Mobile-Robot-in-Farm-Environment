(() => {
  const panel = document.createElement("section");
  panel.className = "project-board";
  panel.setAttribute("aria-label", "คิวงานสามสายของโครงการ");
  panel.innerHTML = `<div class="project-board-head">
    <div><h2>คิวงานสามสาย</h2><p class="muted" id="queueTimestamp">กำลังอ่านข้อมูลที่บันทึกไว้…</p></div>
    <button type="button" id="queueRefresh">อ่านไฟล์คิวอีกครั้ง</button>
  </div>
  <p class="project-caveat">สถานะ PR สามสายด้านบนเป็นบันทึก ณ เวลาที่ระบุ ส่วนสถานะงาน agent ด้านล่างอ่านจากบันทึกการรันในเครื่อง</p>
  <div class="project-details" id="queueLanes"></div>
  <p class="muted" id="queueNext" style="margin-top:12px"></p>
  <div class="project-block" style="margin-top:12px">
    <h3>งานอัตโนมัติของตัวละคร</h3>
    <p class="muted">ปุ่มจัดเข้าที่นั่งเริ่มงานแก้โค้ดที่พร้อมใน clone แยกทันที ส่วนตัวปลุกงานตรวจโควตาก่อนเริ่มงานอัตโนมัติ ผลทั้งสองแบบรอรีวิวก่อนรวม</p>
    <div id="queueAgents" aria-live="polite" style="margin-top:9px">กำลังอ่านสถานะ…</div>
  </div>`;
  document.querySelector(".shell").append(panel);

  const timestamp = panel.querySelector("#queueTimestamp");
  const lanes = panel.querySelector("#queueLanes");
  const next = panel.querySelector("#queueNext");
  const button = panel.querySelector("#queueRefresh");
  const agentJobs = panel.querySelector("#queueAgents");
  const names = { natee: "Natee", min: "Min", palm: "Palm", fah: "Fah", boss: "Boss",
    ploy: "Ploy", tee: "Tee", june: "June", krit: "Krit", mew: "Mew", art: "Art", dao: "Dao" };

  async function loadAutomation() {
    try {
      const response = await fetch("/api/automation", { cache: "no-store" });
      if (!response.ok) throw new Error("status unavailable");
      const data = await response.json();
      agentJobs.replaceChildren();
      if (!data.jobs.length) {
        agentJobs.textContent = "ยังไม่มีงานที่กำหนด";
        return;
      }
      for (const job of data.jobs) {
        const row = document.createElement("p");
        const time = job.at ? new Date(job.at).toLocaleString("th-TH", {
          timeZone: "Asia/Bangkok", dateStyle: "short", timeStyle: "short",
        }) : "ยังไม่เริ่ม";
        row.textContent = `${names[job.agent] || job.agent} · ${job.title || job.lane} · ${job.state} · ${time}` +
          (job.branch ? ` · ${job.branch}` : "");
        agentJobs.append(row);
      }
    } catch {
      agentJobs.textContent = "อ่านสถานะงานอัตโนมัติไม่ได้";
    }
  }

  function render(queue) {
    const date = new Date(queue.recordedAt);
    timestamp.textContent = Number.isNaN(date.getTime())
      ? "ไม่พบเวลาบันทึก"
      : `บันทึก ${date.toLocaleString("th-TH", { timeZone: "Asia/Bangkok", dateStyle: "medium", timeStyle: "short" })} · ฐาน ${queue.baseBranch}`;
    lanes.replaceChildren();
    for (const item of queue.lanes || []) {
      const block = document.createElement("div");
      block.className = "project-block";
      const title = document.createElement("h3");
      title.textContent = item.title;
      const status = document.createElement("p");
      status.textContent = `${item.state} · ${item.owner}`;
      const description = document.createElement("p");
      description.textContent = item.next;
      const evidence = document.createElement("a");
      const url = new URL(item.evidence);
      if (url.protocol === "https:" && url.hostname === "github.com") {
        evidence.href = url.href;
        evidence.target = "_blank";
        evidence.rel = "noopener noreferrer";
        evidence.textContent = "ดู PR และหลักฐาน ↗";
      }
      block.append(title, status, description, evidence);
      lanes.append(block);
    }
    next.textContent = queue.afterMerge || "";
  }

  async function refresh() {
    button.disabled = true;
    try {
      const response = await fetch("/api/work-queue", { cache: "no-store" });
      if (!response.ok) throw new Error("อ่านคิวงานไม่ได้");
      render(await response.json());
    } catch {
      timestamp.textContent = "ไม่สามารถอ่านคิวงานจากเซิร์ฟเวอร์ได้";
      lanes.replaceChildren();
      next.textContent = "";
    } finally {
      button.disabled = false;
    }
  }

  button.addEventListener("click", refresh);
  refresh();
  loadAutomation();
  setInterval(loadAutomation, 30_000);
})();
