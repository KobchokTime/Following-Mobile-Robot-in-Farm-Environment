# Role: thesis-desk

**Scope (may change):** `tools/thesis_desk/`. That covers the Tkinter tracker (`app.py`,
`game_ui.py`), the Godot game (`godot_game/`), `thesis_data.json` and the launchers.

**Rules**
- Everything is simulation. The game and the tracker never talk to real hardware.
- `thesis_data.json` is seed data. Do not commit personal play state, such as XP, position or
  run history.
- Quest `source` paths must exist in the repo. `scripts/check.py` warns when they don't.
- Keep the Python side on the standard library only.

**Checks:** `scripts/check.py`, and a GUI smoke test of whatever you changed.
- Windows: run the `.bat` launchers.
- Linux: use Xvfb with Godot 4.7.2, run from a disposable copy so the save files stay out of the repo.

**Done when:** checks pass and the log entry says which screens or interactions you verified.
