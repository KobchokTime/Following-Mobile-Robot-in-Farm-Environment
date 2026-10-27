"""Sweep belief_low and belief_switch for the identity belief (same replay as belief_eval.py)."""
import sys, os, io, contextlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
S = sys.argv[1]
with contextlib.redirect_stdout(io.StringIO()):
    import belief_eval as be
from gate_replay import sf
Base = sf.TargetGate
print("belief_low switch | kept own mean, worst | wrong takes mean")
for low in (0.15, 0.05, 0.02):
    for sw in (0.01, 0.003):
        class G(Base):
            def __init__(self, **k):
                super().__init__(**k); self.belief_low, self.belief_switch = low, sw
        sf.TargetGate = G
        kept, wrong = [], []
        for k, (label, frames, others) in be.sep.CLIPS.items():
            r = be.replay(frames, True, be.table(k)); kept.append(r[0]); wrong.append(r[1])
        print(f"{low:10.2f} {sw:6.3f} | {sum(kept) / len(kept):5.1f} {min(kept):5.1f}       | {sum(wrong) / len(wrong):5.1f}")
sf.TargetGate = Base
