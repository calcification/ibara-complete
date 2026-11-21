#!/usr/bin/env python3
"""Offline tests for the Phase 12 MIPS extractor and cross-ISA scorer (no game data).

The extractor test compiles a small r5900 program with mips-linux-gnu-gcc (skipped if absent).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research/phase12"))
sys.path.insert(0, str(ROOT / "research/phase11"))
import mips_funcs  # noqa: E402
import xisa_match  # noqa: E402

SRC = r"""
volatile unsigned *const RANK = (unsigned *)0x00338EB4;
int leaf(int x) { return x * 0x1234 + 0x55AA; }
int mid(int x) { *RANK = 0x00FFFFFF; return leaf(x) + leaf(x + 0x777); }
int top(int x) { return mid(x) ^ 0x13579; }
void (*const table[2])(void) = { (void (*)(void))top, (void (*)(void))mid };
"""


@unittest.skipUnless(shutil.which("mips-linux-gnu-gcc"), "mips-linux-gnu toolchain not installed")
class ExtractorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        (d / "t.c").write_text(SRC)
        subprocess.run(["mips-linux-gnu-gcc", "-march=r5900", "-EL", "-mabi=32", "-msoft-float", "-mno-abicalls",
                        "-fno-pic", "-G0", "-O1", "-fno-inline", "-ffreestanding", "-nostdlib", "-no-pie",
                        "-Wl,-Ttext=0x00100000",
                        "-Wl,-e,top", str(d / "t.c"), "-o", str(d / "t.elf")], check=True)
        syms = subprocess.run(["mips-linux-gnu-nm", str(d / "t.elf")], capture_output=True, text=True, check=True).stdout
        cls.sym = {l.split()[2]: int(l.split()[0], 16) for l in syms.splitlines() if len(l.split()) == 3}
        cls.funcs, cls.gp = mips_funcs.extract(mips_funcs.load_elf(d / "t.elf"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_function_starts(self):
        for name in ("leaf", "mid", "top"):
            self.assertIn(self.sym[name], self.funcs, name)

    def test_calls(self):
        self.assertEqual(self.funcs[self.sym["mid"]].calls, [self.sym["leaf"]] * 2)
        self.assertEqual(self.funcs[self.sym["top"]].calls, [self.sym["mid"]])

    def test_constants_and_data_refs(self):
        leaf = self.funcs[self.sym["leaf"]]
        self.assertIn(0x55AA, leaf.consts)
        mid = self.funcs[self.sym["mid"]]
        self.assertIn(0x00FFFFFF, mid.consts)
        self.assertIn(0x777, mid.consts)
        self.assertEqual(xisa_match.tags_for(mid.data_refs, xisa_match.PS2_STRUCTS), {"rank"})


class ScoringTests(unittest.TestCase):
    def test_norm_consts_drops_small_and_addresses(self):
        self.assertEqual(xisa_match.norm_consts([1, -3, 0x0C283794, 0x00FFFFFF, 0x1234, 0x280, 0x290]),
                         {0x00FFFFFF, 0x1234, "STRIDE_PLAYER"})

    def test_mutual_best_and_callgraph(self):
        A = xisa_match.Side({1: 10, 2: 20, 3: 5}, {1: {0x1111, 0x2222}, 2: {0x3333}, 3: set()},
                            {1: {"rank"}, 2: set(), 3: set()}, {1: [3], 2: [], 3: []})
        P = xisa_match.Side({10: 12, 20: 22, 30: 6}, {10: {0x1111, 0x2222}, 20: {0x3333, 0x4444}, 30: set()},
                            {10: {"rank"}, 20: set(), 30: set()}, {10: [30], 20: [], 30: []})
        scores = xisa_match.score_all(A, P, ratio=1.1, min_score=0.1)
        pairs = xisa_match.assign(scores, A, P, anchors={})
        self.assertEqual(pairs[1][0], 10)
        self.assertEqual(pairs[2][0], 20)
        self.assertEqual(pairs[3], (30, "callgraph", 0.0))

    def test_anchor_wins(self):
        A = xisa_match.Side({1: 10}, {1: {0x1111}}, {1: set()}, {1: []})
        P = xisa_match.Side({10: 10, 11: 10}, {10: {0x1111}, 11: set()}, {10: set(), 11: set()}, {10: [], 11: []})
        pairs = xisa_match.assign(xisa_match.score_all(A, P, 1.0, 0.1), A, P, anchors={1: 11})
        self.assertEqual(pairs[1], (11, "anchor", 1.0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
