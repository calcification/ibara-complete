"""Regression checks for the retail Arcade slowdown acceptance score."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "phase22"))
from score_slowdown import compare, read_trace, slowdowns


def ticks_with_holds(holds, updates=40):
    ticks = [100]
    for frame in range(1, updates + len(holds) + 1):
        ticks.append(ticks[-1] + (frame not in holds))
    return ticks


class SlowdownScoreTests(unittest.TestCase):
    def test_bursts_group_alternation_but_split_longer_pauses_between_holds(self):
        events = slowdowns(ticks_with_holds({2, 4, 9, 15}))
        self.assertEqual([(e.onset, e.last_hold, e.held_refreshes) for e in events], [(2, 9, 3), (15, 15, 1)])

    def test_four_matches_out_of_five_meet_the_target(self):
        reference = {str(i): ticks_with_holds({7, 9, 11, 13, 15}) for i in range(5)}
        candidate = dict(reference)
        candidate["0"] = ticks_with_holds(set())
        result = compare(reference, candidate, "pcb")
        self.assertEqual((result["matched_events"], result["missed_events"], result["score_percent"]), (4, 1, 80))
        self.assertIs(result["meets_pcb_80_percent_target"], True)

    def test_false_holds_count_against_the_score(self):
        reference = {"boss": ticks_with_holds({3, 8}), "quiet": ticks_with_holds(set())}
        candidate = {"boss": reference["boss"], "quiet": ticks_with_holds({6})}
        result = compare(reference, candidate, "pcb")
        self.assertEqual((result["matched_events"], result["extra_events"], result["score_percent"]), (1, 1, 50))
        self.assertIs(result["meets_pcb_80_percent_target"], False)
        self.assertEqual(result["windows"]["quiet"]["first_cadence_difference"], 6)
        self.assertIsNone(result["windows"]["boss"]["first_cadence_difference"])

    def test_onset_and_duration_tolerances(self):
        reference = {"boss": ticks_with_holds({3, 4, 5, 6, 7})}
        okay = {"boss": ticks_with_holds({7, 8, 9, 10})}
        late = {"boss": ticks_with_holds({8, 9, 10, 11})}
        short = {"boss": ticks_with_holds({7, 8, 9})}
        self.assertEqual(compare(reference, okay, "pcb")["matched_events"], 1)
        self.assertEqual(compare(reference, late, "pcb")["matched_events"], 0)
        self.assertEqual(compare(reference, short, "pcb")["matched_events"], 0)

    def test_quiet_and_diagnostic_comparisons_cannot_pass_the_pcb_gate(self):
        quiet = {"test": ticks_with_holds(set())}
        slowed = {"test": ticks_with_holds({7})}
        self.assertIsNone(compare(quiet, quiet, "pcb")["score_percent"])
        self.assertIsNone(compare(quiet, slowed, "pcb")["meets_pcb_80_percent_target"])
        self.assertIsNone(compare(slowed, slowed, "diagnostic")["meets_pcb_80_percent_target"])

    def test_mismatched_gameplay_endpoints_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "same number of gameplay updates"):
            compare({"boss": [10, 11, 12]}, {"boss": [105, 106]}, "diagnostic")

    def test_csv_checks_missing_refreshes_and_incomplete_last_update(self):
        with tempfile.TemporaryDirectory() as work:
            path = Path(work, "trace.csv")
            path.write_text("window,frame,tick\nboss,0,4\nboss,1,4\nboss,2,5\n", encoding="utf-8")
            self.assertEqual(read_trace(path), {"boss": [4, 4, 5]})
            path.write_text("window,frame,tick\nboss,0,4\nboss,2,5\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "consecutive"):
                read_trace(path)
            path.write_text("window,frame,tick\nboss,0,4\nboss,1,4\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "advancing refresh"):
                read_trace(path)


if __name__ == "__main__":
    unittest.main()
