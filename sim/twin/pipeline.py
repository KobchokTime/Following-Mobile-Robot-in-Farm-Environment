"""Start and stop the unmodified robot nodes as subprocesses on an isolated ROS domain."""

from __future__ import annotations

import os
import random
import signal
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "ros2_yolo_ws" / "scripts"

# Perception -> fusion -> controller chain, in data-flow order. The camera/YOLO node
# and the LiDAR driver are replaced by the twin world or by a bag.
ROBOT_NODES: Dict[str, Path] = {
    "lidar_sectorizer": SCRIPTS / "Lidar" / "lidar_sectorizer_node.py",
    "sync_fusion": SCRIPTS / "Image" / "sync_fusion_node.py",
    "fusion_prob": SCRIPTS / "Image" / "fusion_prob_node.py",
    "follow_stop": SCRIPTS / "MAIN" / "Control" / "follow_stop_node.py",
}

# Topics worth keeping in a bag: sensor inputs, intermediate products and the command.
RECORD_TOPICS = ["/scan", "/target_centroid_sector", "/target_centroid", "/lidar_sector_dists",
                 "/synced_target", "/target_fused_prob", "/cmd_vel", "/sim/state"]


def isolated_env() -> dict:
    return dict(os.environ, ROS_DOMAIN_ID=str(random.randint(100, 200)),
                ROS_LOCALHOST_ONLY="1", PYTHONUNBUFFERED="1")


class Processes:
    """Background processes that log to files and are stopped with SIGINT, then SIGKILL."""

    def __init__(self, out: Path, env: dict) -> None:
        self.out, self.env = out, env
        self.procs: List[subprocess.Popen] = []
        self.logs = []

    def start(self, name: str, cmd: Sequence[str], cwd: Path) -> subprocess.Popen:
        log = open(self.out / f"{name}.log", "w", encoding="utf-8")
        self.logs.append(log)
        proc = subprocess.Popen(list(cmd), cwd=str(cwd), env=self.env, stdout=log,
                                stderr=subprocess.STDOUT, start_new_session=True)
        self.procs.append(proc)
        return proc

    def start_robot_nodes(self) -> None:
        for name, path in ROBOT_NODES.items():
            self.start(name, [sys.executable, str(path)], SCRIPTS)

    def stop(self) -> None:
        for p in reversed(self.procs):
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGINT)
        for p in self.procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
        for log in self.logs:
            log.close()
