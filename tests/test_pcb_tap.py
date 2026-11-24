"""PCB input tap tools (tools/pcb_tap): hold classification, per-update conversion, comparison. Synthetic data."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "pcb_tap"))

import compare  # noqa: E402
import to_updates  # noqa: E402


class ClassifyTest(unittest.TestCase):
    def test_short_repeats_are_holds_long_runs_are_still_pictures(self):
        flags = ["B", "B", "0", "1", "0", "1", "1", "0", "1", "1", "1", "1", "0"]
        self.assertEqual(to_updates.classify(flags, max_run=2),
                         ["B", "B", "A", "H", "A", "H", "H", "A", "A", "A", "A", "A", "A"])


class UpdatesTest(unittest.TestCase):
    def test_held_refreshes_drop_out_and_are_counted(self):
        tap = [0x10 + i for i in range(8)]
        flags = ["B", "0", "0", "1", "0", "1", "0", "0", "0"]   # capture starts one frame before tap frame 0
        rows = to_updates.to_updates(tap, flags, offset=None, lag=1)
        # tap frames 0..7 -> capture 1..8; frames 2 and 4 are held
        self.assertEqual([r[1] for r in rows], [0, 1, 3, 5, 6, 7])
        self.assertEqual([r[2] for r in rows], [0, 0, 1, 1, 0, 0])
        self.assertEqual([r[3] for r in rows], [0x10, 0x10, 0x12, 0x14, 0x15, 0x16])


class CompareTest(unittest.TestCase):
    def test_matches_and_extras(self):
        pcb = [0, 1, 0, 0, 2, 0, 0, 0]
        mame = [0, 1, 0, 0, 0, 1, 0, 1]
        rows, events, exact, near, extra = compare.compare(pcb, mame, window=4)
        self.assertEqual(rows, [(0, 4, 1, 1), (4, 8, 2, 2)])
        self.assertEqual((events, exact, near, extra), (2, 1, 2, 1))


if __name__ == "__main__":
    unittest.main()
