"""The committed patch parses and carries no long literal runs (no game data)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "patcher"))
sys.path.insert(0, str(ROOT / "scripts"))

import apply_kuro_patch  # noqa: E402
import make_patch  # noqa: E402
import native_menu_label  # noqa: E402


class PatchTest(unittest.TestCase):
    def test_patch_is_small_and_has_no_game_data(self):
        src_size, dst_size, src_md5, _sha, _note, records = apply_kuro_patch.read_patch(
            ROOT / "patcher" / "ibara_kuro.patch")
        self.assertEqual(src_size, make_patch.SOURCE_SIZE)
        self.assertLessEqual(dst_size, src_size, "project rule: the ISO must never grow")
        self.assertEqual(src_md5, make_patch.SOURCE_MD5)
        literal = [len(op[1]) for _a, _n, ops in records for op in ops if op[0] == 1]
        self.assertLessEqual(max(literal), make_patch.MAX_DATA_RUN)
        self.assertLessEqual(sum(literal), make_patch.MAX_DATA_TOTAL)
        for at, length, ops in records:
            self.assertEqual(sum(op[2] if op[0] == 0 else len(op[1]) for op in ops), length)
            self.assertLessEqual(at + length, dst_size)

    def test_native_menu_art_uses_only_disc_copies(self):
        # SLPM-66301, IBARAR.PDM resource 945's image data starts after a 64-byte TIM2 header.
        pixels = 0xDEB50840
        spans = list(native_menu_label.copy_spans(pixels))
        _s, _d, _m, _sha, _note, records = apply_kuro_patch.read_patch(ROOT / "patcher/ibara_kuro.patch")
        copied = []
        for at, length, ops in records:
            if at >= pixels + 65536 or at + length <= pixels:
                continue
            for op in ops:
                self.assertEqual(op[0], make_patch.OP_COPY)
                _, src, size = op
                if src != at:
                    copied.append((at, src, size))
                at += size
        self.assertEqual(copied, spans)

    def test_native_header_keeps_a_word_space_after_outlining(self):
        # header_spans adds a one-pixel shadow to either side of the lettering.
        *_, noir_r, mode = native_menu_label.HEADER_GLYPHS
        noir_end = noir_r[3] + noir_r[4]
        self.assertGreaterEqual(mode[3] - noir_end - 2, 4)

    def test_native_header_copies_the_reserved_plaque_from_its_atlas(self):
        pixels = 0xDEB61040  # SLPM-66301, IBARAR.PDM resource 946
        width = native_menu_label.ATLAS_WIDTH
        left, top, right, bottom = native_menu_label.HEADER_BOX
        _s, _d, _m, _sha, _note, records = apply_kuro_patch.read_patch(ROOT / "patcher" / "ibara_kuro.patch")
        copied = 0
        for at, length, ops in records:
            if at >= pixels + width ** 2 or at + length <= pixels:
                continue
            for op in ops:
                self.assertEqual(op[0], make_patch.OP_COPY)
                _, src, size = op
                if src != at:
                    y, x = divmod(at - pixels, width)
                    self.assertTrue(top <= y < bottom and left <= x < x + size <= right)
                    self.assertTrue(pixels <= src < src + size <= pixels + width ** 2)
                    copied += size
                at += size
        self.assertEqual(copied, (right - left) * (bottom - top))

    def test_patch_has_an_empty_rank_bar_art_slot(self):
        # the art slot is in the patch's literal bytes, tag then 2,240 zero bytes (art comes from the user's ROM)
        _s, _d, _m, _sha, _note, records = apply_kuro_patch.read_patch(ROOT / "patcher" / "ibara_kuro.patch")
        lits = [op[1] for _a, _n, ops in records for op in ops if op[0] == 1]
        hits = [b for b in lits if apply_kuro_patch.BL_ART_TAG in b]
        self.assertEqual(len(hits), 1)
        k = hits[0].index(apply_kuro_patch.BL_ART_TAG) + len(apply_kuro_patch.BL_ART_TAG)
        art = hits[0][k:k + 2 * apply_kuro_patch.BL_ART_W * apply_kuro_patch.BL_ART_H]
        self.assertTrue(len(art) < 2 * 80 * 14 or not any(art))  # zero art (or zero bytes encoded as copies)

    def test_bl_rom_is_checked(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "ibarablk_u2"
            bad.write_bytes(b"\0" * 1024)
            with self.assertRaises(SystemExit):
                apply_kuro_patch.read_bl_art(bad)

    def test_rank_gauge_edits_are_word_aligned_and_distinct(self):
        import build_ee_hooks
        addrs = [a for a, _o, _n in build_ee_hooks.RANK_GAUGE_EDITS]
        self.assertEqual(len(addrs), len(set(addrs)))
        self.assertTrue(all(a % 4 == 0 for a in addrs))


if __name__ == "__main__":
    unittest.main()
