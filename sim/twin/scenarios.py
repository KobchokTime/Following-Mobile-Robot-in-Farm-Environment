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

# One person only, at realistic walking speeds and with the moves a farm worker makes. The earlier
# scenarios walk at 0.3 m/s; people usually walk at 1.0-1.4 m/s.
SOLO_SCENARIOS: Dict[str, dict] = {
    "walk_0p6": {
        "doc": "Target walks straight at 0.6 m/s for 10 s, then stops.",
        "duration_s": 25.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (13, 7.0, 0.0)])],
    },
    "walk_1p0": {
        "doc": "Target walks straight at 1.0 m/s (normal walking) for 8 s, then stops.",
        "duration_s": 30.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (11, 9.0, 0.0)])],
    },
    "turn_90": {
        "doc": "Target walks 3 m at 0.4 m/s, turns 90 degrees left and walks 3 m more.",
        "duration_s": 30.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (10.5, 4.0, 0.0), (18, 4.0, 3.0)])],
    },
    "come_back": {
        "doc": "Target walks 3 m away at 0.4 m/s, turns round and walks 1.5 m back towards the robot, "
               "as a worker does to load the cart, then stands.",
        "duration_s": 30.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (10.5, 4.0, 0.0), (12, 4.0, 0.0),
                                      (15.75, 2.5, 0.0)])],
    },
    "side_step": {
        "doc": "Target steps 1 m sideways (out of the camera's view at this range), then walks on.",
        "duration_s": 30.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (6, 2.2, 0.0), (7, 2.2, 1.0),
                                      (14, 5.0, 1.0)])],
    },
    "zigzag": {
        "doc": "Target weaves 0.6 m left and right every 3 s while walking at 0.4 m/s.",
        "duration_s": 30.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (6, 2.2, 0.6), (9, 3.4, -0.6),
                                      (12, 4.6, 0.6), (15, 5.8, -0.6), (18, 7.0, 0.0)])],
    },
}

# Clothing colour in shade, as in the 2025-04-08 lab videos: a blue top fades towards grey in shade,
# next to someone in a dark grey top. Not in the identity set, which stays as Arena 3 froze it.
BLUE_TOP = (160.0, 110.0)
GREY_TOP = (131.0, 128.0)
COLOUR_SCENARIOS: Dict[str, dict] = {
    "shade_crossing": {
        "doc": "As crossing, but the target wears blue, the crosser dark grey, and both are in deep shade there.",
        "duration_s": 30.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (23, 7.0, 0.0)]),
                   ("distractor", False, [(0, 3.4, -2.5), (10, 3.4, -2.5), (14, 3.4, 2.5)])],
        "clothing": {"target": BLUE_TOP, "distractor": GREY_TOP},
        "shade": [(2.5, 6.0, 0.3)],
    },
    "shade_side_by_side": {
        "doc": "As side_by_side, but the target wears blue, the other person dark grey, and the start is in shade.",
        "duration_s": 32.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (13, 4.0, 0.0), (23, 5.5, 2.6)]),
                   ("distractor", False, [(0, 1.8, -0.7), (3, 1.8, -0.7), (13, 4.8, -0.7), (23, 7.5, -3.0)])],
        "clothing": {"target": BLUE_TOP, "distractor": GREY_TOP},
        "shade": [(0.0, 5.0, 0.3)],
    },
    "lookalike_after_loss": {
        "doc": "Straight walk; the camera loses the target from t=10 s to t=12 s (LiDAR still sees it), "
               "while someone in the same clothes stands about 7.4 m away, 18 deg to the left (T13).",
        "duration_s": 30.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (23, 7.0, 0.0)]),
                   ("distractor", False, [(0, 9.1, 6.0), (9, 9.1, 6.0), (10.5, 9.1, 2.3), (13, 9.1, 2.3),
                                          (16, 9.1, 6.0)])],
        "clothing": {"distractor": TARGET_CLOTHING},
        "hidden": {"target": [(10.0, 12.0)]},
    },
    "close_pair_same": {
        "doc": "Two people in the same clothes walk side by side 0.44 m apart (centres), both in view and apart "
               "in the image, then the other one turns left while the target walks on (T15).",
        "duration_s": 30.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (13, 4.0, 0.0), (23, 7.0, 0.0)]),
                   ("distractor", False, [(0, 1.0, 0.44), (3, 1.0, 0.44), (13, 4.0, 0.44), (18, 5.5, 3.0)])],
        "clothing": {"distractor": TARGET_CLOTHING},
    },
    "walk_up_same": {
        "doc": "A stranger in the same clothes walks up from the right, unseen by the camera until they are 0.40 m "
               "beside the target at t=8 s (their box comes first in each frame), walks beside them, then turns "
               "away to the right (T15 follow-up).",
        "duration_s": 30.0,
        "people": [("stranger", False, [(0, 3.0, -2.5), (5, 3.0, -2.5), (8, 2.55, -0.40), (13, 4.05, -0.40),
                                        (18, 5.5, -3.0)]),
                   ("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (13, 4.0, 0.0), (23, 7.0, 0.0)])],
        "clothing": {"stranger": TARGET_CLOTHING},
        "hidden": {"stranger": [(0.0, 8.0)]},
    },
}

OBSTACLE_SCENARIOS: Dict[str, dict] = {
    "blind_corner": {
        "doc": "turn_90 with someone the camera never detects standing at the inside of the corner, 0.45 m from "
               "the target's path. A robot cutting the corner meets them; only the LiDAR sees them (obstacle stop).",
        "duration_s": 30.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (10.5, 4.0, 0.0), (18, 4.0, 3.0)]),
                   ("bystander", False, [(0, 3.55, 0.55), (30, 3.55, 0.55)])],
        "hidden": {"bystander": [(0.0, 30.0)]},
    },
    "pass_by": {
        "doc": "straight: the target walks past someone the camera never detects (a worker crouched at the row), "
               "0.42 m to the side of the target's line. A robot that keeps to the target's line touches them; "
               "there is room on the other side to swerve (obstacle avoid).",
        "duration_s": 22.0,
        "people": [("target", True, [(0, 1.0, 0.0), (3, 1.0, 0.0), (15, 7.0, 0.0), (22, 7.0, 0.0)]),
                   ("bystander", False, [(0, 4.0, 0.42), (22, 4.0, 0.42)])],
        "hidden": {"bystander": [(0.0, 22.0)]},
    },
}

ALL_SCENARIOS: Dict[str, dict] = {**SCENARIOS, **IDENTITY_SCENARIOS}  # frozen: the Arena 3 scorer checks runs against it
SCENARIO_LOOKUP: Dict[str, dict] = {**ALL_SCENARIOS, **SOLO_SCENARIOS, **COLOUR_SCENARIOS, **OBSTACLE_SCENARIOS}  # every scenario that can be run
SCENARIO_SETS: Dict[str, list] = {
    "all": sorted(SCENARIOS),  # the Arena 2 set; kept as "all" so existing commands mean the same
    "identity": ["crossing", *sorted(IDENTITY_SCENARIOS)],
    "everything": sorted(ALL_SCENARIOS),
    "solo": ["straight", "stop_and_go", "curve_left", "target_loss", *sorted(SOLO_SCENARIOS)],
    "colour": sorted(COLOUR_SCENARIOS),
    "obstacle": sorted(OBSTACLE_SCENARIOS),
}


def make_people(spec: dict) -> list:
    clothing = spec.get("clothing", {})
    return [Person(n, list(wp), is_target=tgt,
                   clothing=clothing.get(n, TARGET_CLOTHING if tgt else OTHER_CLOTHING))
            for n, tgt, wp in spec["people"]]


def build(name: str, seed: int = 0, realism=None, **robot_overrides) -> World:
    spec = SCENARIO_LOOKUP[name]
    world = World(people=make_people(spec), blackouts=spec.get("blackouts", ()), shade=spec.get("shade", ()),
                  hidden=spec.get("hidden", {}), seed=seed,
                  realism=realism)
    for key, value in robot_overrides.items():
        setattr(world.robot, key, value)
    return world
