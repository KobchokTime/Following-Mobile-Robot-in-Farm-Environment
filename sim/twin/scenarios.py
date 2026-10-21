"""Scripted scenarios for the offline twin.

Coordinates are in the robot's starting frame: x forward, y left, metres. The
target starts 1.0 m ahead (0.8 m to its surface), inside the controller's
initialisation window (`init_dist_min`..`init_dist_max` = 0.5..1.0 m of LiDAR range).
"""

from __future__ import annotations

from typing import Dict

from .world import Person, World

# Clothing chroma (Cb, Cr), YCbCr 0-255. The target wears red, other people blue, unless a
# scenario says otherwise.
TARGET_CLOTHING = (110.0, 165.0)
OTHER_CLOTHING = (160.0, 110.0)


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


# Arena 3 (draft): a second person is in view while the robot follows the target. `SCENARIOS`
# stays the Arena 2 set, because the frozen Arena 2 scorer checks a run covers all of it.
IDENTITY_SCENARIOS: Dict[str, dict] = {
    "side_by_side": {
        "doc": "A second person walks ahead-right of the target, then turns right while the target turns left.",
        "duration_s": 32.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (13, 4.0, 0.0), (23, 5.5, 2.6)]),
                   ("distractor", False, [(0, 1.8, -0.7), (3, 1.8, -0.7), (13, 4.8, -0.7), (23, 7.5, -3.0)])],
    },
    "head_on": {
        "doc": "Target walks straight; a second person walks towards the robot and passes 0.8 m to its left.",
        "duration_s": 30.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (23, 7.0, 0.0)]),
                   ("distractor", False, [(0, 9.0, 0.8), (3, 9.0, 0.8), (23, -3.0, 0.8)])],
    },
    "side_by_side_same": {
        "doc": "As side_by_side, but both people wear the same colour, so clothing colour cannot tell them apart.",
        "duration_s": 32.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (13, 4.0, 0.0), (23, 5.5, 2.6)]),
                   ("distractor", False, [(0, 1.8, -0.7), (3, 1.8, -0.7), (13, 4.8, -0.7), (23, 7.5, -3.0)])],
        "clothing": {"distractor": TARGET_CLOTHING},
    },
    "stand_aside": {
        "doc": "Target walks straight past a second person who stands 0.7 m to the right of the path.",
        "duration_s": 30.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (23, 7.0, 0.0)]),
                   ("distractor", False, [(0, 4.0, -0.7), (30, 4.0, -0.7)])],
        "shade": [(3.0, 5.5, 0.5)],  # tree shade around the standing person
    },
}

ALL_SCENARIOS: Dict[str, dict] = {**SCENARIOS, **IDENTITY_SCENARIOS}
SCENARIO_SETS: Dict[str, list] = {
    "all": sorted(SCENARIOS),  # the Arena 2 set; kept as "all" so existing commands mean the same
    "identity": ["crossing", *sorted(IDENTITY_SCENARIOS)],
    "everything": sorted(ALL_SCENARIOS),
}


def make_people(spec: dict) -> list:
    clothing = spec.get("clothing", {})
    return [Person(n, list(wp), is_target=tgt,
                   clothing=clothing.get(n, TARGET_CLOTHING if tgt else OTHER_CLOTHING))
            for n, tgt, wp in spec["people"]]


def build(name: str, seed: int = 0, **robot_overrides) -> World:
    spec = ALL_SCENARIOS[name]
    world = World(people=make_people(spec), blackouts=spec.get("blackouts", ()), shade=spec.get("shade", ()), seed=seed)
    for key, value in robot_overrides.items():
        setattr(world.robot, key, value)
    return world
