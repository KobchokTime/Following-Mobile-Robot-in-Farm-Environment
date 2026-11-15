"""Patch a copy of sync_fusion_node.py to log every gate decision ([GDBG] lines), as used for the
side_step traces in this folder. Not for the robot.

    python3 experiments/sim/box_range_debug/make_debug_build.py <tree>   # patches <tree> in place
    docker build -q --build-arg INSTALL_MCAP=0 -f sim/docker/Dockerfile -t twin:ssdbg <tree>
    docker run --rm -v $PWD/out:/repo/sim_runs twin:ssdbg python3 -m sim.twin.run_scenario \\
        --scenario side_step --bridge-mode mps --realism --ros-param box_range_from_scan:=true \\
        --seed 10 --out sim_runs/d_true_s10
    grep GDBG out/d_true_s10/side_step_mps/sync_fusion.log
"""
import sys
from pathlib import Path

p = Path(sys.argv[1]) / 'ros2_yolo_ws/scripts/Image/sync_fusion_node.py'
s = p.read_text()
patches = [
    ('''        if self.use_gate and not self.gate.accept(ty, bearing, dist, chroma, hist):''',
     '''        _g = self.gate; _pb = _g._predict(ty) if _g.locked else (0, 0)
        _c = _g.cost(ty, bearing, dist, chroma, hist) if _g.locked else -1
        _sec = lidar_data[lidar_sector] if lidar_sector is not None else -1
        _ok = (not self.use_gate) or self.gate.accept(ty, bearing, dist, chroma, hist)
        self.get_logger().info(f"[GDBG] t={ty:.2f} b={math.degrees(bearing):.1f} d={dist:.2f} sec={_sec:.2f} pb={math.degrees(_pb[0]):.1f} pr={_pb[1]:.2f} cost={_c:.2f} ok={_ok}")
        if not _ok:'''),
    ('''        if not math.isfinite(dist):
            self.get_logger().debug(''',
     '''        if not math.isfinite(dist):
            self.get_logger().info(f"[GDBG] t={ty:.2f} b={math.degrees(bearing):.1f} sec={lidar_data[lidar_sector] if lidar_sector is not None else -1:.2f} skip-inf")
            self.get_logger().debug('''),
    ('''        self.gate.accept_lidar(now, bearing, rng)''',
     '''        self.get_logger().info(f"[GDBG] t={now:.2f} lidar-track b={math.degrees(bearing):.1f} r={rng:.2f}")
        self.gate.accept_lidar(now, bearing, rng)'''),
]
for old, new in patches:
    assert s.count(old) == 1, old[:60]
    s = s.replace(old, new)
p.write_text(s)
