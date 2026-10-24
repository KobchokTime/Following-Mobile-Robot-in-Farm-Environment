"""Thai desktop thesis tracker. Standard library only (Tkinter + JSON)."""

from __future__ import annotations

import json
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import messagebox, ttk


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "thesis_data.json"
SOURCE_ROOT = BASE_DIR.parents[1]
BG = "#f3f6f4"
PANEL = "#ffffff"
INK = "#1b2b25"
MUTED = "#718078"
GREEN = "#1e7655"
PALE_GREEN = "#e4f2eb"
LINE = "#e5ebe7"
AMBER = "#a96313"
RED = "#aa4b46"

STATUSES = ["รอเริ่ม", "กำลังทำ", "เสร็จแล้ว", "ติดเงื่อนไข", "พักไว้"]
PRIORITIES = ["สูง", "กลาง", "ต่ำ"]
PHASES = [
    "Orientation & perception",
    "Target tracking & Re-ID",
    "Robot integration",
    "Experiments & analysis",
    "Thesis writing",
]

MAIN_QUEST_IDS = [6, 7, 8, 9, 13, 14, 18, 15]
MAIN_QUEST_GOALS = {
    6: "เก็บผล orientation ซ้ำหลายสภาพ และประเมินตามเกณฑ์ที่กำหนด",
    7: "พิสูจน์ว่าระบบหยุดเมื่อ target หายและกลับมาจับได้",
    8: "สร้าง identity ground truth จากสถานการณ์จริง ไม่ใช้ข้อมูล synthetic แทนผลจริง",
    9: "เปรียบเทียบ baseline และวัด wrong-follow, coverage, ID switch, reacquisition",
    13: "ทดสอบ turn-only และ closed-loop follower ตามเกณฑ์ที่กำหนด",
    14: "ทำซ้ำอย่างน้อย 10 scenarios พร้อม raw data, ground truth และ baseline/ablation",
    18: "สรุป metrics จากข้อมูลที่ตรวจสอบย้อนกลับไปยัง raw evidence ได้",
    15: "เขียนเล่มจากผลที่ยืนยันได้ พร้อมข้อจำกัดและแหล่งอ้างอิง",
}

ROBOT_SLOTS = ["Camera", "Vision AI", "Orientation", "Target ID", "Controller", "Range"]
EQUIPMENT = [
    {"name": "Logitech C922 Camera", "slot": "Camera", "requires": [10], "kind": "VERIFIED SENSOR"},
    {"name": "YOLOv8n OpenVINO", "slot": "Vision AI", "requires": [3], "kind": "DETECTOR"},
    {"name": "Resident Pose Service", "slot": "Orientation", "requires": [4], "kind": "POSE MODULE"},
    {"name": "Identity Protocol Kit · offline", "slot": "Target ID", "requires": [17], "kind": "RESEARCH MODULE"},
    {"name": "ZLAC8015D · READ ONLY", "slot": "Controller", "requires": [10], "kind": "STOPPED CONTROLLER"},
    {"name": "2D LiDAR Module", "slot": "Range", "requires": [], "kind": "LOCKED · SENSOR NOT VERIFIED", "locked": True},
]


def decorate_quests(data: dict) -> dict:
    """Add the RPG quest route while preserving the user's task edits."""
    tasks = data.setdefault("tasks", [])
    if not any(int(t.get("id", -1)) == 17 for t in tasks):
        tasks.append({"id": 17, "title": "เตรียม identity protocol และ offline evaluator", "phase": "Target tracking & Re-ID",
                      "priority": "กลาง", "status": "เสร็จแล้ว", "due": "",
                      "notes": "มี protocol, evaluator, state machine และ replay สำหรับตรวจ logic แล้ว; ยังไม่ใช่ผล benchmark บนหุ่นจริง",
                      "source": "experiments/identity/README.md · src/following_robot/target_identity.py",
                      "quest_type": "Side Quest", "quest_no": 1, "quest_order": 1, "reward_xp": 30})
    if not any(int(t.get("id", -1)) == 18 for t in tasks):
        tasks.append({"id": 18, "title": "วิเคราะห์ผลและจัดทำตาราง/กราฟจากข้อมูลจริง", "phase": "Experiments & analysis",
                      "priority": "สูง", "status": "รอเริ่ม", "due": "",
                      "notes": "ตรวจความครบถ้วนของ raw data, ground truth และ config ก่อนคำนวณ metrics; แยกผลจริงออกจากตัวอย่างและ replay จำลอง",
                      "source": "docs/EXECUTION_WORKFLOW.md · experiments/orientation/README.md",
                      "quest_type": "Main Quest", "quest_no": 9, "quest_order": 9, "reward_xp": 100})
    by_id = {int(t.get("id", -1)): t for t in tasks}
    for order, task_id in enumerate(MAIN_QUEST_IDS, start=1):
        task = by_id.get(task_id)
        if task is None:
            continue
        task.update({"quest_type": "Main Quest", "quest_no": order, "quest_order": order,
                     "reward_xp": 100, "quest_goal": MAIN_QUEST_GOALS[task_id],
                     "depends_on": MAIN_QUEST_IDS[order - 2] if order > 1 else None})
    side_ids = [1, 2, 3, 4, 5, 10, 16, 17]
    for order, task_id in enumerate(side_ids, start=1):
        task = by_id.get(task_id)
        if task is not None:
            task.update({"quest_type": "Side Quest", "quest_no": order, "quest_order": order,
                         "reward_xp": 30, "quest_goal": "งานสนับสนุน ทำเมื่อสะดวก ไม่ขวางเส้นทาง Main Quest",
                         "depends_on": None})
    project = data.setdefault("project", {})
    project["quest_guide"] = {
        "main_quest": "เส้นเรื่องหลัก 8 ด่าน ด่านถัดไปปลดล็อกเมื่อด่านก่อนหน้าเสร็จ",
        "side_quest": "งานเสริมและเครื่องมือสนับสนุน ทำแยกได้ ไม่บล็อก Main Quest",
        "main_quest_count": len(MAIN_QUEST_IDS),
    }
    if not project.get("quest_mode_simplified_v1"):
        clean_notes = {
            1: "วาง workflow ออฟไลน์และเกณฑ์ประเมินไว้แล้ว: offline → replay → read-only hardware → experiment",
            7: "เก็บภาพ/สถานะพร้อมเวลา และบันทึกช่วง target หายกับกลับมาเพื่อประเมิน reacquisition",
            14: "freeze protocol/config, ทำซ้ำหลายรอบ, เก็บ ground truth ของ identity/orientation/distance และทำ baseline/ablation; ทุกตัวเลขย้อนถึง raw data ได้",
        }
        for task in tasks:
            task_id = int(task.get("id", -1))
            if task_id in clean_notes and not task.get("archived"):
                task["notes"] = clean_notes[task_id]
        project["quest_mode_simplified_v1"] = True
    game_state = data.setdefault("game_state", {})
    game_state.setdefault("character_name", "นักวิจัยฝึกหัด")
    game_state.setdefault("robot_name", "FARM-01")
    equipped = game_state.setdefault("equipped", {})
    defaults = {"Camera": "Logitech C922 Camera", "Vision AI": "YOLOv8n OpenVINO",
                "Orientation": "Resident Pose Service", "Target ID": "Identity Protocol Kit · offline",
                "Controller": "ZLAC8015D · READ ONLY", "Range": ""}
    for slot, item in defaults.items():
        equipped.setdefault(slot, item)
    return data


def load_data() -> dict:
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("tasks"), list):
                return decorate_quests(data)
        except (OSError, json.JSONDecodeError):
            pass
    source = str(SOURCE_ROOT)
    tasks = [
        {"id": 1, "title": "วาง workflow และเกณฑ์ผ่านของงานวิจัย", "phase": "Experiments & analysis", "priority": "สูง", "status": "เสร็จแล้ว", "due": "", "notes": "กำหนดลำดับ offline → replay → hardware read-only → test และเกณฑ์ conference-ready ไว้แล้ว", "source": "docs/EXECUTION_WORKFLOW.md"},
        {"id": 2, "title": "ทำระบบเก็บและประเมินหลักฐาน orientation", "phase": "Orientation & perception", "priority": "กลาง", "status": "เสร็จแล้ว", "due": "", "notes": "มี protocol, CSV schema, evaluator และการ export run แล้ว; ต้องใช้ข้อมูลจริงให้ครบก่อนสรุปผล", "source": "experiments/orientation/README.md"},
        {"id": 3, "title": "ทดสอบ detector OpenVINO 320×320 บนกล้องจริง", "phase": "Orientation & perception", "priority": "กลาง", "status": "เสร็จแล้ว", "due": "", "notes": "บันทึกประมาณ 14 FPS และ P95 latency ราว 72 ms; ผลนี้ยืนยัน throughput ของ detector เท่านั้น", "source": "experiments/camera/2026-09-20_camera_only_start.md"},
        {"id": 4, "title": "ทำ resident pose service และ temporal voting", "phase": "Orientation & perception", "priority": "กลาง", "status": "เสร็จแล้ว", "due": "", "notes": "บริการ OpenVINO ทำงานต่อเนื่อง มี 7-frame voting และส่งสถานะ UNCERTAIN ได้; ยังเป็น advisory และไม่ควบคุมมอเตอร์", "source": "experiments/camera/2026-09-20_camera_only_start.md"},
        {"id": 5, "title": "ผ่าน guided orientation sequence รอบแรก", "phase": "Orientation & perception", "priority": "ต่ำ", "status": "เสร็จแล้ว", "due": "", "notes": "มีรายงาน FRONT → BACK → LEFT → RIGHT → NO_TARGET ผ่านหนึ่งรอบ; ใช้เป็น development check ไม่ใช่ผลความแม่นยำตีพิมพ์", "source": "experiments/camera/2026-09-20_camera_only_start.md"},
        {"id": 6, "title": "เก็บ orientation trials ซ้ำหลายสภาพแวดล้อม", "phase": "Orientation & perception", "priority": "สูง", "status": "กำลังทำ", "due": "", "notes": "เก็บหลายระยะ แสง เสื้อผ้า การบังบางส่วน และมุมกึ่งกลาง ทำ ground truth จากภาพจริง แล้วประเมิน macro-F1, coverage, P95 และ FPS", "source": "docs/EXECUTION_WORKFLOW.md · experiments/orientation/README.md"},
        {"id": 7, "title": "บันทึกการทดลอง target loss และ reacquisition", "phase": "Target tracking & Re-ID", "priority": "สูง", "status": "รอเริ่ม", "due": "", "notes": "รันทดสอบ FRONT → NO_TARGET → FRONT; ต้องเก็บภาพ/สถานะพร้อมเวลา และยืนยัน motor_commands = 0 ตลอดการทดลอง", "source": "experiments/camera/2026-09-20_camera_only_start.md"},
        {"id": 8, "title": "เก็บชุดข้อมูล target identity จากสถานการณ์จริง", "phase": "Target tracking & Re-ID", "priority": "สูง", "status": "รอเริ่ม", "due": "", "notes": "ทดสอบ single-person, crossing, เสื้อคล้ายกัน, partial/full occlusion, target ออกจากฉากและกลับเข้าเฟรม; ข้อมูลตัวอย่างปัจจุบันเป็น synthetic", "source": "experiments/identity/README.md · docs/EXECUTION_WORKFLOW.md"},
        {"id": 9, "title": "เปรียบเทียบ baseline การติดตามเป้าหมาย", "phase": "Target tracking & Re-ID", "priority": "กลาง", "status": "รอเริ่ม", "due": "", "notes": "เปรียบเทียบ nearest-person, ByteTrack/BoT-SORT และแนวทาง appearance + motion + range; รายงาน wrong-follow, coverage, ID switch และเวลาหยุด/กลับมาจับเป้าหมาย", "source": "docs/EXECUTION_WORKFLOW.md · experiments/identity/README.md"},
        {"id": 10, "title": "ตรวจ read-only hardware และสถานะ LiDAR", "phase": "Robot integration", "priority": "กลาง", "status": "เสร็จแล้ว", "due": "", "notes": "ตรวจ camera/serial แบบอ่านอย่างเดียวแล้ว; ยังไม่พบ LiDAR ใน USB inventory และยังไม่มี live ROS application graph", "source": "experiments/hardware/2026-09-20_connected_runtime_validation.md"},
        {"id": 13, "title": "ทดสอบ turn-only และ closed-loop follower", "phase": "Robot integration", "priority": "สูง", "status": "ติดเงื่อนไข", "due": "", "notes": "เริ่ม turn-only ก่อน forward motion และต้องผ่าน controlled test 10/10", "source": "docs/EXECUTION_WORKFLOW.md"},
        {"id": 14, "title": "เตรียม conference experiment อย่างน้อย 10 scenarios", "phase": "Experiments & analysis", "priority": "กลาง", "status": "รอเริ่ม", "due": "", "notes": "freeze protocol/config, ทำซ้ำหลายรอบ, เก็บ ground truth และ events, ทำ baseline/ablation; ทุกตัวเลขต้องย้อนถึง raw data ได้", "source": "docs/EXECUTION_WORKFLOW.md"},
        {"id": 15, "title": "เขียน Methodology, Results และข้อจำกัด", "phase": "Thesis writing", "priority": "กลาง", "status": "รอเริ่ม", "due": "", "notes": "เริ่มจากวิธีทดลองและระบบที่ยืนยันได้ แยกผลบนหุ่นจริง ผลจำลอง และข้อเสนอ offline ให้ชัด; ไม่อ้างผลจากข้อมูล synthetic เป็นผลจริง", "source": "docs/EXECUTION_WORKFLOW.md · README.md"},
        {"id": 16, "title": "เก็บ LiDAR ไว้เป็นงานพักจนกว่าจะยืนยันอุปกรณ์", "phase": "Robot integration", "priority": "ต่ำ", "status": "พักไว้", "due": "", "notes": "เอกสารระบุว่ายังไม่พบตัวอุปกรณ์ในการตรวจครั้งล่าสุด ให้นำกลับมาทำเมื่อพบและตรวจ timestamps/ROS graph ได้", "source": "docs/EXECUTION_WORKFLOW.md · experiments/hardware/2026-09-20_connected_runtime_validation.md"},
    ]
    return decorate_quests({"project": {"title": "Following Mobile Robot in Farm Environment", "subtitle": "Thesis workspace · หุ่นยนต์ติดตามคนในสภาพแวดล้อมฟาร์ม", "source_root": source}, "tasks": tasks})


class ThesisTracker:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.data = load_data()
        self.tasks = self.data["tasks"]
        self.game = self.data.setdefault("game_state", {})
        self.game.setdefault("scene", "office")
        self.game.setdefault("player", {"x": 0.5, "y": 0.78})
        self.game.setdefault("test_runs", [])
        self.near_station = None
        self.last_game_key = 0
        self.quest_panel_open = False
        self.walk_step = 0
        # Persist one-time quest metadata migration while retaining existing task edits.
        self.persist()
        self.filtered: list[dict] = []
        self.selected: dict | None = None
        self.filter_var = tk.StringVar(value="Main Quest")
        self.status_var = tk.StringVar(value="")
        self._configure()
        self._build()
        self.refresh()
        self.root.after(180, self.start_game)

    def _configure(self):
        self.root.title("Thesis Desk · ติดตามงานวิทยานิพนธ์")
        self.root.geometry("1280x820")
        self.root.minsize(1020, 690)
        self.root.configure(bg=BG)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=INK,
                        rowheight=40, font=("Leelawadee UI", 10), borderwidth=0)
        style.configure("Treeview.Heading", background="#f7f9f8", foreground=MUTED,
                        font=("Leelawadee UI", 9, "bold"), relief="flat", padding=(8, 10))
        style.map("Treeview", background=[("selected", PALE_GREEN)], foreground=[("selected", INK)])
        style.configure("TCombobox", padding=7, font=("Leelawadee UI", 10))
        style.configure("Vertical.TScrollbar", background=BG, troughcolor=BG, bordercolor=BG, arrowsize=12)

    def _label(self, parent, text, *, size=10, color=INK, bold=False, **kwargs):
        return tk.Label(parent, text=text, bg=kwargs.pop("bg", PANEL), fg=color,
                        font=("Leelawadee UI", size, "bold" if bold else "normal"), **kwargs)

    def _button(self, parent, text, command, *, primary=False):
        bg, fg = (GREEN, "white") if primary else ("#f0f4f1", INK)
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                         activebackground="#155c40" if primary else "#e4ebe7",
                         activeforeground="white" if primary else INK,
                         relief="flat", bd=0, padx=15, pady=9,
                         font=("Leelawadee UI", 10, "bold"), cursor="hand2")

    def _build(self):
        from game_ui import build_game_ui
        build_game_ui(self)
    def set_filter(self, phase: str):
        self.filter_var.set(phase)
        self.refresh()

    def refresh(self):
        visible_tasks = [t for t in self.tasks if not t.get("archived")]
        selected_filter = self.filter_var.get()
        if selected_filter in ("Main Quest", "Side Quest"):
            self.filtered = [t for t in visible_tasks if t.get("quest_type", "Side Quest") == selected_filter]
        elif selected_filter == "ทุกเควส":
            self.filtered = visible_tasks
        else:
            self.filtered = [t for t in visible_tasks if t.get("phase") == selected_filter]
        self.tree.delete(*self.tree.get_children())
        self.filtered.sort(key=lambda t: (0 if t.get("quest_type") == "Main Quest" else 1,
                                          int(t.get("quest_order", 999)), int(t.get("id", 0))))
        for task in self.filtered:
            tags = ("done",) if task.get("status") == "เสร็จแล้ว" else ("blocked",) if task.get("status") == "ติดเงื่อนไข" else ()
            kind = "MAIN" if task.get("quest_type") == "Main Quest" else "SIDE"
            number = int(task.get("quest_no", 0))
            quest_label = f"{kind} {number:02d}" if number else kind
            if task.get("quest_type") == "Main Quest" and self.is_locked(task):
                quest_label += " · LOCK"
            self.tree.insert("", "end", iid=str(task["id"]), text=task.get("title", ""),
                             values=(quest_label, task.get("phase", ""), task.get("status", ""),
                                     task.get("priority", ""), task.get("due") or "—"), tags=tags)
        active = sum(t.get("status") == "กำลังทำ" for t in self.tasks)
        main_quests = sorted((t for t in self.tasks if t.get("quest_type") == "Main Quest"), key=lambda t: int(t.get("quest_order", 999)))
        done_main = sum(t.get("status") == "เสร็จแล้ว" for t in main_quests)
        xp = sum(int(t.get("reward_xp", 0)) for t in self.tasks if t.get("status") == "เสร็จแล้ว") + int(self.game.get("simulation_xp", 0))
        side_quests = [t for t in self.tasks if t.get("quest_type") == "Side Quest"]
        side_done = sum(t.get("status") == "เสร็จแล้ว" for t in side_quests)
        self.metrics["progress"].configure(text=f"{done_main}/{len(main_quests)} ด่าน")
        self.metrics["active"].configure(text=str(active))
        self.metrics["xp"].configure(text=f"{xp} XP")
        self.metrics["side"].configure(text=f"{side_done}/{len(side_quests)} ผ่านแล้ว")
        self.refresh_game_profile()
        self.draw_scene()
        visible = {str(t["id"]) for t in self.filtered}
        if self.selected and str(self.selected["id"]) in visible:
            task = next(t for t in self.tasks if t["id"] == self.selected["id"])
        else:
            task = next((t for t in self.filtered if t.get("status") in ("กำลังทำ", "รอเริ่ม", "ติดเงื่อนไข")),
                        self.filtered[0] if self.filtered else None)
        if task:
            self.selected = task
            self._load_detail(task)
            self.tree.selection_set(str(task["id"]))
            self.tree.see(str(task["id"]))

    def is_locked(self, task):
        if task.get("quest_type") != "Main Quest":
            return False
        previous = [t for t in self.tasks if t.get("quest_type") == "Main Quest"
                    and int(t.get("quest_order", 999)) < int(task.get("quest_order", 999))]
        return any(t.get("status") != "เสร็จแล้ว" for t in previous)

    def start_game(self):
        self.quest_canvas.focus_set()
        self.draw_scene()

    def toggle_quest_panel(self):
        if self.quest_panel_open:
            self.log_panel.pack_forget()
            self.detail_shell.pack_forget()
            self.quest_panel_open = False
        else:
            self.log_panel.pack(side="bottom", fill="x")
            self.detail_shell.pack(side="right", fill="y", padx=(9, 0))
            self.quest_panel_open = True

    def interact_npc(self, npc):
        conversations = {
            "mentor": ("พี่นักวิจัย", "ยินดีต้อนรับสู่แล็บ! คุยกับทีมได้ แล้วไป Test Field เพื่อเริ่มภารกิจจำลองนะ"),
            "engineer": ("วิศวกรหุ่นยนต์", "FARM-01 พร้อมแล้ว เลือก Robot Run, Camera หรือ Motor ที่ Test Field เพื่อเล่นการทดสอบ")
        }
        title, message = conversations[npc]
        self.scene_hint.configure(text=f"{title}: {message}")
        self.quest_canvas.focus_set()

    def switch_scene(self, scene):
        self.game["scene"] = "field" if scene == "field" else "office"
        self.game["player"] = {"x": 0.12, "y": 0.78} if scene == "office" else {"x": 0.10, "y": 0.78}
        self.near_station = None
        self.persist()
        self.draw_scene()
        self.quest_canvas.focus_set()

    def game_key(self, event):
        if isinstance(event.widget, (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox)):
            return
        key = event.keysym.lower()
        char = (event.char or "").lower()
        if key in ("e", "space", "return") or char == "e":
            if self.near_npc:
                self.interact_npc(self.near_npc)
            else:
                self.interact_station()
            return "break"
        if char in ("w", "a", "s", "d"):
            key = char
        if key not in ("w", "a", "s", "d", "up", "down", "left", "right"):
            return
        now = self.root.tk.call("clock", "milliseconds")
        if int(now) - self.last_game_key < 18:
            return "break"
        self.last_game_key = int(now)
        self.walk_step = (self.walk_step + 1) % 2
        dx = (-0.035 if key in ("a", "left") else 0.035 if key in ("d", "right") else 0)
        dy = (-0.045 if key in ("w", "up") else 0.045 if key in ("s", "down") else 0)
        p = self.game.setdefault("player", {"x": .5, "y": .78})
        p["x"] = min(.95, max(.05, float(p.get("x", .5)) + dx))
        p["y"] = min(.91, max(.48, float(p.get("y", .78)) + dy))
        self.draw_scene()
        return "break"

    def game_click(self, event):
        self.quest_canvas.focus_set()
        c=self.quest_canvas
        w,h=max(c.winfo_width(),520),max(c.winfo_height(),360)
        ox,oy,sw,sh=34,32,w-68,h-64
        px,py=ox+float(self.game["player"].get("x",.5))*sw,oy+float(self.game["player"].get("y",.78))*sh
        field=self.game.get("scene")=="field"
        np=[("mentor",ox+sw*.57,oy+sh*.53),("engineer",ox+sw*.82,oy+sh*.78)] if not field else []
        for name,x,y in np:
            if abs(event.x-x)<25 and abs(event.y-y)<30:
                self.near_npc=name; self.near_station=None
                self.render_station_actions(); self.interact_npc(name)
                return "break"
        for name,x,y,label in self._stations():
            sx,sy=ox+x*sw,oy+y*sh
            if abs(event.x-sx)<42 and abs(event.y-sy)<46:
                self.near_station=name; self.near_npc=None
                self.render_station_actions()
                choices=self.station_choices(name)
                if len(choices)==1: self.run_simulation(choices[0][1])
                return "break"
        dx=(event.x-px)/sw; dy=(event.y-py)/sh
        p=self.game["player"]
        p["x"]=min(.95,max(.05,float(p.get("x",.5))+dx*.45))
        p["y"]=min(.91,max(.48,float(p.get("y",.78))+dy*.45))
        self.draw_scene()
        return "break"

    def _stations(self):
        if self.game.get("scene") == "field":
            return [("robot", .25, .68, "Robot Run"), ("camera", .50, .68, "Camera"),
                    ("motor", .75, .68, "Motor Bench")]
        return [("board", .25, .66, "Quest Board"), ("desk", .52, .66, "Research Desk"),
                ("robotbay", .78, .66, "Robot Bay")]

    def draw_scene(self):
        canvas = getattr(self, "quest_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        c = canvas
        w, h = max(c.winfo_width(), 520), max(c.winfo_height(), 360)
        field = self.game.get("scene") == "field"
        c.delete("all")
        # Recessed game window and pixel-frame surround inspired by the reference.
        c.create_rectangle(0, 0, w, h, fill="#172039", outline="")
        c.create_rectangle(5, 5, w-5, h-5, fill="#64728c", outline="#0c1224", width=4)
        c.create_rectangle(12, 12, w-12, h-12, fill="#d5ddec", outline="#8291aa", width=3)
        c.create_rectangle(20, 20, w-20, h-20, fill="#101522", outline="#283248", width=4)
        ox, oy = 34, 32
        sw, sh = w-68, h-64
        if field:
            c.configure(bg="#101522")
            c.create_rectangle(ox, oy, w-ox, h-oy, fill="#86c9dc", outline="#d3c29b", width=4)
            c.create_rectangle(ox, oy+sh*.52, w-ox, h-oy, fill="#83aa5b", outline="")
            c.create_rectangle(ox, oy+sh*.51, w-ox, oy+sh*.56, fill="#68904a", outline="")
            # Crop rows, test lanes, cones, and target silhouettes.
            for y in (h*.63, h*.76, h*.89):
                c.create_rectangle(ox, oy+y, w-ox, oy+y+5, fill="#b49a62", outline="")
            c.create_rectangle(ox+sw*.12, oy+sh*.56, ox+sw*.88, oy+sh*.78, fill="#b99d68", outline="")
            for x in (.16,.34,.66,.84):
                xx=ox+x*sw; yy=oy+sh*.60
                c.create_polygon(xx,yy+18,xx+9,yy,xx+18,yy+18,fill="#e86f42",outline="#8a442e")
                c.create_rectangle(xx+4,yy+12,xx+14,yy+16,fill="#fff0c9",outline="")
            for x in (.43,.56):
                c.create_rectangle(ox+x*sw,oy+sh*.43,ox+x*sw+8,oy+sh*.65,fill="#654f44",outline="")
                c.create_rectangle(ox+x*sw-15,oy+sh*.43,ox+x*sw+23,oy+sh*.46,fill="#4b3436",outline="")
            c.create_text(ox+12, oy+10, anchor="nw", text="TEST FIELD  /  FARM TRACK", fill="#173d35", font=("Leelawadee UI", 13, "bold"))
        else:
            c.configure(bg="#101522")
            c.create_rectangle(ox,oy,w-ox,h-oy,fill="#315552",outline="#cfb38c",width=5)
            c.create_rectangle(ox,oy,w-ox,oy+sh*.56,fill="#34384b",outline="")
            c.create_rectangle(ox,oy+sh*.56,w-ox,h-oy,fill="#54877c",outline="")
            c.create_rectangle(ox,oy+sh*.56,w-ox,h-oy,fill="",outline="#bda77f",width=5)
            # Pixel windows, floorboards, and office furniture.
            for x in range(int(ox+18),w-ox,28): c.create_rectangle(x,oy+sh*.56,x+1,h-oy,fill="#65968a",outline="")
            for y in range(int(oy+sh*.61),h-oy,27): c.create_rectangle(ox,y,w-ox,y+1,fill="#65968a",outline="")
            for x in (.08,.87):
                xx=ox+x*sw
                c.create_rectangle(xx,oy+sh*.04,xx+sw*.10,oy+sh*.32,fill="#60788b",outline="#d1b38a",width=5)
                c.create_line(xx+sw*.05,oy+sh*.04,xx+sw*.05,oy+sh*.32,fill="#d1b38a",width=3)
                c.create_line(xx,oy+sh*.18,xx+sw*.10,oy+sh*.18,fill="#d1b38a",width=3)
            # bookshelf
            c.create_rectangle(ox+sw*.30,oy+sh*.04,ox+sw*.42,oy+sh*.34,fill="#76533b",outline="#503c31",width=3)
            for yy in (.20,.30,.40):
                c.create_rectangle(ox+sw*.31,oy+sh*yy,ox+sw*.41,oy+sh*yy+4,fill="#d8bb79",outline="")
                for j,col in enumerate(("#a34f42","#4e8290","#d0a04d","#56724c")):
                    c.create_rectangle(ox+sw*(.315+j*.022),oy+sh*yy-18,ox+sw*(.33+j*.022),oy+sh*yy,fill=col,outline="")
            # desks/computer and quest board
            # Work islands, meeting table, cabinets, plants, terminals and wall fixtures.
            self._pixel_desk(c,ox+sw*.20,oy+sh*.10,sw*.19,sh*.25,"#a95d3c")
            self._pixel_desk(c,ox+sw*.48,oy+sh*.08,sw*.25,sh*.15,"#6c5748")
            self._pixel_desk(c,ox+sw*.17,oy+sh*.55,sw*.13,sh*.24,"#9b7956")
            self._pixel_desk(c,ox+sw*.39,oy+sh*.65,sw*.24,sh*.12,"#a36b4b")
            self._pixel_desk(c,ox+sw*.73,oy+sh*.57,sw*.13,sh*.23,"#715c4d")
            # cabinets / printers
            for xx,yy,col in ((.10,.25,"#b6c5c3"),(.78,.20,"#a1473e"),(.84,.43,"#65788a"),(.09,.72,"#d6d0bd")):
                x0,y0=ox+sw*xx,oy+sh*yy
                c.create_rectangle(x0,y0,x0+sw*.07,y0+sh*.13,fill=col,outline="#252d3b",width=3)
                c.create_rectangle(x0+4,y0+5,x0+sw*.07-4,y0+sh*.05,fill="#87969b",outline="")
                c.create_line(x0+4,y0+sh*.075,x0+sw*.07-4,y0+sh*.075,fill="#4a5762",width=2)
            # plants and chairs
            for xx,yy in ((.37,.45),(.70,.38),(.29,.86),(.89,.62)):
                x0,y0=ox+sw*xx,oy+sh*yy
                c.create_rectangle(x0-6,y0+6,x0+7,y0+17,fill="#a55b45",outline="#563f37")
                c.create_rectangle(x0-2,y0-9,x0+3,y0+8,fill="#40714f",outline="")
                c.create_rectangle(x0-12,y0-3,x0-2,y0+2,fill="#51875c",outline="")
                c.create_rectangle(x0+3,y0-7,x0+12,y0-2,fill="#51875c",outline="")
            for xx,yy in ((.46,.53),(.65,.58),(.35,.72),(.66,.78)):
                x0,y0=ox+sw*xx,oy+sh*yy
                c.create_rectangle(x0-10,y0-8,x0+10,y0+8,fill="#526779",outline="#283246",width=2)
                c.create_rectangle(x0-6,y0-5,x0+6,y0+5,fill="#77989d",outline="")
            c.create_text(ox+12,oy+10,anchor="nw",text="OFFICE  /  RESEARCH HUB",fill="#fff0c9",font=("Leelawadee UI",13,"bold"))
        for name,x,y,label in self._stations():
            self._draw_station(c, name, ox+x*sw, oy+y*sh, label)
        p=self.game.setdefault("player",{"x":.5,"y":.78})
        px,py=ox+float(p.get("x",.5))*sw,oy+float(p.get("y",.78))*sh
        self._draw_player(c,px,py,self.walk_step)
        # A small animated digital coworker sits beside the player.
        npc_points=[]
        if self.game.get("scene") == "office":
            npc_points=[("mentor",ox+sw*.57,oy+sh*.53,"#e1bb86","#78547c"),
                        ("engineer",ox+sw*.82,oy+sh*.78,"#d7a477","#426a72")]
            for _npc,nx,ny,skin,shirt in npc_points:
                self._draw_npc(c,nx,ny,skin,shirt)
                c.create_oval(nx-13,ny-27,nx+13,ny-23,fill="#f3d77d",outline="#fff0c9")
        self.near_npc=None
        if npc_points:
            npc=min(npc_points,key=lambda n:((n[1]-px)**2+(n[2]-py)**2))
            if ((npc[1]-px)**2+(npc[2]-py)**2)**.5 < min(sw,sh)*.11:
                self.near_npc=npc[0]
        nearest=min(self._stations(),key=lambda s:((ox+s[1]*sw-px)**2+(oy+s[2]*sh-py)**2))
        dist=((ox+nearest[1]*sw-px)**2+(oy+nearest[2]*sh-py)**2)**.5
        self.near_station=nearest[0] if dist < min(w,h)*.22 else None
        if self.near_npc:
            self.near_station=None
        if self.near_station:
            c.create_rectangle(ox+6,h-oy-30,w-ox-6,h-oy-6,fill="#173b31",outline="#f2d27c",width=2)
            target="พี่นักวิจัย" if self.near_npc=="mentor" else "วิศวกรหุ่นยนต์" if self.near_npc=="engineer" else nearest[3]
            c.create_text(ox+14,h-oy-18,anchor="w",text=f"กด E เพื่อคุย/โต้ตอบ: {target}",fill="white",font=("Leelawadee UI",9,"bold"))
        self.scene_title.configure(text="TEST FIELD" if field else "OFFICE")
        self.render_station_actions()

    def _draw_npc(self,c,x,y,skin,shirt):
        c.create_oval(x-9,y+11,x+9,y+15,fill="#283243",outline="")
        c.create_rectangle(x-7,y-8,x+7,y+9,fill=shirt,outline="#2a3440",width=2)
        c.create_rectangle(x-6,y-19,x+6,y-8,fill=skin,outline="#644b3a",width=2)
        c.create_rectangle(x-7,y-21,x+7,y-17,fill="#493b38",outline="")
        c.create_rectangle(x-3,y-14,x-1,y-12,fill="#24303b",outline="")
        c.create_rectangle(x+2,y-14,x+4,y-12,fill="#24303b",outline="")

    def _pixel_desk(self,c,x,y,w,h,color):
        c.create_rectangle(x+5,y+8,x+w+5,y+h+8,fill="#253040",outline="")
        c.create_rectangle(x,y,x+w,y+h,fill=color,outline="#543e3b",width=3)
        c.create_rectangle(x+4,y+4,x+w-4,y+h-4,fill="#bd7952",outline="")
        c.create_rectangle(x+8,y+h*.78,x+w-8,y+h*.88,fill="#704d3f",outline="")
        # monitor, keyboard, paper and desk clutter
        c.create_rectangle(x+w*.38,y-13,x+w*.63,y+5,fill="#313c4d",outline="#182333",width=2)
        c.create_rectangle(x+w*.41,y-10,x+w*.60,y+1,fill="#91c6bf",outline="")
        c.create_rectangle(x+w*.17,y+h*.24,x+w*.33,y+h*.34,fill="#eadbb7",outline="#9e8059")
        c.create_rectangle(x+w*.68,y+h*.55,x+w*.86,y+h*.62,fill="#c8b998",outline="")

    def _draw_station(self,c,name,x,y,label):
        c.create_oval(x-24,y-23,x+24,y+24,fill="#f2d27c",outline="#f9edc8",width=2)
        if name in ("robot","robotbay"):
            c.create_rectangle(x-18,y-15,x+18,y+13,fill="#d8e2d4",outline="#344a49",width=3)
            c.create_rectangle(x-12,y-23,x+12,y-14,fill="#687e72",outline="#344a49",width=2)
            c.create_oval(x-7,y-21,x-2,y-16,fill="#83d5d0",outline="")
            c.create_oval(x+2,y-21,x+7,y-16,fill="#83d5d0",outline="")
            c.create_oval(x-22,y+8,x-7,y+23,fill="#384345",outline="")
            c.create_oval(x+7,y+8,x+22,y+23,fill="#384345",outline="")
        elif name=="camera":
            c.create_rectangle(x-20,y-13,x+16,y+13,fill="#46595a",outline="#223b3a",width=2)
            c.create_oval(x-8,y-9,x+9,y+9,fill="#86cfd2",outline="#1d3837",width=2)
            c.create_rectangle(x-8,y+13,x-4,y+34,fill="#4e5d50",outline="")
            c.create_rectangle(x+5,y+13,x+9,y+34,fill="#4e5d50",outline="")
        elif name=="motor":
            c.create_rectangle(x-19,y-13,x+19,y+13,fill="#bf7654",outline="#633d30",width=3)
            c.create_oval(x-11,y-7,x+11,y+7,fill="#e6c274",outline="#633d30",width=2)
            c.create_line(x,y-27,x,y-14,fill="#493e36",width=4)
        elif name=="board":
            c.create_rectangle(x-24,y-20,x+24,y+18,fill="#9f754a",outline="#503c31",width=3)
            for j,col in enumerate(("#f1d77f","#c76c58","#b1d6b6")):
                c.create_rectangle(x-17+j*13,y-12,x-7+j*13,y+8,fill=col,outline="")
        else:
            c.create_rectangle(x-20,y-12,x+20,y+8,fill="#79583e",outline="#503c31",width=2)
            c.create_rectangle(x-15,y-25,x+15,y-12,fill="#455657",outline="#25393a",width=2)
            c.create_rectangle(x-12,y-22,x+12,y-15,fill="#a6d7be",outline="")
        c.create_text(x,y+31,text=label,fill="#fff2ca",font=("Leelawadee UI",8,"bold"))

    def _draw_player(self,c,x,y,step=0):
        stride=2 if step else -2
        c.create_oval(x-9,y+13,x+9,y+17,fill="#283243",outline="")
        c.create_rectangle(x-6,y-7,x+6,y+10,fill="#315e50",outline="#203e36",width=1)
        c.create_rectangle(x-5,y-17,x+5,y-7,fill="#e4b886",outline="#644b3a",width=1)
        c.create_rectangle(x-6,y-19,x+6,y-16,fill="#4a3930",outline="")
        c.create_rectangle(x-8,y-5,x-6,y+4+stride,fill="#e4b886",outline="")
        c.create_rectangle(x+6,y-5,x+8,y+4-stride,fill="#e4b886",outline="")
        c.create_rectangle(x-5-stride,y+9,x-1-stride,y+14,fill="#293d4b",outline="")
        c.create_rectangle(x+1+stride,y+9,x+5+stride,y+14,fill="#293d4b",outline="")

    def render_station_actions(self):
        if not hasattr(self,"game_actions"): return
        for widget in self.game_actions.winfo_children(): widget.destroy()
        label = "เดิน/คลิกตัวละครหรือสถานีเพื่อคุย/เริ่มกิจกรรม" if not (self.near_station or self.near_npc) else "เลือกกิจกรรม (ผลจำลองในเกม)"
        tk.Label(self.game_actions,text=label,bg="#223b3a",fg="#f4e8b8",font=("Leelawadee UI",9,"bold")).pack(side="left",padx=8,pady=5)
        if self.near_npc:
            npc_title="คุยกับพี่นักวิจัย" if self.near_npc=="mentor" else "คุยกับวิศวกรหุ่นยนต์"
            tk.Button(self.game_actions,text=npc_title,command=lambda:self.interact_npc(self.near_npc),bg="#a9c4e8",fg="#263b36",relief="flat",bd=0,padx=10,pady=6,font=("Leelawadee UI",8,"bold"),cursor="hand2").pack(side="left",padx=4,pady=3)
        elif self.near_station:
            for title,action in self.station_choices(self.near_station):
                tk.Button(self.game_actions,text=title,command=lambda a=action:self.run_simulation(a),bg="#f2d27c",fg="#263b36",relief="flat",bd=0,padx=10,pady=6,font=("Leelawadee UI",8,"bold"),cursor="hand2").pack(side="left",padx=4,pady=3)
        tk.Label(self.game_actions,text=f"รอบจำลอง {len(self.game.get('test_runs',[]))}",bg="#223b3a",fg="#b6d0c6",font=("Leelawadee UI",8)).pack(side="right",padx=8)

    def station_choices(self,station):
        if station=="camera": return [("เริ่มทดสอบกล้อง", "camera")]
        if station=="motor": return [("จำลองทดสอบมอเตอร์", "motor")]
        if station=="robot": return [("จำลองหุ่นวิ่งตามเส้น", "run"),("จำลองหยุด/กลับมาจับเป้า", "tracking")]
        if station=="board": return [("ดูเควสหลัก", "quests"),("ดูเควสเสริม", "sidequests")]
        if station=="desk": return [("เปิดเควสที่กำลังทำ", "active"),("ดูผลจำลองล่าสุด", "results")]
        return [("ดูสถานะหุ่น", "robot_status"),("ไป Test Field", "field")]

    def interact_station(self):
        if not self.near_station:
            self.scene_hint.configure(text="ยังไม่มีสถานีใกล้พอ · ใช้ WASD ขยับเข้าใกล้")
            return
        choices=self.station_choices(self.near_station)
        if len(choices)==1: self.run_simulation(choices[0][1])
        else: self.scene_hint.configure(text="เลือกกิจกรรมจากปุ่มด้านล่างฉาก")

    def run_simulation(self,action):
        if action=="field": self.switch_scene("field"); return
        if action in ("quests","sidequests","active"):
            if not self.quest_panel_open: self.toggle_quest_panel()
            self.set_filter("Main Quest" if action=="quests" else "Side Quest" if action=="sidequests" else self.tasks[0].get("phase")); return
        if action=="robot_status":
            self.details_tabs.select(1); self.scene_hint.configure(text="FARM-01 · สถานะโปรไฟล์ในเกม"); return
        if action=="results":
            runs=self.game.get("test_runs",[])
            self.scene_hint.configure(text=(runs[-1].get("summary","ยังไม่มีรอบจำลอง") if runs else "ยังไม่มีรอบจำลอง")); return
        summaries={"camera":"Camera simulation: target frame 1280×720 · detection stable · 30 FPS (ตัวอย่างจำลอง)",
                   "motor":"Motor simulation: left/right RPM response matched · command output to hardware = none",
                   "run":"Robot run simulation: completed 8 m virtual lane · 2 turns · 0 collisions",
                   "tracking":"Tracking simulation: target lost then reacquired · virtual stop event recorded"}
        summary=summaries[action]
        run={"type":action,"summary":summary,"scene":self.game.get("scene"),"date":str(date.today()),"source":"SIMULATION ONLY"}
        runs=self.game.setdefault("test_runs",[]); runs.append(run); self.game["test_runs"]=runs[-100:]
        self.game["simulation_xp"]=int(self.game.get("simulation_xp",0))+10
        self.persist(); self.scene_hint.configure(text=f"✦ +10 XP  ·  {summary}"); self.render_station_actions(); self.refresh_test_runs(); self.refresh_game_profile()

    def refresh_test_runs(self):
        if hasattr(self,"test_runs_label"):
            runs=self.game.get("test_runs",[])
            self.test_runs_label.configure(text="\n".join(f"• {r.get('summary','')}" for r in reversed(runs[-4:])) or "ยังไม่มีผลจำลอง")

    def draw_quest_map(self):
        canvas = getattr(self, "quest_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        canvas.delete("all")
        w, h = max(canvas.winfo_width(), 520), max(canvas.winfo_height(), 360)
        c = canvas
        # Sky, block clouds and a square sun.
        c.create_rectangle(0, 0, w, h, fill="#77c8d1", outline="")
        c.create_rectangle(w - 75, 26, w - 45, 56, fill="#ffe28a", outline="")
        c.create_rectangle(w - 83, 34, w - 37, 48, fill="#ffe28a", outline="")
        for x, y in ((45, 42), (w * .40, 32), (w * .69, 73)):
            c.create_rectangle(x, y + 8, x + 54, y + 21, fill="#e4f1e1", outline="")
            c.create_rectangle(x + 10, y, x + 42, y + 28, fill="#e4f1e1", outline="")
            c.create_rectangle(x + 21, y - 5, x + 34, y + 30, fill="#e4f1e1", outline="")
        # Layered, stepped farm hills.
        ridge_y = h * .34
        for offset, color in ((0, "#5b9d83"), (27, "#478368")):
            points = [0, ridge_y + 22 + offset, w * .12, ridge_y + 22 + offset,
                      w * .12, ridge_y + 5 + offset, w * .23, ridge_y + 5 + offset,
                      w * .23, ridge_y - 8 + offset, w * .39, ridge_y - 8 + offset,
                      w * .39, ridge_y + 13 + offset, w * .57, ridge_y + 13 + offset,
                      w * .57, ridge_y - 2 + offset, w * .73, ridge_y - 2 + offset,
                      w * .73, ridge_y + 18 + offset, w, ridge_y + 18 + offset, w, h, 0, h]
            c.create_polygon(points, fill=color, outline="")
        c.create_rectangle(0, h * .46, w, h, fill="#79ad55", outline="")
        # Farm plots and small pixel trees along the lower edge.
        for x in range(18, w, 46):
            c.create_rectangle(x, h * .88, x + 27, h * .90, fill="#8dbb63", outline="")
        for x in (26, w - 38, w * .18, w * .82):
            y = h * .84
            c.create_rectangle(x + 9, y + 22, x + 17, y + 45, fill="#775439", outline="")
            c.create_rectangle(x + 2, y + 10, x + 24, y + 27, fill="#276b4c", outline="")
            c.create_rectangle(x + 7, y, x + 19, y + 34, fill="#398657", outline="")
            c.create_rectangle(x + 10, y + 4, x + 15, y + 10, fill="#68a85d", outline="")

        main = sorted((t for t in self.tasks if t.get("quest_type") == "Main Quest" and not t.get("archived")),
                      key=lambda t: int(t.get("quest_order", 999)))
        n = len(main)
        if n:
            columns = min(5, n)
            rows = (n + columns - 1) // columns
            margin = 43
            xs = [margin + i * (w - 2 * margin) / max(columns - 1, 1) for i in range(columns)]
            ys = [h * (.38 + .31 * row / max(rows - 1, 1)) for row in range(rows)]
            coords = []
            for index in range(n):
                row, pos = divmod(index, columns)
                col = pos if row % 2 == 0 else columns - 1 - pos
                coords.append((xs[col], ys[row]))
            # The trail is drawn before the quest markers.
            for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
                c.create_line(x1, y1, x2, y2, fill="#774d35", width=20, capstyle=tk.PROJECTING)
                c.create_line(x1, y1, x2, y2, fill="#d8a45c", width=13, capstyle=tk.PROJECTING)
                c.create_line(x1, y1, x2, y2, fill="#f0cf84", width=2, dash=(3, 7))
            short = ["ORIENTATION", "TARGET LOST", "IDENTITY DATA", "BASELINES",
                     "10 SCENARIOS", "ANALYSIS", "THESIS"]
            selected_id = self.selected.get("id") if self.selected else None
            for index, (task, (x, y)) in enumerate(zip(main, coords)):
                locked = self.is_locked(task)
                done = task.get("status") == "เสร็จแล้ว"
                active = task.get("status") == "กำลังทำ"
                fill = "#4e9e72" if done else "#df9a36" if active else "#627774" if locked else "#90a445"
                edge = "#fff3b2" if task.get("id") == selected_id or active else "#f3e4ac"
                # Pixel badge: shadow, border plate, colored center and status glyph.
                c.create_rectangle(x - 19 + 3, y - 19 + 4, x + 19 + 3, y + 19 + 4, fill="#24433f", outline="")
                c.create_rectangle(x - 20, y - 20, x + 20, y + 20, fill=edge, outline="#3d4938", width=2,
                                   tags=(f"quest_{task['id']}",))
                c.create_rectangle(x - 15, y - 15, x + 15, y + 15, fill=fill, outline="",
                                   tags=(f"quest_{task['id']}",))
                if done:
                    c.create_rectangle(x - 8, y + 1, x - 3, y + 6, fill="#fff4c7", outline="", tags=(f"quest_{task['id']}",))
                    c.create_rectangle(x - 3, y + 5, x + 9, y - 7, fill="#fff4c7", outline="", tags=(f"quest_{task['id']}",))
                elif locked:
                    c.create_rectangle(x - 7, y - 1, x + 7, y + 9, fill="#d1d7c4", outline="", tags=(f"quest_{task['id']}",))
                    c.create_rectangle(x - 4, y - 8, x + 4, y + 1, fill="", outline="#d1d7c4", width=2,
                                       tags=(f"quest_{task['id']}",))
                else:
                    c.create_rectangle(x - 2, y - 10, x + 3, y + 10, fill="#fff2be", outline="", tags=(f"quest_{task['id']}",))
                    c.create_rectangle(x - 10, y - 2, x + 10, y + 3, fill="#fff2be", outline="", tags=(f"quest_{task['id']}",))
                label = short[index] if index < len(short) else f"QUEST {index + 1:02d}"
                row = index // columns
                label_y = y - 31 if row % 2 == 0 else y + 31
                c.create_text(x, label_y, text=label, fill="#183b2e", font=("Consolas", 8, "bold"),
                              tags=(f"quest_{task['id']}",))
                c.create_text(x, y + 1, text=f"{int(task.get('quest_no', index + 1)):02d}",
                              fill="#fffdf0" if not done else "#16392d", font=("Consolas", 8, "bold"),
                              tags=(f"quest_{task['id']}",))
                c.tag_bind(f"quest_{task['id']}", "<Button-1>", lambda _e, tid=task["id"]: self.select_quest(tid))
                c.tag_bind(f"quest_{task['id']}", "<Enter>", lambda _e: c.configure(cursor="hand2"))
                c.tag_bind(f"quest_{task['id']}", "<Leave>", lambda _e: c.configure(cursor=""))
        # Side quests live in a separate optional guild board and never block the main route.
        side = [t for t in self.tasks if t.get("quest_type") == "Side Quest"]
        banner_y = h - 25
        c.create_rectangle(8, banner_y - 12, w - 8, h - 4, fill="#24483e", outline="#ddc987")
        c.create_rectangle(17, banner_y - 5, 27, banner_y + 5, fill="#e8b94d", outline="")
        c.create_text(36, banner_y, anchor="w", text=f"SIDE QUEST GUILD   ·   {len(side):02d} optional quests   ·   ไม่ล็อกเส้นทางหลัก",
                      fill="#fff0bf", font=("Consolas", 8, "bold"))

    def select_quest(self, task_id):
        task = next((t for t in self.tasks if t.get("id") == task_id), None)
        if not task:
            return
        self.filter_var.set("Main Quest")
        self.refresh()
        self.selected = task
        if self.tree.exists(str(task_id)):
            self.tree.selection_set(str(task_id))
            self.tree.see(str(task_id))
        self._load_detail(task)
        self.draw_scene()

    def on_select(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        task = next((t for t in self.tasks if str(t["id"]) == selection[0]), None)
        if task:
            self._load_detail(task)

    def _load_detail(self, task):
        self.selected = task
        kind = task.get("quest_type", "Side Quest")
        number = int(task.get("quest_no", 0))
        kind_label = f"{kind} {number:02d}" if number else kind
        objective = task.get("quest_goal", task.get("notes", ""))
        dependency = next((t for t in self.tasks if t.get("id") == task.get("depends_on")), None)
        if kind == "Main Quest" and dependency and dependency.get("status") != "เสร็จแล้ว":
            unlock = f"สถานะ: LOCKED · รอ Main Quest {dependency.get('quest_no', 0):02d}"
        elif kind == "Main Quest":
            unlock = "สถานะ: ปลดล็อกแล้ว · ทำเสร็จแล้วรับ XP"
        else:
            unlock = "เควสเสริม · ทำได้อิสระ ไม่ขวางเส้นเรื่องหลัก"
        self.quest_info.configure(text=f"{kind_label}   ·   +{task.get('reward_xp', 0)} XP\nเป้าหมาย: {objective}\n{unlock}")
        self.title_entry.delete(0, "end"); self.title_entry.insert(0, task.get("title", ""))
        self.phase_box.set(task.get("phase", PHASES[0]))
        self.status_box.set(task.get("status", STATUSES[0]))
        self.priority_box.set(task.get("priority", "กลาง"))
        self.due_entry.delete(0, "end"); self.due_entry.insert(0, task.get("due", ""))
        self.notes.delete("1.0", "end"); self.notes.insert("1.0", task.get("notes", ""))
        self.source_label.configure(text="อ้างอิงหลักฐาน: " + task.get("source", "—"))
        self.status_var.set("")

    def save_selected(self):
        if not self.selected:
            self.status_var.set("เลือกงานก่อนบันทึก")
            return
        due = self.due_entry.get().strip()
        if due:
            try:
                date.fromisoformat(due)
            except ValueError:
                messagebox.showerror("รูปแบบวันที่ไม่ถูกต้อง", "กรุณาใส่วันที่เป็น YYYY-MM-DD เช่น 2026-11-15")
                return
        self.selected.update({"title": self.title_entry.get().strip() or "งานใหม่",
                              "phase": self.phase_box.get(), "status": self.status_box.get(),
                              "priority": self.priority_box.get(), "due": due,
                              "notes": self.notes.get("1.0", "end-1c").strip()})
        self.persist(); self.refresh(); self.status_var.set("บันทึกแล้ว ✓")

    def complete_selected(self):
        if not self.selected:
            self.status_var.set("เลือกงานก่อนทำเครื่องหมายเสร็จ")
            return
        self.status_box.set("เสร็จแล้ว")
        self.save_selected()

    def unlocked_equipment(self):
        completed = {int(t["id"]) for t in self.tasks if t.get("status") == "เสร็จแล้ว"}
        return [item for item in EQUIPMENT if not item.get("locked")
                and all(int(required_id) in completed for required_id in item.get("requires", []))]

    def equip_item(self, slot):
        box = self.equipment_boxes.get(slot)
        if box is None:
            return
        chosen = box.get()
        available = {item["name"] for item in self.unlocked_equipment() if item["slot"] == slot}
        if chosen and chosen not in available:
            return
        self.data.setdefault("game_state", {}).setdefault("equipped", {})[slot] = chosen
        self.persist()
        self.draw_robot_sprite()
        self.profile_status.set(f"ติดตั้ง {chosen or 'ช่องว่าง'} ในช่อง {slot} แล้ว")

    def save_game_profile(self):
        state = self.data.setdefault("game_state", {})
        state["character_name"] = self.character_name_entry.get().strip() or "นักวิจัยฝึกหัด"
        state["robot_name"] = self.robot_name_entry.get().strip() or "FARM-01"
        self.persist()
        self.draw_character_sprite()
        self.draw_robot_sprite()
        self.profile_status.set("เซฟโปรไฟล์แล้ว ✓")

    def draw_xp_bar(self, width=None):
        if not hasattr(self, "profile_xp_canvas"):
            return
        canvas = self.profile_xp_canvas
        width = width or max(canvas.winfo_width(), 160)
        xp = sum(int(t.get("reward_xp", 0)) for t in self.tasks if t.get("status") == "เสร็จแล้ว") + int(self.game.get("simulation_xp", 0))
        canvas.delete("all")
        canvas.create_rectangle(0, 0, width, 8, fill="#3c4c52", outline="")
        canvas.create_rectangle(0, 0, width * (xp % 100) / 100, 8, fill="#f2c65d", outline="")

    def draw_character_sprite(self, _event=None):
        canvas = getattr(self, "character_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        canvas.delete("all")
        w, h = max(canvas.winfo_width(), 300), max(canvas.winfo_height(), 66)
        # Pixel field researcher: hair, face, lab coat, notebook and rank stars.
        canvas.create_rectangle(0, 0, w, h, fill="#263b46", outline="")
        for x, y in ((w - 55, 16), (w - 31, 38), (w - 83, 48), (w - 23, 14)):
            canvas.create_rectangle(x, y, x + 3, y + 3, fill="#eacb74", outline="")
        x, y = 43, max(8, h // 2 - 25)
        canvas.create_rectangle(x + 9, y, x + 33, y + 8, fill="#263129", outline="")
        canvas.create_rectangle(x + 5, y + 7, x + 37, y + 20, fill="#7e523e", outline="")
        canvas.create_rectangle(x + 10, y + 9, x + 32, y + 25, fill="#edbd8a", outline="")
        canvas.create_rectangle(x + 13, y + 15, x + 16, y + 18, fill="#283c44", outline="")
        canvas.create_rectangle(x + 27, y + 15, x + 30, y + 18, fill="#283c44", outline="")
        canvas.create_rectangle(x + 4, y + 25, x + 38, y + 45, fill="#e9eee0", outline="")
        canvas.create_rectangle(x + 17, y + 25, x + 25, y + 43, fill="#2d8b69", outline="")
        canvas.create_rectangle(x - 3, y + 30, x + 5, y + 40, fill="#edbd8a", outline="")
        canvas.create_rectangle(x + 37, y + 30, x + 45, y + 40, fill="#edbd8a", outline="")
        canvas.create_rectangle(x + 42, y + 31, x + 56, y + 43, fill="#d9b45c", outline="")
        canvas.create_text(117, h // 2 - 7, anchor="w", text=self.data.get("game_state", {}).get("character_name", "นักวิจัยฝึกหัด"),
                           fill="#fff0bf", font=("Leelawadee UI", 10, "bold"))
        canvas.create_text(117, h // 2 + 12, anchor="w", text="FIELD RESEARCHER  ·  QUEST HERO",
                           fill="#9dc5b4", font=("Consolas", 7, "bold"))

    def draw_robot_sprite(self, _event=None):
        canvas = getattr(self, "robot_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        canvas.delete("all")
        w, h = max(canvas.winfo_width(), 300), max(canvas.winfo_height(), 68)
        canvas.create_rectangle(0, 0, w, h, fill="#263b46", outline="")
        state = self.data.get("game_state", {})
        equipped = state.get("equipped", {})
        x, y = w // 2, h // 2 + 3
        # Pixel rover companion. Green optics appear only when the matching gear is equipped.
        canvas.create_rectangle(x - 33, y - 18, x + 33, y + 14, fill="#bfc8b7", outline="#edf0dd", width=2)
        canvas.create_rectangle(x - 23, y - 26, x + 23, y - 18, fill="#748a86", outline="")
        canvas.create_rectangle(x - 18, y - 7, x + 18, y + 6, fill="#314c50", outline="")
        lens = "#79e0ab" if equipped.get("Vision AI") else "#627774"
        canvas.create_rectangle(x - 12, y - 4, x - 4, y + 3, fill=lens, outline="")
        canvas.create_rectangle(x + 4, y - 4, x + 12, y + 3, fill=lens, outline="")
        canvas.create_rectangle(x - 28, y + 14, x - 15, y + 25, fill="#293538", outline="#89968b")
        canvas.create_rectangle(x + 15, y + 14, x + 28, y + 25, fill="#293538", outline="#89968b")
        if equipped.get("Camera"):
            canvas.create_rectangle(x - 5, y - 33, x + 5, y - 26, fill="#eacb74", outline="")
            canvas.create_rectangle(x - 2, y - 31, x + 3, y - 28, fill="#263b46", outline="")
        canvas.create_text(9, 10, anchor="nw", text=state.get("robot_name", "FARM-01"),
                           fill="#fff0bf", font=("Consolas", 8, "bold"))
        slots = sum(bool(equipped.get(slot)) for slot in ROBOT_SLOTS)
        canvas.create_text(w - 9, 10, anchor="ne", text=f"GEAR {slots}/6",
                           fill="#9dc5b4", font=("Consolas", 7, "bold"))

    def refresh_game_profile(self):
        state = self.data.setdefault("game_state", {})
        xp = sum(int(t.get("reward_xp", 0)) for t in self.tasks if t.get("status") == "เสร็จแล้ว") + int(state.get("simulation_xp", 0))
        level = xp // 100 + 1
        xp_in_level = xp % 100
        titles = {1: "Junior Researcher", 2: "Field Apprentice", 3: "Robotics Engineer",
                  4: "Robotics Scholar", 5: "Principal Investigator"}
        title = titles.get(level, "Legendary PI")
        if hasattr(self, "profile_level"):
            self.profile_level.configure(text=f"LV. {level}   ·   {title}")
            self.profile_xp_label.configure(text=f"{xp_in_level} / 100 XP  ·  {xp} XP รวม")
            self.draw_xp_bar()
            self.character_name_entry.delete(0, "end")
            self.character_name_entry.insert(0, state.get("character_name", "นักวิจัยฝึกหัด"))
            self.robot_name_entry.delete(0, "end")
            self.robot_name_entry.insert(0, state.get("robot_name", "FARM-01"))
            equipped = state.setdefault("equipped", {})
            unlocked = self.unlocked_equipment()
            self.equipment_boxes = getattr(self, "equipment_boxes", {})
            for slot, box in self.equipment_boxes.items():
                values = [""] + [item["name"] for item in unlocked if item["slot"] == slot]
                box.configure(values=values)
                selected = equipped.get(slot, "")
                if selected not in values:
                    selected = ""
                    equipped[slot] = ""
                box.set(selected)
            locked = [item for item in EQUIPMENT if item.get("locked") or item not in unlocked]
            if hasattr(self, "locked_gear_label"):
                self.locked_gear_label.configure(text="LOCKED GEAR\n" + "\n".join(
                    f"▣ {item['slot']}: {item['kind']}" for item in locked))
            self.draw_character_sprite()
            self.draw_robot_sprite()

    def persist(self):
        DATA_FILE.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def add_task(self):
        win = tk.Toplevel(self.root); win.title("เพิ่มเควสใหม่"); win.configure(bg=PANEL)
        win.geometry("450x550"); win.resizable(False, False); win.transient(self.root); win.grab_set()
        self._label(win, "เพิ่มเควสใน thesis", size=16, bold=True, bg=PANEL).pack(anchor="w", padx=22, pady=(20, 3))
        self._label(win, "ข้อมูลจะถูกบันทึกไว้ในเครื่องนี้", size=9, color=MUTED, bg=PANEL).pack(anchor="w", padx=22, pady=(0, 13))
        form = tk.Frame(win, bg=PANEL); form.pack(fill="both", expand=True, padx=22)
        def field(label, widget):
            self._label(form, label, size=9, color=MUTED, bg=PANEL).pack(anchor="w", pady=(9, 4))
            widget.pack(fill="x")
        title = tk.Entry(form, bg="#f7f9f8", fg=INK, relief="flat", font=("Leelawadee UI", 10), insertbackground=GREEN)
        field("ชื่องาน", title)
        phase = ttk.Combobox(form, values=PHASES, state="readonly"); phase.set(PHASES[0]); field("หมวดงาน", phase)
        quest_kind = ttk.Combobox(form, values=["Side Quest", "Main Quest"], state="readonly")
        quest_kind.set("Side Quest"); field("เส้นทางเควส", quest_kind)
        row = tk.Frame(form, bg=PANEL); row.pack(fill="x", pady=(9, 0))
        pwrap = tk.Frame(row, bg=PANEL); pwrap.pack(side="left", fill="x", expand=True, padx=(0, 6))
        swrap = tk.Frame(row, bg=PANEL); swrap.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self._label(pwrap, "ความสำคัญ", size=9, color=MUTED, bg=PANEL).pack(anchor="w", pady=(0, 4))
        priority = ttk.Combobox(pwrap, values=PRIORITIES, state="readonly"); priority.set("กลาง"); priority.pack(fill="x")
        self._label(swrap, "สถานะ", size=9, color=MUTED, bg=PANEL).pack(anchor="w", pady=(0, 4))
        status = ttk.Combobox(swrap, values=STATUSES, state="readonly"); status.set("รอเริ่ม"); status.pack(fill="x")
        due = tk.Entry(form, bg="#f7f9f8", fg=INK, relief="flat", font=("Leelawadee UI", 10), insertbackground=GREEN)
        field("กำหนดส่ง (YYYY-MM-DD, เว้นว่างได้)", due)
        note = tk.Text(form, height=4, wrap="word", bg="#f7f9f8", fg=INK, relief="flat", font=("Leelawadee UI", 9), padx=8, pady=7)
        field("รายละเอียด / ขั้นตอนถัดไป", note)
        buttons = tk.Frame(win, bg=PANEL); buttons.pack(fill="x", padx=22, pady=17)
        def create():
            due_text = due.get().strip()
            if due_text:
                try: date.fromisoformat(due_text)
                except ValueError:
                    messagebox.showerror("รูปแบบวันที่ไม่ถูกต้อง", "ใช้รูปแบบ YYYY-MM-DD", parent=win); return
            task_id = max((int(t.get("id", 0)) for t in self.tasks), default=0) + 1
            kind = quest_kind.get()
            same_kind = [t for t in self.tasks if t.get("quest_type") == kind]
            number = max((int(t.get("quest_no", 0)) for t in same_kind), default=0) + 1
            order = max((int(t.get("quest_order", 0)) for t in same_kind), default=0) + 1
            dependency = max(same_kind, key=lambda t: int(t.get("quest_order", 0))).get("id") if kind == "Main Quest" and same_kind else None
            self.tasks.append({"id": task_id, "title": title.get().strip() or "เควสใหม่", "phase": phase.get(),
                               "priority": priority.get(), "status": status.get(), "due": due_text,
                               "notes": note.get("1.0", "end-1c").strip(), "source": "เพิ่มโดยผู้ใช้",
                               "quest_type": kind, "quest_no": number, "quest_order": order,
                               "reward_xp": 100 if kind == "Main Quest" else 30,
                               "quest_goal": "เป้าหมายของเควสใหม่", "depends_on": dependency})
            self.persist(); self.filter_var.set(kind); self.refresh()
            self.tree.selection_set(str(task_id)); self.tree.see(str(task_id)); self.on_select()
            win.destroy()
        self._button(buttons, "ยกเลิก", win.destroy).pack(side="right", padx=(7, 0))
        self._button(buttons, "สร้างงาน", create, primary=True).pack(side="right")


def main():
    root = tk.Tk()
    ThesisTracker(root)
    root.mainloop()


if __name__ == "__main__":
    main()
