"""The committed patch parses and carries no long literal runs (no game data)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "patcher"))
sys.path.insert(0, str(ROOT / "scripts"))

import apply_kuro_patch  # noqa: E402
import make_patch  # noqa: E402


class PatchTest(unittest.TestCase):
    def test_patch_is_small_and_has_no_game_data(self):
        src_size, dst_size, src_md5, _sha, _note, records = apply_kuro_patch.read_patch(
            ROOT / "patcher" / "ibara_kuro.patch")
        self.assertEqual(src_size, make_patch.SOURCE_SIZE)
        self.assertEqual(src_md5, make_patch.SOURCE_MD5)
        literal = [len(op[1]) for _a, _n, ops in records for op in ops if op[0] == 1]
        self.assertLessEqual(max(literal), make_patch.MAX_DATA_RUN)
        self.assertLessEqual(sum(literal), make_patch.MAX_DATA_TOTAL)
        for at, length, ops in records:
            self.assertEqual(sum(op[2] if op[0] == 0 else len(op[1]) for op in ops), length)
            self.assertLessEqual(at + length, dst_size)

    def test_rank_gauge_edits_are_word_aligned_and_distinct(self):
        import build_ee_hooks
        addrs = [a for a, _o, _n in build_ee_hooks.RANK_GAUGE_EDITS]
        self.assertEqual(len(addrs), len(set(addrs)))
        self.assertTrue(all(a % 4 == 0 for a in addrs))


if __name__ == "__main__":
    unittest.main()
