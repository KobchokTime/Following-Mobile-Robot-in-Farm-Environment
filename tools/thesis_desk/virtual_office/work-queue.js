(() => {
  const panel = document.createElement("section");
  panel.className = "project-board";
  panel.setAttribute("aria-label", "คิวงานสามสายของโครงการ");
  panel.innerHTML = `<div class="project-board-head">
    <div><h2>คิวงานสามสาย</h2><p class="muted" id="queueTimestamp">กำลังอ่านข้อมูลที่บันทึกไว้…</p></div>
    <button type="button" id="queueRefresh">อ่านไฟล์คิวอีกครั้ง</button>
  </div>
  <p class="project-caveat">สถานะนี้เป็นบันทึก ณ เวลาที่ระบุ ไม่ใช่ข้อมูลสดหรือการสั่งให้ agent ทำงานอัตโนมัติ</p>
  <div class="project-details" id="queueLanes"></div>
  <p class="muted" id="queueNext" style="margin-top:12px"></p>`;
  document.querySelector(".shell").append(panel);

  const timestamp = panel.querySelector("#queueTimestamp");
  const lanes = panel.querySelector("#queueLanes");
  const next = panel.querySelector("#queueNext");
  const button = panel.querySelector("#queueRefresh");

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
})();
