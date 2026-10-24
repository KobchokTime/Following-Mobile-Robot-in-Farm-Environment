# Execution Workflow — Conference-ready Following Robot

อัปเดต: 17 กันยายน 2026

## เป้าหมาย

สร้างหุ่นที่เลือกและติดตามคนเป้าหมายได้ รักษาระยะตามที่กำหนด และมีหลักฐานการทดลองที่เพียงพอสำหรับ conference

## หลักการจัดลำดับ

1. งานที่วัดผลไม่ได้ยังไม่นับว่าเสร็จ
2. ทดสอบ perception และ controller แยกกันก่อนรวมระบบ
5. ทุกผลทดลองต้องผูกกับ raw data, config, protocol, code revision และ metrics

## Priority 0 — Reproducible experiment foundation

สถานะ: **กำลังดำเนินการ**

- [x] บันทึกสถานะกล้องและ orientation baseline
- [x] กำหนด schema สำหรับ orientation experiment
- [x] เพิ่มเครื่องมือคำนวณ accuracy, confusion matrix, coverage และ latency
- [x] เพิ่ม validation, evidence manifest และ acceptance verdict
- [x] เพิ่มปุ่มบันทึก raw image/overlay/prediction/label เป็น JSON ใน Robot Console และ export เป็น CSV สำหรับ evaluator
- [x] บันทึก model path/hash, ความละเอียดจริง, เวลาและคะแนน heuristic ของ probe; ยังต้องบันทึก threshold/config ที่ใช้จริงแบบครบถ้วนก่อนยกระดับเป็น verified
- [x] เพิ่ม run ID ต่อ probe; ยังต้องผูก commit SHA และ config snapshot กับทุก run อัตโนมัติ
- [x] เพิ่ม offline readiness checker และ one-day hardware runbook
- [x] ตรวจเส้นทาง timestamp เดิมและกำหนดแผน migration ใน `docs/SOURCE_TIMESTAMP_MIGRATION.md`
- [x] เพิ่ม source-stamped single-person fusion core, ROS wrapper และ sensor stamp audit ที่เริ่มต้นแบบ disabled/uncalibrated

Gate: ผลทดสอบหนึ่งรอบสามารถประมวลผลซ้ำและได้ตัวเลขเดิม

## Priority 1 — Person detection และ orientation

สถานะ: **เริ่มแล้ว แต่ยังไม่ผ่าน gate**

- ตรวจสอบ camera framing ให้เห็นร่างกายเพียงพอ
- สร้าง dataset ขั้นต่ำ FRONT/BACK/LEFT/RIGHT/NO_TARGET
- เปรียบเทียบ pose heuristic กับ orientation classifier
- export โมเดลที่เลือกเป็น OpenVINO
- เพิ่ม temporal smoothing และสถานะ UNCERTAIN
- วัด accuracy, macro-F1, coverage, p50/p95 latency และ FPS

Gate:

- orientation macro-F1 ≥ 0.80 ในชุดทดสอบที่แยกจากชุดพัฒนา
- coverage ≥ 0.90 เมื่อเห็นร่างกายตาม protocol
- p95 latency ≤ 200 ms บน UP Board หรือระบุข้อจำกัดและลด scope
- confidence ต่ำต้องคืน UNCERTAIN ไม่เดาคำตอบ

## Priority 2 — Motor bring-up

- [x] ตรวจ serial mapping, fault/feedback แบบ read-only และสร้าง stable path
  `/dev/following_robot_motor`
- [x] ยกล้อพ้นพื้นและทดสอบ single-wheel/two-wheel pulse ที่ 5 RPM / 0.5 s
- [x] บันทึก logical wheel mapping จากการสังเกตจริงใน
  `config/motor_wheel_calibration.md`
- [ ] ยืนยันทิศทาง/scale ของ encoder ด้วย repeated trials
- [ ] บันทึก command/feedback/fault อย่างน้อย 20 pulse ที่ทำซ้ำได้

## Priority 3 — Minimal closed-loop follower

- เลือกเป้าหมายหนึ่งคนอย่างชัดเจน
- เชื่อม camera bearing กับระยะเป้าหมาย
- ทดสอบ turn-only ก่อน forward motion
- เพิ่ม stop distance, slow zone และ target timeout
- replay rosbag ก่อนทดสอบกับหุ่นจริง

Gate: single-target controlled test 10/10 รอบ ไม่มี collision หรือคำสั่งค้าง

## Priority 4 — Tracking, Re-ID และ target state machine

- [x] กำหนด protocol และ evaluator สำหรับ wrong-follow, coverage, ID switches และเวลาหยุด/กลับมาจับเป้าหมาย (`experiments/identity/`); มีเพียงข้อมูลตัวอย่าง ไม่ใช่ผลบนหุ่น
- [x] เพิ่ม state machine สำหรับ human-selected target แบบ pure Python พร้อม ambiguity/timeout/reacquisition gates; ยังไม่มี embedding ที่วัดผลหรือ ROS integration บนหุ่นจริง
- [x] เพิ่ม JSONL replay สำหรับ state machine เพื่อทดสอบ crossing/target loss แบบไม่ต่อหุ่น
- [x] เพิ่ม ROS adapter แบบปิดโดยค่าเริ่มต้นสำหรับ explicit enrollment และ status-only; ยังไม่มี upstream embedding ที่สอบเทียบหรือ live integration
- [x] เพิ่ม adaptive evidence router แบบอธิบายเหตุผลได้, config, JSONL replay และ ROS status-only adapter; รองรับ motion/range/light embedding/color GMM/pose-shape/strong Re-ID score contract แต่ยังไม่มี producer จริงหรือ calibrated score จากหุ่น
- baseline A: nearest detected person
- baseline B: ByteTrack หรือ BoT-SORT
- proposed: appearance + motion + range reliability
- adaptive policy: เลือก evidence ตามภาพ, orientation, occlusion, จำนวนคน, sensor age/sync และ compute load
- states: SEARCHING, CANDIDATE, LOCKED, LOST, REACQUIRING
- ทดสอบ crossing, occlusion, similar clothing และ target leaving scene

Gate: ผ่านเกณฑ์ ID switch, wrong-follow และ reacquisition ที่กำหนดก่อนเริ่มเก็บผลจริง

## Priority 5 — Conference experiment

- freeze protocol และ config
- อย่างน้อย 10 scenarios และทำซ้ำหลายรอบ
- เก็บ ground truth ของ identity, orientation และ distance
- ทำ baseline comparison และ ablation
- สร้างตารางและกราฟจาก script เท่านั้น

Gate: ทุกตัวเลขย้อนกลับไปยัง raw data และ config ได้

## Workflow ต่อหนึ่ง feature

`Define metric → Create offline test → Implement baseline → Replay recorded data → Hardware read-only test → Record evidence → Analyze → Freeze result`

## งานที่ทำได้เมื่อไม่มีหุ่น

1. ทำ experiment schema และ evaluator
2. label ภาพ/วิดีโอ orientation
3. replay CSV/rosbag เดิม
4. refactor state machine และเขียน unit tests
5. ทำ OpenVINO export pipeline
6. สร้างกราฟ ตาราง และส่วน Methodology

## งานครั้งถัดไปเมื่อเชื่อมหุ่น

1. ตรวจ camera framing และเก็บ orientation dataset รอบแรก
2. วัด Pose/OpenVINO latency 100 เฟรม
3. ตรวจ LiDAR และ timestamps แบบ read-only
4. ทำ motor pulse test
