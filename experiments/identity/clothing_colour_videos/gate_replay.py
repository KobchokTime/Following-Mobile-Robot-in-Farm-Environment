"""Replay the lab videos through the robot's own TargetGate, colour only.

Every box is given the gate's predicted bearing and range, so only the colour term decides. Each frame
the boxes are offered best-first (the node offers them in arrival order; geometry usually leaves one
in the gate). Histograms come from the H,S pixel samples (12 x 4 bins, as ros2_yolo_live sends).
Usage: gate_replay.py DATA_DIR
The gate is loaded from ros2_yolo_ws/scripts/Image/sync_fusion_node.py of this checkout, or from the
file in $SYNC_FUSION (the histogram gate is on branch claude/robot/hs-colour).
"""
import sys, os, types, importlib.util
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colour_models import load, hs_hist, VIDS

ROOT = Path(__file__).resolve().parents[3]
names = ["rclpy", "rclpy.node", "rclpy.qos", "std_msgs", "std_msgs.msg", "sensor_msgs", "sensor_msgs.msg", "geometry_msgs", "geometry_msgs.msg"]
stubs = {n: types.ModuleType(n) for n in names}
stubs["rclpy.node"].Node = object
for k in ("QoSProfile", "QoSReliabilityPolicy", "QoSHistoryPolicy", "QoSDurabilityPolicy"):
    setattr(stubs["rclpy.qos"], k, object)
stubs["std_msgs.msg"].Int32MultiArray = stubs["std_msgs.msg"].Float32MultiArray = object
stubs["sensor_msgs.msg"].LaserScan = object
stubs["geometry_msgs.msg"].Twist = object
sys.modules.update(stubs)
spec = importlib.util.spec_from_file_location("sf", os.environ.get("SYNC_FUSION", ROOT / "ros2_yolo_ws/scripts/Image/sync_fusion_node.py"))
sf = importlib.util.module_from_spec(spec); spec.loader.exec_module(sf)


def replay(frames, target, use_hist):
    g = sf.TargetGate(); st = dict(CT=0, CL=0, WT=0, WL=0); ranked = [0, 0]; t = 0.0
    feats = lambda r: ((r['cb'], r['cr']), [float(x) for x in hs_hist(r['hs'])] if use_hist else None)
    for fr in frames:
        t += 0.1
        here = any(r['who'] == target for r in fr)
        if not g.locked:
            first = [r for r in fr if r['who'] == target]
            if first:
                c, h = feats(first[0]); g.accept(t, 0.0, 0.8, c, h)  # lock-on window: 0.8 m, image centre
            continue
        pb, pr = g._predict(t)
        order = sorted(fr, key=lambda r: g.cost(t, pb, pr, *feats(r)))
        if here and any(r['who'] != target for r in fr):
            ranked[0] += order[0]['who'] == target; ranked[1] += 1
        took = next((r for r in order if g.accept(t, pb, pr, *feats(r))), None)
        st[('CT' if took['who'] == target else 'WT') if took else ('WL' if here else 'CL')] += 1
    return st, ranked


if __name__ == "__main__":
    S = sys.argv[1]
    for v, _ in VIDS:
        frames = load(S, v)
        for target in 'BD':
            for use_hist in (False, True):
                st, rk = replay(frames, target, use_hist); n = sum(st.values())
                print(f"{v[4:19]} target={target} {'Cb,Cr + H,S hist' if use_hist else 'Cb,Cr only':16s} ranked first {100 * rk[0] / rk[1]:5.1f}% | "
                      + ' '.join(f"{k} {100 * st[k] / n:5.1f}%" for k in ('CT', 'CL', 'WT', 'WL')))
