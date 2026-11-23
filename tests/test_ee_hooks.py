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

    def test_pending_facts_block_emission(self):
        self.assertEqual(hooks.pending(hooks.HOOKS["h00_smoke"]), [])
        self.assertEqual(hooks.pending(hooks.HOOKS["bl_xtc"]), [])
        hooks.FACTS["_synthetic"] = "pending"
        try:
            self.assertEqual(hooks.pending({"requires": ["player_score", "_synthetic"]}), ["_synthetic"])
        finally:
            del hooks.FACTS["_synthetic"]

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

    def test_bl_mode_is_bake_only_and_hooks_verified_sites(self):
        h = hooks.HOOKS["bl_mode"]
        self.assertTrue(h.get("bake_only"))
        self.assertFalse((ROOT / "pnach/hooks/bl_mode").exists(), "bl_mode must never be a PNACH (Exit reloads the disc)")
        sites = {site: orig for site, orig, _e in h["sites"]}
        self.assertEqual(sites[0x001CA7F0], hooks.jal(0x001370E0))   # Exit sound call
        self.assertEqual(sites[0x0012C394], hooks.jal(0x0012C0E0))   # per-frame score print (Arcade)
        self.assertEqual(sites[0x0012C3BC], hooks.jal(0x0012C0E0))   # per-frame score print (Arrange)
        patches = {a: (o, n) for a, o, n in h["patches"]}
        self.assertEqual(patches[0x0012EE70], (0x14800046, 0x10000046))  # option pickup -> stock path
        self.assertEqual(len([a for a, (o, n) in patches.items() if o == 0x8F879254 and n == 0x24070001]), 16)
        b = hooks.build_hook("bl_mode", Path(self.tmp.name), hooks.BAKE_BASE, hooks.BAKE_END)
        self.assertLessEqual(hooks.BAKE_BASE + b["size"], hooks.BAKE_END)
        self.assertEqual(len(b["sites"]), len(h["sites"]) + len(h["patches"]) + len(h["jumps"]) + len(h["patches_extra"])
                         + len(h["sym_patches"]))
        addrs = [site for site, _o, _n in b["sites"]]
        self.assertEqual(len(addrs), len(set(addrs)), "two patches on one word")
        jumps = {site: new for site, _o, new in b["sites"] if site == 0x00122120}
        self.assertEqual(jumps[0x00122120], 0x08000000 | (b["syms"]["bl_fire_timer"] >> 2) & 0x03FFFFFF)

    def test_prebuilt_bl_mode_matches_sources(self):
        import json
        b = hooks.build_hook("bl_mode", Path(self.tmp.name), hooks.BAKE_BASE, hooks.BAKE_END)
        committed = json.loads((ROOT / "ps2/prebuilt/bl_mode.json").read_text())
        self.assertEqual(hooks.export_bake(b), committed,
                         "ps2/prebuilt/bl_mode.json is stale: run python3 scripts/build_ee_hooks.py")

    def test_video_hook_is_leaf_safe(self):
        import re
        b = hooks.build_hook("video", Path(self.tmp.name), hooks.BAKE_BASE, hooks.BAKE_END)
        # HOOK_AFTER_LEAF does not preserve callee-saved registers: the hook code must not touch them.
        uses = [l for l in b["listing"].splitlines() if re.search(r"\t.*\b(s[0-7]|s8|fp)\b", l)]
        self.assertEqual(uses, [], "video hook uses callee-saved registers; it needs the full HOOK_AFTER stub")
        # (The frontend executable no longer has to fit its retail extent: the launcher builder moves it to free
        # disc space when it grows, research/phase04/build_menu_probe.py.)
        self.assertLessEqual(hooks.BAKE_BASE + b["size"], hooks.BAKE_END)
        for site in hooks.RANK_OPTION_SITES | hooks.PRACTICE_MODE_SITES:
            self.assertIn(site, {a for a, _o, _n in b["sites"]})
        h = hooks.HOOKS["bl_mode"]
        self.assertIn((hooks.VIDEO_SITE, 0x0C043920, "video_entry"), h["sites"])

    def test_instant_kuro_image(self):
        import re
        b = hooks.build_hook("kuro", Path(self.tmp.name), hooks.BAKE_BASE, hooks.BAKE_END)
        self.assertLessEqual(hooks.BAKE_BASE + b["size"], hooks.BAKE_END)
        # Everything reachable from the leaf per-frame stub or from menu-code patches uses temporaries only.
        leaf = {"frame_hook", "kuro_frame", "kuro_set", "isolate_config", "isolate_practice", "kuro_enter", "kuro_leave", "kuro_enter_entry",
                "kuro_leave_entry", "xtc_reset", "video_frame", "video_apply", "fix_one_env", "fix_full_frame_env",
                "opt_set", "cfg_value",
                "cfg_toggle", "arr_practice", "cfg_accept_entry", "prac_start", "prac_exit_state", "arr_accept_entry",
                "hdr_state", "bomb_d_kind", "frontend_rank_bar", "bl_rank_bar", "bl_rank_bar_off", "sel_menu", "sel_start_stub",
                "sel_layers_stub", "sel_begin", "sel_pause", "kuro_weapon_bar", "noir_practice_wrap"}
        cur, bad = None, []
        for line in b["listing"].splitlines():
            m = re.match(r"^[0-9a-f]+ <(\w+)>:", line)
            if m:
                cur = m.group(1)
            elif cur in leaf and re.search(r"\t.*\b(s[0-7]|s8|fp)\b", line):
                bad.append(line)
        self.assertEqual(bad, [])
        # n32 frames: every stack adjustment is a multiple of 16 (the game and the kernel's thread switch spill
        # 128-bit registers with sq / lq relative to sp, which an 8-byte-aligned o32 frame broke).
        frames = [int(x) for x in re.findall(r"\taddiu\tsp,sp,(-?\d+)", b["listing"])]
        self.assertTrue(frames)
        self.assertEqual([f for f in frames if f % 16], [])
        # ship_popup_tab stands in for the retail `lui s3`: s3 is the only saved register it touches.
        body = b["listing"].split("<ship_popup_tab>:")[1].split("\n\n")[0]
        self.assertEqual(set(re.findall(r"\b(s[0-8]|fp)\b", body)), {"s3"})
        # The runtime table contains KURO's gameplay words, with no overlap with the static edits.
        words = {a: v for _p, a, v in b["words"]}
        tab, n = words[b["syms"]["kuro_tab"]], words[b["syms"]["kuro_tab_n"]]
        rows = [(words[tab + 12 * i], words[tab + 12 * i + 4], words[tab + 12 * i + 8]) for i in range(n)]
        dynamic = hooks.HOOKS["kuro"]["dynamic"]
        self.assertEqual(n, sum(len(group) for group in dynamic.values()))
        addrs = [a for a, _o, _n in rows]
        self.assertEqual(len(addrs), len(set(addrs)))
        self.assertFalse(set(addrs) & {a for a, _o, _n in b["sites"]})
        self.assertNotIn(0x001CA7F0, addrs)
        by_site = {site: (original, replacement) for site, original, replacement in rows}
        self.assertEqual(by_site[0x002A8E40], (0xD0000003, 0x70700003))  # Arcade header UV, Noir while active
        self.assertEqual(by_site[0x002A903C], (0x00301CA0, 0x00301C50))  # PLAY DATA becomes EXIT
        self.assertEqual(by_site[0x001CB36C], (0x10620042, 0x10620005))  # row 3 confirms EXIT
        self.assertEqual(by_site[0x001CB1AC], (0x14430010, 0x10000010))  # bypass shared slot screen
        self.assertEqual(by_site[0x002A90E0], (0x00301D50, b["syms"]["noir_start_help"]))
        self.assertEqual(by_site[0x00113610], (hooks.jal(0x0013D580), 0x0000102D))
        for site in (0x001155A8, 0x0012CEC0):
            self.assertEqual(by_site[site], (hooks.jal(0x0013DE90), 0))
        self.assertEqual(by_site[0x001285EC], (0x106000D0, 0))
        self.assertEqual(by_site[0x0012E434], (hooks.jal(0x001285C0), hooks.jal(b["syms"]["kuro_weapon_bar"])))
        self.assertEqual(by_site[0x0012C3E0], (0x24A50001, 0x24A50003))
        self.assertEqual(by_site[0x0012C604], (0x02E21021, 0x02E21026))  # Noir P2 join/continue stays in ship IDs 0-7
        self.assertEqual(by_site[0x00337EA0], (0, 2))
        self.assertEqual(by_site[0x00337EA8], (4, 6))
        for site in (0x0011536C, 0x0012C978, 0x0012C990):
            self.assertEqual(by_site[site], (0x24050004, 0x24050005))
        self.assertFalse({0x0012C394, 0x0012C3BC} & set(by_site))  # native score calls, no fixed XTC text
        static = {site: (original, replacement) for site, original, replacement in b["sites"]}
        self.assertEqual(static[0x0012CF2C], (0x0000302D, 0x24060002))
        self.assertEqual(static[0x0012C31C], (0x24030002, 0x24030004))
        self.assertEqual(by_site[0x0012E1AC], (hooks.jal(0x0012C220), hooks.jal(b["syms"]["sel_pause"])))
        self.assertTrue(all(o != k for _a, o, k in rows))

    def test_bake_keeps_program_headers_after_elf_header(self):
        # synthetic retail-shaped ELF: phdrs at 0x34, one PT_LOAD at file 0x80 / vaddr 0x00100000
        body = bytearray(0x30000)
        struct.pack_into("<I", body, 0x0012E62C - 0x00100000, 0x0C04AB18)
        elf = bytearray(0x80) + body
        elf[:7] = b"\x7fELF\x01\x01\x01"
        struct.pack_into("<HHIIIIIHHHHHH", elf, 16, 2, 8, 1, 0x00100008, 0x34, 0, 0, 52, 32, 1, 40, 0, 0)
        struct.pack_into("<8I", elf, 0x34, 1, 0x80, 0x00100000, 0x00100000, len(body), len(body), 7, 0x80)
        b = hooks.build_hook("bl_xtc", Path(self.tmp.name), hooks.BAKE_BASE, hooks.BAKE_END)
        out = hooks.bake_elf(bytes(elf), b)
        self.assertEqual(struct.unpack_from("<I", out, 0x1C)[0], 0x34)
        self.assertEqual(struct.unpack_from("<H", out, 0x2C)[0], 2)
        ph = [struct.unpack_from("<8I", out, 0x34 + 32 * i) for i in range(2)]
        self.assertEqual(ph[0][1], 0x100)
        self.assertEqual((ph[1][2], ph[1][1] % 16), (hooks.BAKE_BASE, 0))
        self.assertEqual(out[ph[1][1]:ph[1][1] + 4], struct.pack("<I", 0x31435458))
        site = struct.unpack_from("<I", out, 0x100 + 0x0012E62C - 0x00100000)[0]
        self.assertEqual(site, hooks.jal(b["syms"]["xtc_entry"]))
        self.assertGreaterEqual(b["syms"]["xtc_entry"], hooks.BAKE_BASE)

    def test_xtc_state_at_cave_base_and_profile_current(self):
        b = self.built["bl_xtc"]
        self.assertEqual(b["syms"]["xtc"], hooks.CAVE_BASE)
        w = {a: (p, v) for p, a, v in b["words"]}
        self.assertEqual(w[hooks.CAVE_BASE], (0, 0x31435458))
        path = ROOT / "pnach/hooks/bl_xtc" / pn.NAME
        self.assertIn(hooks.pnach_group(hooks.HOOKS["bl_xtc"], b), path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
