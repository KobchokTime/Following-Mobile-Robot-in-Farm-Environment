# Motion Safety Gate — Offline RPM Proposal Core

อัปเดต: 16 กันยายน 2026

`src/following_robot/motion_safety.py` เป็น safety gate แบบ pure Python ที่รับ
body-velocity proposal แล้วคืนค่า **wheel RPM proposal** เท่านั้น ไม่มี ROS, serial, GPIO,
camera, clock, subprocess หรือ driver import และไม่สามารถสั่งมอเตอร์จริงได้

```
SafeFollowController proposal + DriveHealth snapshot
                  ↓
          MotionSafetyGate
                  ↓
       WheelRpmProposal (no I/O)
```

## Invariants ที่ enforce ใน code

1. เริ่มต้นเป็น `DISARMED` และ output เป็น `0 RPM, 0 RPM`
2. ต้อง `start_arm_session(token)` แล้ว `arm(token, now, health)` ด้วย token เดียวกัน
3. Arm จะผ่านต่อเมื่อ E-stop อยู่ในสถานะ released, fault ซ้าย/ขวาเป็นศูนย์, feedback valid
   และ health snapshot สดตาม timeout
4. ทุกครั้งที่ evaluate ต้องมี proposal และ health ที่ fresh; future, stale, missing หรือ invalid
   input คืนศูนย์
5. Differential-drive mixing คำนวณซ้าย/ขวาจาก linear/angular proposal แล้ว clamp ตาม RPM bound
6. คำสั่งเคลื่อนที่ปกติเปลี่ยนไม่เกิน `max_rpm_change_per_s × elapsed time`; safety stop เป็นข้อยกเว้นและคืนศูนย์ทันที
7. fault, E-stop, feedback invalid, stop gate, session reset และ `disarm()` ล้าง RPM ที่จดจำเป็นศูนย์
8. `disarm()` invalidate token เดิม; ต้องเปิด session ใหม่ก่อน arm อีกครั้ง
9. การขอ arm โดยไม่มี session หรือ token ผิดจะล้าง session ทันที; proposal/health ที่ขาด เก่า ผิดปกติ, fault หรือ E-stop จะคืนศูนย์และปลด arm ค้าง ไม่เริ่มหมุนอีกเองเมื่อข้อมูลกลับมา
10. คำสั่งศูนย์เป็น safety stop: ข้ามตัวจำกัดความชันรอบและคืน `0 RPM` ในการประเมินครั้งนั้นทันที; เวลาไม่เพิ่มหรือข้อมูลผิดชนิดก็คืนศูนย์และล้าง session

## ขอบเขตที่ยังไม่สามารถกล่าวอ้างได้

นี่ไม่ใช่ hardware watchdog และไม่ใช่ transport driver จึงยังไม่ได้พิสูจน์ว่า:

- E-stop ทางกายภาพตัด motor power จริง
- feedback ที่ได้ตรงกับล้อที่กำลังหมุน
- ZLAC8015D รับหรือ execute RPM proposal ถูกต้อง
- serial disconnect ทำให้ driver หยุดภายในเวลาที่กำหนด

ชั้น transport ฝั่งหุ่นต้องมี watchdog ของตัวเอง, stable serial path, fault gate ที่อ่านจริง,
คำสั่ง zero เมื่อ transport หาย และผ่าน motor pulse protocol โดยยกล้อพ้นพื้นก่อน

## ตรวจแบบออฟไลน์

```powershell
python -m unittest tests/test_motion_safety.py -v
python -m unittest discover -s tests -v
```

ชุดทดสอบครอบคลุม token/session, default disarm, stale/future proposal, fault/E-stop/feedback
gates, invalid values, differential mixing, RPM saturation, ramp limit และ zero/disarm invariant
โดยไม่เชื่อมต่อหุ่น
