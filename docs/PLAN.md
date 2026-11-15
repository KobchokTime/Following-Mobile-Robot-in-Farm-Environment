# แผนงาน 12 สัปดาห์ — Following Robot

อัปเดต: 20 ตุลาคม 2026 (เวลาไทย) · ตกลงร่วมกับผู้ใช้ในการคุยกับ Claude Code
ใช้คู่กับ [`EXECUTION_WORKFLOW.md`](EXECUTION_WORKFLOW.md) (เกณฑ์ผ่านแต่ละ priority) และ [`AGENTS.md`](../AGENTS.md) (วิธีทำงานของ Claude/Codex)

## ข้อตกลงหลัก

| เรื่อง | ข้อตกลง |
|---|---|
| ระยะเวลา | 1–3 เดือน วางแผนไว้ 12 สัปดาห์ (20 ต.ค. 2026 – ประมาณ 15 ม.ค. 2027) |
| เวลากับหุ่นจริง | เดือนละ 2 วัน รวมประมาณ 5 วันตลอดแผน วันที่ยังไม่กำหนด |
| ขอบเขต | ให้หุ่นติดตามคนบนพื้นจริง (closed-loop follower) |
| ความปลอดภัย | **ผู้ใช้ตัดสินใจ:** ไม่ทำ physical E-stop, motor-side watchdog, safety bridge และไม่จำกัดความเร็วในโครงการนี้ ใช้พื้นที่ field test แยก และมีคนประจำจุดหลายคนแทน |
| โค้ดเดิม | logic "target หาย / confidence ต่ำ → หยุด" และระยะหยุดที่มีอยู่แล้วให้คงไว้ เพราะเป็นพฤติกรรมของ follower ที่ต้องวัดผล (quest 7) ไม่ใช่งาน safety ที่เพิ่มใหม่ |
| Simulator | Gazebo (ไม่มี RTX จึงไม่ใช้ Isaac Sim) รันแบบ headless บน cloud และ CI ได้ |
| Quest | quest 11–12 (E-stop, pulse) ตัดออก ส่วน 13 (turn-only และ closed-loop follower) กลับเข้า Main Quest |

ในเล่ม thesis ต้องระบุไว้ในหัวข้อข้อจำกัด (Limitations) ว่าไม่มี hardware E-stop และ motor-side watchdog

## Offline twin: ลดการ SSH เข้าหุ่น

1. **Record & replay:** ในวันหุ่น ใช้ script บันทึกมาตรฐานเก็บ rosbag2 (MCAP) ทุก topic
   (`/image_raw` แบบบีบอัด, `/scan`, `/cmd_vel`, feedback/fault ของมอเตอร์, tf) พร้อม config,
   commit SHA และ scenario label จากนั้น replay ด้วย node เดิมแบบ offline
2. **Docker + driver ปลอม:** image Ubuntu 22.04 + ROS 2 Humble + OpenVINO
   - กล้องปลอมอ่านจากวิดีโอ, LiDAR ปลอมอ่านจาก scan ที่บันทึกไว้, ZLAC ปลอมผ่าน serial จำลอง
   - CI รัน replay test ทุก PR
3. **Gazebo:** URDF หุ่นขับสองล้อ + กล้อง + LiDAR 2D ในฉากฟาร์มที่มีคนเดิน
   - controller ทุกเวอร์ชันต้องผ่าน sim ก่อนลงพื้นจริง
   - ห้ามใช้ภาพจาก sim วัดผล perception

## ไทม์ไลน์

| ช่วง | งาน | Quest | ผู้รับผิดชอบ |
|---|---|---|---|
| สัปดาห์ 1 | ดึงโค้ดทั้งหมดเข้า repo และทำรายการวิดีโอ/bag เดิม | – | Codex |
| สัปดาห์ 1–3 | script บันทึก rosbag บนหุ่น | – | Codex (`robot`) |
| | replay harness, Docker, กล้อง/ZLAC ปลอม, CI | – | Claude (`robot`, `qa`) |
| | Gazebo world และ follower ใน sim | 13 | Claude (`robot`) |
| | checklist วันหุ่น #1 | – | Claude (`research`) |
| 🤖 วันหุ่น #1–2 | เก็บ orientation, target loss, identity และลอง follower บนพื้น | 6, 7, 8, 13 | ผู้ใช้ + Codex |
| สัปดาห์ 4–7 | ประเมิน orientation (macro-F1 ≥ 0.80, coverage ≥ 0.90, p95 ≤ 200 ms), เปรียบเทียบ baseline, ปรับ follower ใน sim | 6, 9, 13 | Claude + Codex (cross-check) |
| 🤖 วันหุ่น #3–4 | conference experiment ≥ 10 scenarios พร้อม follower | 14 | ผู้ใช้ + Codex |
| สัปดาห์ 8–9 | script วิเคราะห์ผล ตารางและกราฟจาก raw data | 18 | Claude |
| 🤖 วันหุ่น #5 | เก็บข้อมูลที่ขาด และทำซ้ำรอบที่มีปัญหา | – | ผู้ใช้ + Codex |
| สัปดาห์ 10–12 | Methodology, Results, ข้อจำกัด แล้ว freeze ผล | 15 | Claude ร่าง / ผู้ใช้เขียน |

**ถ้าได้แค่ 1 เดือน:** ใช้ผลวันหุ่น #1–2 คือ orientation, target loss และ baseline identity แล้วเขียนเป็นงาน perception

## ยังไม่ทราบ

- วันเข้าหุ่นจริง (ผู้ใช้จะแจ้ง)
- ตำแหน่งของโค้ดที่เอกสารอ้างถึงแต่ไม่อยู่ใน repo เช่น Robot Console (`dashboard/`),
  `src/following_robot/motion_safety.py`, tests 121 ข้อ ดูงาน Codex สัปดาห์ 1 ใน `HANDOFF.md`
