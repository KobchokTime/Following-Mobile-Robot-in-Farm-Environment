"""Offline tests for the Arena 2 scorer's input validation and scoring (sim/arena/score_entry_v2.py)."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sim.arena.score_entry_v2 import BRIDGE_MODES, score, validate  # noqa: E402
from sim.twin.scenarios import SCENARIOS  # noqa: E402


def _result(scenario, mode, seed, gap=0.8):
    return {"scenario": scenario, "bridge_mode": mode, "seed": seed, "median_gap_m": gap,
            "final_gap_m": gap, "target_in_camera_fov_end": True, "contact": False, "turned": True,
            "stop_latency_s": 1.0 if scenario == "target_loss" else None}


def _twin(seed):
    return [_result(sc, m, seed) for sc in SCENARIOS for m in BRIDGE_MODES]


def _gazebo(n=2):
    return [_result("curve_left", "fixed", 0) for _ in range(n)]


class Arena2ValidationTest(unittest.TestCase):
    def test_full_protocol_is_valid(self):
        self.assertEqual(validate([_twin(0), _twin(1), _twin(2)], _gazebo()), [])

    def test_too_few_twin_repeats(self):
        self.assertTrue(validate([_twin(0), _twin(1)], _gazebo()))

    def test_incomplete_twin_repeat(self):
        partial = [r for r in _twin(2) if r["scenario"] != "straight"]
        self.assertTrue(validate([_twin(0), _twin(1), partial], _gazebo()))

    def test_duplicate_result_in_a_repeat(self):
        run = _twin(2)
        run.append(dict(run[0]))
        self.assertTrue(validate([_twin(0), _twin(1), run], _gazebo()))

    def test_reused_seed(self):
        self.assertTrue(validate([_twin(0), _twin(1), _twin(1)], _gazebo()))

    def test_missing_or_non_integer_seed(self):
        no_seed = [{k: v for k, v in r.items() if k != "seed"} for r in _twin(0)]
        self.assertTrue(validate([no_seed, _twin(1), _twin(2)], _gazebo()))
        for bad in (None, "0", 0.0, True):
            self.assertTrue(validate([_twin(bad), _twin(1), _twin(2)], _gazebo()), bad)

    def test_missing_gazebo(self):
        self.assertTrue(validate([_twin(0), _twin(1), _twin(2)], []))
        self.assertTrue(validate([_twin(0), _twin(1), _twin(2)], _gazebo(1)))

    def test_gazebo_runs_of_other_scenarios_do_not_count(self):
        other = [_result("straight", "fixed", 0), _result("curve_left", "current", 0)]
        self.assertTrue(validate([_twin(0), _twin(1), _twin(2)], other + _gazebo(1)))


class Arena2ScoreTest(unittest.TestCase):
    def test_perfect_entry_scores_100(self):
        runs = [[dict(r, median_gap_m=0.5) for r in _twin(s)] for s in range(3)]
        self.assertEqual(score(runs, _gazebo())["points"], 100.0)

    def test_failed_gazebo_curve_costs_reliability(self):
        gz = _gazebo()
        gz[0]["final_gap_m"] = 2.0
        result = score([_twin(0), _twin(1), _twin(2)], gz)
        self.assertEqual(result["reliability"]["failures"], 1)
        self.assertAlmostEqual(result["reliability"]["points"], 30 * 4 / 5, places=2)


if __name__ == "__main__":
    unittest.main()
