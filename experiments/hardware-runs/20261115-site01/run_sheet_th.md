# 2026-11-15 site01: ส่วนเสริมของ cheatsheet

ใช้คู่กับ `docs/robot_day_cheatsheet_th.md` (PR #19) ไฟล์นี้มีแค่ส่วนที่ cheatsheet ยังไม่ครอบคลุม
และสิ่งที่ได้เรียนรู้จากวันที่ 7 พ.ย.

**โค้ดที่ใช้:** `~/robot-follow-clean-20261107` บนหุ่น = `codex/robot/field-forward-review @ 026fe17`
(integration-hub + PR #19, CI ผ่าน 3/3)

## ลำดับวันนี้

| # | ทำอะไร | บริดจ์ | ล้อ | เวลา |
| --- | --- | --- | --- | --- |
| 0 | เตรียมหุ่น ล้างดิสก์ แก้ checkout | ปิด | ลอย | 15 นาที |
| 1 | E3: ยืนตรงหน้า 7 ระยะ × หันหน้า/หันหลัง (14 run) | **ปิด** | วางพื้นได้ | 15 นาที |
| 2 | E1: ยืนบนจุดเทป 21 จุด | **ปิด** | วางพื้นได้ | 40 นาที |
| 3 | ทดสอบตัดความเร็ว 0.5 m/s + preflight `--live` | เปิด | **ลอย** | 15 นาที |
| 4 | ให้หุ่นเดินตาม (E6) ตาม cheatsheet หัวข้อ 6–7 | เปิด | พื้น | 60 นาที |

ข้อ 1–2 ทำก่อนเพราะใช้แค่การรับรู้ ไม่มีการเคลื่อนที่ จึงยืนใกล้หุ่นได้อย่างปลอดภัย
(E3 มีระยะ 0.4 m ซึ่งใกล้กว่าระยะตาม 0.5 m ถ้าบริดจ์เปิด หุ่นจะขยับ)

## 0. เตรียมหุ่น (หุ่นบนแท่น ล้อลอย)

```bash
df -h /
```

- ☐ ดิสก์เหลือ ≥ 5 GB ถ้าไม่ถึง: `~/robot_day_recordings` ของวันที่ 7 มีสำเนาครบในโน้ตบุ๊กแล้ว
  (md5 ตรงกันทั้ง 208 ไฟล์) **ลบได้ต่อเมื่อไทม์สั่งเท่านั้น**

```bash
cd ~/robot-follow-clean-20261107 && git status --short --branch && git rev-parse --short HEAD
```

- ☐ HEAD = `026fe17` และไม่มีไฟล์ที่แก้ค้าง

หุ่นไม่มี MCAP plugin ต้องเปลี่ยนเป็น sqlite3 (ตัวอัดจะบันทึก diff นี้ไว้ใน `worktree.patch` ของแต่ละ run เอง):

```bash
sed -i 's/--storage mcap/--storage sqlite3/g; s/"storage_id": "mcap"/"storage_id": "sqlite3"/' ros2_yolo_ws/scripts/record_robot_day.sh
```

launch เรียก `python3` สำหรับทุก node แต่ ultralytics มีแค่ใน `~/openvino_env`
ให้เปิด venv **ก่อน** launch แล้วเช็คว่าทุก node import ได้:

```bash
source /opt/ros/humble/setup.bash && source ~/ydlidar_ros2_ws/install/setup.bash && source ~/openvino_env/bin/activate
python3 -c "import rclpy, cv_bridge, ultralytics, numpy, minimalmodbus; print('imports ok')"
```

- ☐ ขึ้น `imports ok` ถ้าขาด `minimalmodbus` ให้ติดตั้งลง venv ด้วย `pip install minimalmodbus`
  (ต้องใช้แค่ตอนเปิดบริดจ์ ขั้น 3 เป็นต้นไป)
- ☐ copy `run_check.py` จากโน้ตบุ๊กไป `~/run_check.py`

## 1–2. E3 และ E1 (บริดจ์ปิด)

ทุก terminal ต้อง source ROS + ydlidar + venv เหมือนขั้น 0

```bash
ros2 launch ros2_yolo_ws/launch/follow_bringup.launch.py bridge:=false \
    camera_cmd:="ros2 run v4l2_camera v4l2_camera_node --ros-args -p video_device:=/dev/video0" \
    lidar_cmd:="ros2 launch ydlidar_ros2_driver x3_ydlidar_launch.py params_file:=/home/yakgreen001/ydlidar_tmini.yaml"
```

อัดแต่ละจุด แล้ว**เช็คทันที**ก่อนย้ายไปจุดต่อไป:

```bash
ros2_yolo_ws/scripts/record_robot_day.sh --scenario e1_b-20_d2.0 --countdown 10 --duration 10 && python3 ~/run_check.py
```

- `OK` = ไปจุดต่อไป · `RETAKE` = ยืนให้ตรงจุดแล้วอัดชื่อเดิมซ้ำ (run เก่าไม่ต้องลบ ตอนวิเคราะห์จะใช้ run ล่าสุดที่ผ่าน)
- run_check เป็นแค่การจับข้อผิดพลาดใหญ่ (ล็อกเป้าไม่ถึง 50%, มุมคลาดเกิน 8°, ระยะคลาดเกิน 0.4 m)
  ไม่ใช่ผล E1

**E3** ยืนตรงหน้า (มุม 0°): `e3_d<ระยะ>_front` และ `e3_d<ระยะ>_back` ที่ระยะ 0.4, 0.5, 0.75, 1.0, 1.5, 2, 3 m
run_check จะไม่ตรวจมุมของ E3 ดูแค่จำนวนเฟรมกับการล็อก
(หันหลังอาจล็อกได้น้อยกว่า ถ้าเป็นแบบนี้จริงก็ถือเป็นผลการทดลอง ไม่ต้องอัดซ้ำ)

**E1** จุดเทปวัดจากกึ่งกลางหุ่นไปถึงกึ่งกลางลำตัวคน **ซ้ายของหุ่น = มุมบวก**
x = ระยะไปข้างหน้า, y = ระยะไปทางซ้าย (ค่าลบ = ไปทางขวา)

| มุม | d = 1 m (x, y) | d = 2 m (x, y) | d = 3 m (x, y) |
| --- | --- | --- | --- |
| −30° | 0.87, −0.50 | 1.73, −1.00 | 2.60, −1.50 |
| −20° | 0.94, −0.34 | 1.88, −0.68 | 2.82, −1.03 |
| −10° | 0.98, −0.17 | 1.97, −0.35 | 2.95, −0.52 |
| 0° | 1.00, 0.00 | 2.00, 0.00 | 3.00, 0.00 |
| +10° | 0.98, +0.17 | 1.97, +0.35 | 2.95, +0.52 |
| +20° | 0.94, +0.34 | 1.88, +0.68 | 2.82, +1.03 |
| +30° | 0.87, +0.50 | 1.73, +1.00 | 2.60, +1.50 |

ชื่อ scenario: `e1_b<มุม>_d<ระยะ>` เช่น `e1_b-30_d1.0`, `e1_b0_d2.0`, `e1_b20_d3.0`
(ระยะใช้ทศนิยมหนึ่งตำแหน่ง มุมเป็นจำนวนเต็ม **ห้ามใส่เครื่องหมาย +** เพราะ analyze.py จะอ่านชื่อนั้นไม่ได้)
กล้อง HFOV 70° (±35°): ที่ ±30° คนจะอยู่ใกล้ขอบภาพ ถ้าล็อกไม่ได้ ให้จดไว้ แล้วไปจุดต่อไป

## 3. ทดสอบตัดความเร็ว (ล้อลอย, บริดจ์เปิด)

ตรวจจากโค้ดแล้ว: บริดจ์ตัดความเร็วล้อแต่ละข้างไว้ที่ `max_speed_mps`
**แต่ค่า default ใน launch คือ `max_speed_mps=1.4` และ `forward_dir=1.0`**
ถ้าลืมใส่ 2 ค่านี้ หุ่นจะวิ่งเร็วถึงราว 0.97 m/s และเดินหน้ากลายเป็นถอยหลัง

ปิด launch ของขั้น 1–2 ก่อน แล้วเปิดใหม่:

```bash
ros2 launch ros2_yolo_ws/launch/follow_bringup.launch.py \
    max_speed_mps:=0.5 wheel_radius_m:=0.085 forward_dir:=-1.0 turn_dir:=1.0 \
    camera_cmd:="ros2 run v4l2_camera v4l2_camera_node --ros-args -p video_device:=/dev/video0" \
    lidar_cmd:="ros2 launch ydlidar_ros2_driver x3_ydlidar_launch.py params_file:=/home/yakgreen001/ydlidar_tmini.yaml"
```

```bash
python3 tools/robot_day/preflight.py --live --max-speed 0.5 --wheel-radius 0.085 \
    --expect-forward-dir -1.0 --expect-turn-dir 1.0 --obstacle-stop true --avoid-trail false
```

- ☐ `ready` และ FAIL = 0

**ทดสอบตัดความเร็ว** (Claude จะสั่งก็ต่อเมื่อไทม์พิมพ์ยืนยันเองว่า "ล้อลอยและ spotter พร้อม"):
ออกจากหน้ากล้องก่อน (follow_stop จะได้ไม่ส่ง `/cmd_vel` ซ้อน) แล้วส่ง 1.0 m/s เป็นเวลา 2 วินาที

```bash
ros2 topic pub -r 10 -t 20 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 1.0}}"
```

- ☐ log ของบริดจ์แสดง `0x2088` และ `0x2089` ไม่เกิน ±56.2 rpm (= 0.5 m/s ที่ r = 0.085 m)
  ถ้าเกิน **หยุด ห้ามวางลงพื้น**
- ☐ ล้อหยุดภายใน ~1.5 s หลังคำสั่งหมด (timeout 1.0 s + ช่วงลดความเร็ว 0.5 s)

## 4. เดินตาม (E6)

ทำตาม cheatsheet หัวข้อ 6–7 ด้วยคำสั่ง launch ของขั้น 3 เท่านั้น
- เงื่อนไขก่อนวางลงพื้น: ไม่มีใครอยู่ในรัศมี 3 m นอกจากคนที่ให้หุ่นตาม และมี spotter พร้อมตัดไฟ
- หลังแต่ละ run: `python3 ~/run_check.py` (E6 ดูแค่ว่าล็อกเป้าได้ต่อเนื่องไหม)
