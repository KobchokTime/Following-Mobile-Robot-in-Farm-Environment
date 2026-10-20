"""Scripted scenarios for the offline twin.

Coordinates are in the robot's starting frame: x forward, y left, metres. The
target starts 1.0 m ahead (0.8 m to its surface), inside the controller's
initialisation window (`init_dist_min`..`init_dist_max` = 0.5..1.0 m of LiDAR range).
"""

from __future__ import annotations

from typing import Dict

from .world import Person, World

SCENARIOS: Dict[str, dict] = {
    "straight": {
        "doc": "Target walks straight ahead at 0.3 m/s, then stops.",
        "duration_s": 30.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (23, 7.0, 0.0)])],
    },
    "stop_and_go": {
        "doc": "Target walks, stands still for 5 s, then walks again.",
        "duration_s": 30.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (10, 3.1, 0.0),
                                      (15, 3.1, 0.0), (23, 5.5, 0.0)])],
    },
    "curve_left": {
        "doc": "Target walks ahead, then turns about 60 deg to the left.",
        "duration_s": 32.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (13, 4.0, 0.0),
                                      (23, 5.5, 2.6)])],
    },
    "target_loss": {
        "doc": "Straight walk; the detector sees nothing from t=10 s to t=14 s.",
        "duration_s": 30.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (23, 7.0, 0.0)])],
        "blackouts": [(10.0, 14.0)],
    },
    "crossing": {
        "doc": "Straight walk; a second person crosses between robot and target.",
        "duration_s": 30.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (23, 7.0, 0.0)]),
                   ("distractor", False, [(0, 3.4, -2.5), (10, 3.4, -2.5), (14, 3.4, 2.5)])],
    },
}


def build(name: str, seed: int = 0, **robot_overrides) -> World:
    spec = SCENARIOS[name]
    people = [Person(n, list(wp), is_target=tgt) for n, tgt, wp in spec["people"]]
    world = World(people=people, blackouts=spec.get("blackouts", ()), seed=seed)
    for key, value in robot_overrides.items():
        setattr(world.robot, key, value)
    return world
