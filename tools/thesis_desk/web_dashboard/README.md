# Thesis Field Notes — web dashboard ของ Codex

เว็บทางเลือกสำหรับดูเควสจาก `../thesis_data.json` ของ Thesis Desk (รุ่น Tkinter/Godot ที่มีอยู่ใน repo) ใช้ HTML/CSS/JavaScript ธรรมดา ไม่ต้องติดตั้ง package และไม่เชื่อมต่อหุ่นยนต์

ภาพตัวอย่าง: [preview.png](preview.png)

จาก **root ของ repo** รัน:

```bash
python3 -m http.server 8000
```

แล้วเปิด `http://localhost:8000/tools/thesis_desk/web_dashboard/`

- ภาพรวม, เส้นทาง Main Quest, ค้นหาและกรองงาน, รายการไฟล์อ้างอิง
- คลิกงานเพื่อแก้สถานะ ความสำคัญ วันส่ง และโน้ต การแก้ไขอยู่ใน `localStorage` ของเบราว์เซอร์นี้; ไฟล์ต้นทางไม่ถูกเขียนทับ
- ปุ่ม **ส่งออกข้อมูล** ดาวน์โหลด JSON ที่รวมการแก้ไข ถ้าจะนำไปใช้ใน tracker เดิม ให้ตรวจและนำเข้าด้วยตัวเอง
- ปุ่ม **คืนค่าข้อมูลตั้งต้น** ลบเฉพาะการแก้ไขในเบราว์เซอร์นี้

สร้างไว้ให้เทียบวิธีนำเสนอและการใช้งานกับ Thesis Desk ของ Claude โดยไม่เปลี่ยนแอปเดิม
