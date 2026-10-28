const stateLabels = {
  ready: "พร้อมรับงาน",
  assigned: "กำลังทำ",
  "review-ready": "รอรีวิว",
  failed: "ล้มเหลว",
  paused: "พักงาน",
};

export function formatAutomationJob(job, name, time) {
  const heading = `${name} · ${job.lane} · ${stateLabels[job.state] || job.state} · ${time}`;
  const details = [];
  if (job.branch) details.push(`สาขา: ${job.branch}`);

  if (job.state === "review-ready" || job.state === "failed") {
    if (job.checkTimedOut) details.push("ตรวจออฟไลน์หมดเวลา");
    else if (job.checkExit === 0) details.push("ตรวจออฟไลน์ผ่าน (exit 0)");
    else if (Number.isInteger(job.checkExit)) details.push(`ตรวจออฟไลน์ไม่ผ่าน (exit ${job.checkExit})`);
    else if (job.state === "review-ready") details.push("ไม่พบผลตรวจออฟไลน์");
  }

  if (job.summary) details.push(job.summary);
  else if (job.state === "failed") details.push("ไม่พบเหตุผลที่บันทึกไว้");
  return { heading, details };
}
