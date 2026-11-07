"""past_tracks stays under the dashboard's file limit: gen_live.fit_past_tracks thins the oldest first."""

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("gen_live", ROOT / "tools" / "dashboard" / "live" / "gen_live.py")
gen_live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen_live)


def run(exp, n=40):
    """One run's 2 Hz points (t every 0.5 s)."""
    return [dict(run=f"{exp}|r|straight", t=k / 2, rx=0.0, ry=0.0, ryaw=0.0, v=0.0,
                 tx=None, ty=None, gap=None, tb=None, ox=None, oy=None) for k in range(n)]


def size(rows):
    return len(json.dumps(rows, separators=(",", ":")).encode("utf-8"))


class PastTracksTest(unittest.TestCase):
    past = [(1, [run("old")]), (3, [run("new")]), (2, [run("mid")])]

    def rate(self, rows, exp):
        return sum(r["run"].startswith(exp) for r in rows)

    def test_everything_at_1_hz_when_it_fits(self):
        rows = gen_live.fit_past_tracks(self.past, budget=10**9)
        self.assertEqual([self.rate(rows, e) for e in ("old", "mid", "new")], [20, 20, 20])

    def test_the_oldest_experiment_is_thinned_first(self):
        full = size(gen_live.fit_past_tracks(self.past, budget=10**9))
        rows = gen_live.fit_past_tracks(self.past, budget=full - 1)
        self.assertEqual([self.rate(rows, e) for e in ("old", "mid", "new")], [10, 20, 20])
        self.assertLessEqual(size(rows), full - 1)
        times = [r["t"] for r in rows if r["run"].startswith("old")]
        self.assertEqual(times, sorted(times))  # still increasing within the run, as the validator needs

    def test_thins_until_it_fits(self):
        one_hz = size(gen_live.fit_past_tracks(self.past, budget=10**9))
        rows = gen_live.fit_past_tracks(self.past, budget=one_hz * 7 // 10)  # needs two experiments thinned, not three
        self.assertEqual([self.rate(rows, e) for e in ("old", "mid", "new")], [10, 10, 20])


if __name__ == "__main__":
    unittest.main()
