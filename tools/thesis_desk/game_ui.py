"""Pixel-art quest map widgets for Thesis Desk (Tkinter Canvas only)."""

import tkinter as tk
from tkinter import ttk


BG = "#f3f6f4"
PANEL = "#fffdf4"
INK = "#1b2b25"
MUTED = "#718078"
GREEN = "#1e7655"
AMBER = "#a96313"
LINE = "#e7ddbd"
RED = "#aa4b46"
PHASES = ["Orientation & perception", "Target tracking & Re-ID", "Robot integration",
          "Experiments & analysis", "Thesis writing"]
STATUSES = ["รอเริ่ม", "กำลังทำ", "เสร็จแล้ว", "ติดเงื่อนไข", "พักไว้"]
PRIORITIES = ["สูง", "กลาง", "ต่ำ"]


def build_game_ui(app):
    root = app.root
    root.title("Thesis Quest · Farm Robot Adventure")
    root.geometry("1480x940")
    root.minsize(1200, 780)
    root.configure(bg=BG)

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Treeview", background="#fffdf8", fieldbackground="#fffdf8", foreground=INK,
                    rowheight=27, font=("Leelawadee UI", 9), borderwidth=0)
    style.configure("Treeview.Heading", background="#f2ecd9", foreground="#655c47",
                    font=("Leelawadee UI", 8, "bold"), relief="flat", padding=(6, 4))
    style.map("Treeview", background=[("selected", "#e5e9ae")], foreground=[("selected", INK)])
    style.configure("TCombobox", padding=5, font=("Leelawadee UI", 9))
    style.configure("Vertical.TScrollbar", background=BG, troughcolor=BG, bordercolor=BG, arrowsize=11)

    shell = tk.Frame(root, bg=BG)
    shell.pack(fill="both", expand=True)
    body = tk.Frame(shell, bg=BG)
    body.pack(fill="both", expand=True, padx=18, pady=12)
    head = tk.Frame(body, bg=BG)
    head.pack(fill="x", pady=(0, 9))
    hleft = tk.Frame(head, bg=BG); hleft.pack(side="left", fill="x", expand=True)
    app._label(hleft, "FARM ROBOT ADVENTURE   /   PLAYER HUB", size=9, color=GREEN, bold=True, bg=BG).pack(anchor="w")
    app._label(hleft, "เดินสำรวจ · คุยกับทีม · ทดลองระบบหุ่นยนต์", size=20, bold=True, bg=BG).pack(anchor="w", pady=(2, 0))
    app._button(head, "Office", lambda: app.switch_scene("office")).pack(side="right", padx=(6, 0))
    app._button(head, "Test Field", lambda: app.switch_scene("field")).pack(side="right", padx=(6, 0))
    app._button(head, "QUEST MENU", app.toggle_quest_panel).pack(side="right", anchor="center", padx=(12, 0))

    cards = tk.Frame(body, bg=BG); cards.pack(fill="x", pady=(0, 7))
    app.metrics = {}
    for key, title in [("progress", "CHAPTERS"), ("active", "ACTIVE QUEST"), ("xp", "PLAYER XP"), ("side", "SIDE QUESTS")]:
        card = tk.Frame(cards, bg="#fffdf4", highlightbackground=LINE, highlightthickness=1)
        card.pack(side="left", fill="x", expand=True, padx=(0, 7))
        app._label(card, title, size=8, color=MUTED, bg="#fffdf4").pack(anchor="w", padx=11, pady=(4, 0))
        value = app._label(card, "—", size=12, color=INK, bold=True, bg="#fffdf4")
        value.pack(anchor="w", padx=11, pady=(0, 4))
        app.metrics[key] = value

    game_row = tk.Frame(body, bg=BG)
    game_row.pack(fill="both", expand=True, pady=(0, 8))
    map_panel = tk.Frame(game_row, bg="#223b3a", highlightbackground="#172c2b", highlightthickness=2)
    map_panel.pack(side="left", fill="both", expand=True, padx=(0, 0))
    map_head = tk.Frame(map_panel, bg="#223b3a"); map_head.pack(fill="x", padx=12, pady=(8, 4))
    app.scene_title = app._label(map_head, "OFFICE", size=9, color="#f4e8b8", bold=True, bg="#223b3a")
    app.scene_title.pack(side="left")
    app.scene_hint = app._label(map_head, "WASD เดิน · E โต้ตอบ · เลือกสถานีเพื่อเริ่มกิจกรรม", size=8, color="#b6d0c6", bg="#223b3a")
    app.scene_hint.pack(side="right")
    app.game_title = app._label(map_panel, "THESIS QUEST", size=20, color="#fff8df", bold=True, bg="#223b3a")
    app.game_title.pack(pady=(0, 4))
    app.quest_canvas = tk.Canvas(map_panel, bg="#80cbd0", highlightthickness=0, cursor="crosshair", takefocus=True)
    app.quest_canvas.pack(fill="both", expand=True, padx=22, pady=(0, 6))
    app.quest_canvas.bind("<Configure>", lambda _e: app.draw_scene())
    app.quest_canvas.bind("<Button-1>", app.game_click)
    app.quest_canvas.bind("<KeyPress>", app.game_key)
    root.bind_all("<KeyPress>", app.game_key, add="+")
    app.game_actions = tk.Frame(map_panel, bg="#223b3a")
    app.game_actions.pack(fill="x", padx=7, pady=(0, 7))
    app.character_select = tk.Frame(map_panel, bg="#182344")
    app.character_select.pack(fill="x", padx=7, pady=(0, 7))
    for label, color in [("PLAYER", "#274d79"), ("FARM-01", "#3d5b4d"), ("QUEST", "#6a4b72")]:
        tk.Button(app.character_select, text=f"  ◆  {label}", command=app.quest_canvas.focus_set,
                  bg="#263252", fg="#fff8df", activebackground=color, activeforeground="white",
                  relief="flat", bd=0, padx=12, pady=8, font=("Consolas", 9, "bold"), cursor="hand2").pack(side="left", padx=5, pady=5)
    app._label(app.character_select, "คลิกฉาก · WASD เดิน · E เลือกกิจกรรม", size=8,
               color="#d9deeb", bg="#182344").pack(side="right", padx=10)

    detail_shell = tk.Frame(game_row, bg="#fffdf4", width=350, highlightbackground=LINE, highlightthickness=1)
    app.detail_shell = detail_shell
    detail_shell.pack_forget()
    detail_shell.pack_propagate(False)
    tabs = ttk.Notebook(detail_shell)
    tabs.pack(fill="both", expand=True, padx=4, pady=4)
    detail = tk.Frame(tabs, bg="#fffdf4")
    profile_page = tk.Frame(tabs, bg="#fffdf4")
    tabs.add(detail, text="QUEST")
    tabs.add(profile_page, text="HERO / ROBOT")
    app.details_tabs = tabs
    app._label(detail, "QUEST JOURNAL", size=9, color=AMBER, bold=True, bg="#fffdf4").pack(anchor="w", padx=13, pady=(9, 1))
    app.quest_info = app._label(detail, "เลือกเควสบนแผนที่เพื่อดูรายละเอียด", size=8, color=GREEN,
                                 bg="#e8f3ed", justify="left", anchor="w", wraplength=285, padx=8, pady=7)
    app.quest_info.pack(fill="x", padx=10, pady=(6, 7))
    app.title_entry = tk.Entry(detail, bg="white", fg=INK, relief="flat", font=("Leelawadee UI", 10, "bold"), insertbackground=GREEN)
    app.title_entry.pack(fill="x", padx=10, ipady=6)
    app._label(detail, "หมวดงาน", size=8, color=MUTED, bg="#fffdf4").pack(anchor="w", padx=11, pady=(6, 2))
    app.phase_box = ttk.Combobox(detail, values=PHASES, state="readonly"); app.phase_box.pack(fill="x", padx=10)
    fields = tk.Frame(detail, bg="#fffdf4"); fields.pack(fill="x", padx=10, pady=(6, 0))
    f1 = tk.Frame(fields, bg="#fffdf4"); f1.pack(side="left", fill="x", expand=True, padx=(0, 4))
    f2 = tk.Frame(fields, bg="#fffdf4"); f2.pack(side="left", fill="x", expand=True, padx=(4, 0))
    app._label(f1, "สถานะ", size=8, color=MUTED, bg="#fffdf4").pack(anchor="w", pady=(0, 2))
    app.status_box = ttk.Combobox(f1, values=STATUSES, state="readonly"); app.status_box.pack(fill="x")
    app._label(f2, "ความสำคัญ", size=8, color=MUTED, bg="#fffdf4").pack(anchor="w", pady=(0, 2))
    app.priority_box = ttk.Combobox(f2, values=PRIORITIES, state="readonly"); app.priority_box.pack(fill="x")
    app._label(detail, "กำหนดส่ง (YYYY-MM-DD)", size=8, color=MUTED, bg="#fffdf4").pack(anchor="w", padx=11, pady=(6, 2))
    app.due_entry = tk.Entry(detail, bg="white", fg=INK, relief="flat", font=("Leelawadee UI", 9), insertbackground=GREEN)
    app.due_entry.pack(fill="x", padx=10, ipady=5)
    app._label(detail, "บันทึก / ขั้นตอนถัดไป", size=8, color=MUTED, bg="#fffdf4").pack(anchor="w", padx=11, pady=(6, 2))
    app.notes = tk.Text(detail, height=4, wrap="word", bg="white", fg=INK, relief="flat", bd=0,
                        font=("Leelawadee UI", 8), padx=7, pady=5, insertbackground=GREEN)
    app.notes.pack(fill="both", expand=True, padx=10)
    app.source_label = app._label(detail, "อ้างอิง: เลือกเควสเพื่อดู", size=7, color=MUTED,
                                  bg="#fffdf4", justify="left", anchor="w", wraplength=290)
    app.source_label.pack(fill="x", padx=11, pady=(4, 1))
    actions = tk.Frame(detail, bg="#fffdf4"); actions.pack(fill="x", padx=10, pady=(3, 4))
    app._button(actions, "บันทึก", app.save_selected, primary=True).pack(side="left", fill="x", expand=True, padx=(0, 4))
    app._button(actions, "เคลียร์เควส", app.complete_selected).pack(side="left", fill="x", expand=True, padx=(4, 0))
    tk.Label(detail, textvariable=app.status_var, bg="#fffdf4", fg=GREEN,
             font=("Leelawadee UI", 8), anchor="w").pack(fill="x", padx=11, pady=(0, 4))

    app._label(profile_page, "PLAYER PROFILE", size=9, color=AMBER, bold=True, bg="#fffdf4").pack(anchor="w", padx=11, pady=(8, 3))
    app.character_canvas = tk.Canvas(profile_page, height=68, bg="#263b46", highlightthickness=0)
    app.character_canvas.pack(fill="x", padx=9)
    app.character_canvas.bind("<Configure>", app.draw_character_sprite)
    app.profile_level = app._label(profile_page, "LV. 1 · Junior Researcher", size=10, color=GREEN, bold=True, bg="#fffdf4")
    app.profile_level.pack(anchor="w", padx=11, pady=(5, 0))
    app.profile_xp_label = app._label(profile_page, "0 / 100 XP", size=8, color=MUTED, bg="#fffdf4")
    app.profile_xp_label.pack(anchor="w", padx=11, pady=(0, 2))
    app.profile_xp_canvas = tk.Canvas(profile_page, height=8, bg="#3c4c52", highlightthickness=0)
    app.profile_xp_canvas.pack(fill="x", padx=11)
    app.profile_xp_canvas.bind("<Configure>", lambda event: app.draw_xp_bar(event.width))
    app._label(profile_page, "เควสหลัก +100 XP · เควสเสริม +30 XP · ครบ 100 XP เลเวลอัป",
               size=7, color=MUTED, bg="#fffdf4").pack(anchor="w", padx=11, pady=(1, 0))
    names = tk.Frame(profile_page, bg="#fffdf4"); names.pack(fill="x", padx=10, pady=(5, 1))
    nleft = tk.Frame(names, bg="#fffdf4"); nleft.pack(side="left", fill="x", expand=True, padx=(0, 4))
    nright = tk.Frame(names, bg="#fffdf4"); nright.pack(side="left", fill="x", expand=True, padx=(4, 0))
    app._label(nleft, "ชื่อตัวละคร", size=7, color=MUTED, bg="#fffdf4").pack(anchor="w")
    app.character_name_entry = tk.Entry(nleft, bg="white", fg=INK, relief="flat", font=("Leelawadee UI", 8))
    app.character_name_entry.pack(fill="x", ipady=3)
    app._label(nright, "ชื่อหุ่น", size=7, color=MUTED, bg="#fffdf4").pack(anchor="w")
    app.robot_name_entry = tk.Entry(nright, bg="white", fg=INK, relief="flat", font=("Leelawadee UI", 8))
    app.robot_name_entry.pack(fill="x", ipady=3)
    app._button(profile_page, "เซฟชื่อตัวละคร / หุ่น", app.save_game_profile).pack(fill="x", padx=10, pady=(2, 4))
    app.profile_status = tk.StringVar(value="")
    tk.Label(profile_page, textvariable=app.profile_status, bg="#fffdf4", fg=GREEN,
             font=("Leelawadee UI", 7), anchor="w").pack(fill="x", padx=11)
    app._label(profile_page, "SIMULATION RUNS · RECENT", size=8, color=AMBER, bold=True, bg="#fffdf4").pack(anchor="w", padx=11, pady=(7, 2))
    app.test_runs_label = app._label(profile_page, "ยังไม่มีผลจำลอง", size=7, color=MUTED, bg="#fffdf4", justify="left", anchor="w", wraplength=300)
    app.test_runs_label.pack(fill="x", padx=11, pady=(0, 4))
    app._label(profile_page, "ROBOT LOADOUT · EQUIPPED ITEMS", size=8, color=AMBER, bold=True, bg="#fffdf4").pack(anchor="w", padx=11, pady=(4, 2))
    app.robot_canvas = tk.Canvas(profile_page, height=72, bg="#263b46", highlightthickness=0)
    app.robot_canvas.pack(fill="x", padx=9, pady=(0, 4))
    app.robot_canvas.bind("<Configure>", app.draw_robot_sprite)
    app.equipment_boxes = {}
    for slot in ["Camera", "Vision AI", "Orientation", "Target ID", "Controller", "Range"]:
        row = tk.Frame(profile_page, bg="#fffdf4"); row.pack(fill="x", padx=10, pady=1)
        app._label(row, slot.upper(), size=7, color=MUTED, bold=True, bg="#fffdf4", width=12, anchor="w").pack(side="left")
        options = [""] + [item["name"] for item in app.unlocked_equipment() if item["slot"] == slot]
        box = ttk.Combobox(row, values=options, state="readonly", width=26)
        box.pack(side="left", fill="x", expand=True)
        box.bind("<<ComboboxSelected>>", lambda _e, s=slot: app.equip_item(s))
        app.equipment_boxes[slot] = box
    app.locked_gear_label = app._label(profile_page, "LOCKED GEAR", size=7, color=RED, bg="#fffdf4",
                                       justify="left", anchor="w", wraplength=300)
    app.locked_gear_label.pack(fill="x", padx=11, pady=(4, 1))
    app._label(profile_page, "โหลดเอาต์นี้เป็นโปรไฟล์เกม ไม่เชื่อมต่อหรือสั่งงานหุ่นจริง",
               size=7, color=MUTED, bg="#fffdf4", wraplength=300, justify="left").pack(anchor="w", padx=11, pady=(0, 4))

    log_panel = tk.Frame(body, bg=PANEL, highlightbackground=LINE, highlightthickness=1, height=137)
    app.log_panel = log_panel
    log_panel.pack(side="bottom", fill="x")
    log_panel.pack_propagate(False)
    log_head = tk.Frame(log_panel, bg=PANEL); log_head.pack(fill="x", padx=11, pady=(4, 2))
    app._label(log_head, "QUEST LOG", size=9, bold=True, bg=PANEL).pack(side="left")
    app.filter_box = ttk.Combobox(log_head, textvariable=app.filter_var,
                                  values=["Main Quest", "Side Quest", "ทุกเควส"] + PHASES,
                                  state="readonly", width=23)
    app.filter_box.pack(side="right")
    app.filter_box.bind("<<ComboboxSelected>>", lambda _e: app.refresh())
    treewrap = tk.Frame(log_panel, bg=PANEL); treewrap.pack(fill="both", expand=True, padx=7, pady=(0, 4))
    cols = ("quest", "phase", "status", "priority", "due")
    app.tree = ttk.Treeview(treewrap, columns=cols, show="tree headings", selectmode="browse")
    app.tree.heading("#0", text="เควส", anchor="w"); app.tree.column("#0", width=310, minwidth=180, stretch=True)
    for col, label, width in [("quest", "ด่าน", 80), ("phase", "หมวด", 125), ("status", "สถานะ", 82), ("priority", "สำคัญ", 55), ("due", "ส่ง", 75)]:
        app.tree.heading(col, text=label, anchor="w"); app.tree.column(col, width=width, minwidth=50, stretch=False, anchor="w")
    app.tree.tag_configure("done", foreground="#78877f")
    app.tree.tag_configure("blocked", foreground=RED)
    app.tree.bind("<<TreeviewSelect>>", app.on_select)
    scroll = ttk.Scrollbar(treewrap, orient="vertical", command=app.tree.yview)
    app.tree.configure(yscrollcommand=scroll.set)
    app.tree.pack(side="left", fill="both", expand=True); scroll.pack(side="right", fill="y")
    log_panel.pack_forget()
