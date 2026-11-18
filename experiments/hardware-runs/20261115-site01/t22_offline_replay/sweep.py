"""Timing sweep: replay one bag through one code tree at several YOLO delays and timer phases."""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE / "venv" / "Scripts" / "python.exe"
DELAYS = [0, 20, 40, 60, 80, 100]
PHASES = [0, 25, 50, 75]


def run(bag, code, preset, out, d, ph):
    f = out / f"d{d}_p{ph}.json"
    subprocess.run([str(PY), str(HERE / "offline_replay.py"), bag, "--code", code, "--preset", preset,
                    "--yolo-delay-ms", str(d), "--timer-phase-ms", str(ph), "--out", str(f)],
                   check=True, capture_output=True)
    r = json.loads(f.read_text(encoding="utf-8"))["replayed"]
    return d, ph, r


def main():
    bag, code, preset, out = sys.argv[1:5]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(d, ph) for d in DELAYS for ph in PHASES]
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda j: run(bag, code, preset, out, *j), jobs))
    rows = []
    for d, ph, r in res:
        w = r["wrong_direction"]
        rows.append({"yolo_delay_ms": d, "timer_phase_ms": ph, "wrong": len(w),
                     "wrong_t": [x["t"] for x in w], "cmd_vel": r["cmd_vel"], "synced": r["synced"],
                     "turn_msgs": r["turn_msgs"], "max_abs_wz": r["max_abs_wz"]})
    (out / "sweep.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    bad = [x for x in rows if x["wrong"]]
    print(f"{len(rows)} runs, {len(bad)} with a wrong-direction turn")
    for x in bad:
        print(f"  delay {x['yolo_delay_ms']} ms phase {x['timer_phase_ms']} ms: {x['wrong']} at {x['wrong_t'][:6]}")


if __name__ == "__main__":
    main()
