"""Offline tests for the Arena 3 draft scorer (sim/arena/score_entry_v3.py) and the new scenarios."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sim.arena.score_entry_v3 import BRIDGE_MODES, GAZEBO_MIN, IDENTITY, score, validate  # noqa: E402
from sim.twin.scenarios import ALL_SCENARIOS, IDENTITY_SCENARIOS, SCENARIO_SETS, SCENARIOS, build  # noqa: E402


def _result(scenario, mode, seed, gap=0.5, **kw):
    r = {"scenario": scenario, "bridge_mode": mode, "seed": seed, "median_gap_m": gap, "final_gap_m": gap,
         "target_in_camera_fov_end": True, "contact": False, "turned": True, "target_tracked_share": 1.0,
         "stop_latency_s": 1.0 if scenario == "target_loss" else None}
    r.update(kw)
    return r


def _twin(seed):
    return [_result(sc, m, seed) for sc in ALL_SCENARIOS for m in BRIDGE_MODES]


def _gazebo():
    return [_result(sc, "fixed", 0) for sc, n in GAZEBO_MIN.items() for _ in range(n)]


class Arena3ScenarioTest(unittest.TestCase):
    def test_arena2_set_is_unchanged(self):
        self.assertEqual(sorted(SCENARIOS), ["crossing", "curve_left", "stop_and_go", "straight", "target_loss"])
        self.assertEqual(SCENARIO_SETS["all"], sorted(SCENARIOS))

    def test_identity_scenarios_have_one_target_and_one_other_person(self):
        for name in IDENTITY_SCENARIOS:
            w = build(name)
            self.assertEqual(sum(p.is_target for p in w.people), 1, name)
            self.assertEqual(len(w.people), 2, name)
            self.assertTrue(w.people_robot_frame()["target"][0] > 0.5, name)

    def test_identity_set_covers_the_scored_scenarios(self):
        self.assertEqual(sorted(SCENARIO_SETS["identity"]), sorted(IDENTITY))


class Arena3ScorerTest(unittest.TestCase):
    def test_full_protocol_is_valid_and_perfect_scores_100(self):
        runs = [_twin(s) for s in range(3)]
        self.assertEqual(validate(runs, _gazebo()), [])
        self.assertEqual(score(runs, _gazebo())["points"], 100.0)

    def test_missing_gazebo_identity_runs(self):
        gz = [r for r in _gazebo() if r["scenario"] != "stand_aside"]
        self.assertTrue(validate([_twin(0), _twin(1), _twin(2)], gz))

    def test_missing_scenario_or_bridge(self):
        partial = [r for r in _twin(2) if not (r["scenario"] == "head_on" and r["bridge_mode"] == "diff_drive")]
        self.assertTrue(validate([_twin(0), _twin(1), partial], _gazebo()))

    def test_following_the_wrong_person_fails_the_run(self):
        runs = [_twin(s) for s in range(3)]
        for r in runs[0]:
            if r["scenario"] == "side_by_side" and r["bridge_mode"] == "fixed":
                r.update(final_gap_m=5.2, target_in_camera_fov_end=False, target_tracked_share=0.4, contact=True)
        result = score(runs, _gazebo())
        self.assertEqual(result["identity"]["passed_per_scenario"]["side_by_side"], "4/5")
        self.assertIn("contact in at least one run", result["behaviour"]["failed_checks"])
        self.assertLess(result["points"], 95.0)

    def test_low_tracked_share_fails_even_when_the_end_looks_fine(self):
        runs = [_twin(s) for s in range(3)]
        row = next(r for r in runs[1] if r["scenario"] == "stand_aside" and r["bridge_mode"] == "fixed")
        row["target_tracked_share"] = 0.5
        result = score(runs, _gazebo())["identity"]
        self.assertEqual((result["passed"], result["runs"]), (20, 21))

if __name__ == "__main__":
    unittest.main()
