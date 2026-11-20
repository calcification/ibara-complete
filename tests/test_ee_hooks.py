#!/usr/bin/env python3
"""Offline tests for injected EE hook builds (scripts/build_ee_hooks.py). No game data needed.

Toolchain-dependent tests are skipped when mips-linux-gnu-gcc is absent.
"""
from __future__ import annotations

import importlib.util
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_ee_hooks", ROOT / "scripts/build_ee_hooks.py")
hooks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hooks)
pn = hooks.build_pnach


class EncodingTests(unittest.TestCase):
    def test_jal_encoding_matches_retail_site_preimage(self):
        # 0x0012E62C is documented (phase09) as `jal 0x0012AC60`.
        self.assertEqual(hooks.jal(0x0012AC60), 0x0C04AB18)
        for h in hooks.HOOKS.values():
            for _site, orig, _entry in h["sites"]:
                self.assertEqual(orig >> 26, 0x03, "hook sites must be jal instructions")

    def test_unaligned_jal_rejected(self):
        with self.assertRaises(AssertionError):
            hooks.jal(0x000C0002)

    def test_cave_below_elf_and_above_kernel(self):
        self.assertGreaterEqual(hooks.CAVE_BASE, 0x00080000)
        self.assertLessEqual(hooks.CAVE_END, pn.ELF_BASE)

    def test_pending_facts_block_xtc(self):
        self.assertTrue(hooks.pending(hooks.HOOKS["bl_xtc"]))
        self.assertEqual(hooks.pending(hooks.HOOKS["h00_smoke"]), [])

    def test_every_requirement_is_a_known_fact(self):
        for h in hooks.HOOKS.values():
            for r in h["requires"] + h["establishes"]:
                self.assertIn(r, hooks.FACTS)

    def test_default_pnach_bound_unchanged(self):
        txt = pn.HEADER + "\n[X]\npatch=0,EE,000C0000,word,00000000\n"
        with self.assertRaises(AssertionError):
            pn.check_pnach(txt)
        self.assertEqual(pn.check_pnach(txt, min_addr=hooks.CAVE_BASE)["writes"], 1)

    def test_check_ram_detects_foreign_words(self):
        built = {"size": 16, "words": [(2, hooks.CAVE_BASE, 1)]}
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "eeMemory.bin"
            ram = bytearray(32 * 1024 * 1024)
            struct.pack_into("<I", ram, hooks.CAVE_BASE, 1)
            p.write_bytes(ram)
            self.assertEqual(hooks.check_ram(p, built), 1)
            struct.pack_into("<I", ram, hooks.CAVE_BASE + 8, 0xDEAD)
            p.write_bytes(ram)
            with self.assertRaises(AssertionError):
                hooks.check_ram(p, built)


@unittest.skipUnless(hooks.have_toolchain(), "mips-linux-gnu toolchain not installed")
class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.built = {k: hooks.build_hook(k, Path(cls.tmp.name)) for k in hooks.HOOKS}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_images_fit_cave(self):
        for b in self.built.values():
            self.assertLessEqual(hooks.CAVE_BASE + b["size"], hooks.CAVE_END)
            for _p, addr, _v in b["words"]:
                self.assertTrue(hooks.CAVE_BASE <= addr < hooks.CAVE_END)

    def test_h00_header_is_once_only_and_magic(self):
        w = {a: (p, v) for p, a, v in self.built["h00_smoke"]["words"]}
        self.assertEqual(w[hooks.CAVE_BASE], (0, 0x58434249))
        self.assertEqual(w[hooks.CAVE_BASE + 8][0], 0, "mutable counter must not be rewritten each vsync")

    def test_stub_preserves_128bit_registers(self):
        b = self.built["h00_smoke"]
        entry = b["syms"]["h00_entry"]
        code = {a: v for _p, a, v in b["words"]}
        sq = [code[entry + 4 + 4 * i] for i in range(10)]
        self.assertTrue(all(v >> 26 == 0x1F for v in sq), "expected sq (opcode 0x1F) saves")
        self.assertIn(hooks.jal(0x0012AC60), code.values(), "stub must call the retail routine")

    def test_site_points_at_stub(self):
        b = self.built["h00_smoke"]
        site, orig, new = b["sites"][0]
        self.assertEqual((site, orig), (0x0012E62C, 0x0C04AB18))
        self.assertEqual(new, hooks.jal(b["syms"]["h00_entry"]))

    def test_generated_profile_is_valid(self):
        txt = pn.HEADER + hooks.pnach_group(hooks.HOOKS["h00_smoke"], self.built["h00_smoke"])
        stats = pn.check_pnach(txt, min_addr=hooks.CAVE_BASE)
        self.assertEqual(stats["groups"], 1)

    def test_committed_profile_matches_build(self):
        path = ROOT / "pnach/hooks/h00_smoke" / pn.NAME
        expected = hooks.pnach_group(hooks.HOOKS["h00_smoke"], self.built["h00_smoke"])
        self.assertIn(expected, path.read_text(encoding="utf-8"),
                      "pnach/hooks is stale: run python3 scripts/build_ee_hooks.py")

    def test_xtc_not_emitted(self):
        self.assertFalse((ROOT / "pnach/hooks/bl_xtc" / pn.NAME).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
