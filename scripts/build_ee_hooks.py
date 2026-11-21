#!/usr/bin/env python3
"""Build injected EE hook code for Ibara (SLPM-66301, CRC 420C7FAB) into PCSX2 PNACH profiles.

Pipeline: C/asm in ps2/hooks -> mips-linux-gnu-gcc (-march=r5900, o32, soft-float, no PIC, -G0)
-> linked at the code cave -> PNACH words. Hook sites are retail `jal` words replaced by `jal stub`;
stubs (ps2/hooks/stub.S) call the retail routine first, then our C, preserving 128-bit registers.

Safety rules (fail closed):
* every hook site's original word is listed and checked against the clean ELF when --elf is given;
* a hook whose `requires` names a RUNTIME_PENDING fact is never emitted as a PNACH group (build-only);
* the image must fit inside the cave; --check-ram verifies the cave is zero in a PCSX2 eeMemory dump.

    python3 scripts/build_ee_hooks.py                 # build all, write pnach/hooks/<hook>/
    python3 scripts/build_ee_hooks.py --elf SLPM_663.01   # also verify retail preimages
    python3 scripts/build_ee_hooks.py --check-ram eeMemory.bin
"""
from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_pnach  # noqa: E402

PS2 = ROOT / "ps2"
CROSS = "mips-linux-gnu-"
CFLAGS = ["-march=r5900", "-EL", "-mabi=32", "-msoft-float", "-mno-abicalls", "-fno-pic", "-G0", "-O2",
          "-ffreestanding", "-fno-builtin", "-nostdlib", "-fno-common", "-Wall", "-Werror",
          "-Wa,-mfix-r5900", "-I", str(PS2 / "include")]
CAVE_BASE = 0x000C0000  # PNACH profiles: written after boot (C00/K01 runtime-verified)
CAVE_END = 0x00100000
# Baked ELF payloads: a PT_LOAD at 0x000C0000 kills PCSX2 v1.7.4000 during LoadExecPS2 (bisected
# 2026-11-20), so they live in high RAM that stayed zero in ~160 savestates (title, menus, demos,
# Arcade stages 1-2): 0x01EFE100-0x01FFDA00, below the stack. Runtime-observed only.
BAKE_BASE = 0x01F00000
BAKE_END = 0x01F10000

# Facts a hook may depend on. Only "verified" facts allow a PNACH group to be emitted.
FACTS = {
    "site_frame_collide": "verified",   # 0x0012E62C: jal 0x0012AC60, phase09 static
    "player_score": "verified",         # 0x0044C600, phase08 static
    "rank_inv": "verified",             # 0x00338EB4, phase07 static
    # static: no game code builds an address in 0x000C0000-0x000FFFFF (81 lui hits there are fixed-point
    # constants; the one stack, 0x00081FC0 set at 0x00215748, grows down away from it). C00 confirms at runtime.
    "cave_free": "verified",
    "bullet_layout": "verified",        # 0x00462F40 x256, +0 0x10000000, +0x28/+0x2C: 0x0012A680 static
    "player_xy": "verified",            # +0x10/+0x14, same space as bullets: 0x0012A680 static
    "pad_held": "verified",             # +0x24C held, shot 0x10: 0x0012DA3C / 0x0013B2F0 static
}

# Sources behind HOOK_AFTER_LEAF stubs (no callee-saved register preservation): keep the compiler off s0-s7/fp.
LEAF_SOURCES = {"video.c", "options.c", "kuro.c"}
LEAF_CFLAGS = [f"-ffixed-s{i}" for i in range(8)] + ["-ffixed-fp"]

VIDEO_SITE = 0x0010BC78  # main loop: jal 0x0010E480 (per-frame display output, every screen)
# start-up settings loads: jal 0x0010FE20 (store the applied screen mode) -> video_apply (carried screen mode)
VIDEO_APPLY_SITES = [(0x001D1B24, 0x0C043F88, "video_apply"), (0x001D3CD4, 0x0C043F88, "video_apply")]
VIDEO_SITES = {VIDEO_SITE} | {a for a, _o, _e in VIDEO_APPLY_SITES}

# ARCADE MODE > CONFIG gets a RANK GAUGE ON/OFF row (ps2/hooks/options.c; research/phase17). Same addresses in
# the launcher and KURO (KURO is a copy of the retail executable). (address, original, kind, target[, addend]):
# kind word/jal/j/hi/lo takes a symbol of our image or a number; raw is a plain new word.
RANK_OPTION_PATCHES = [
    # label table 0x002A9220: row 6 RANK GAUGE, rows 7-9 FIGHTER TYPE, KEY CONFIG, EXIT (slot 9 was spare)
    (0x002A9238, 0x00301CC0, "word", "rank_label"),
    (0x002A923C, 0x00301CE0, "word", 0x00301CC0),
    (0x002A9240, 0x00301C50, "word", 0x00301CE0),
    (0x002A9244, 0x00000000, "word", 0x00301C50),
    # 10 rows: draw loop `slti v0,s2,9`, cursor down `slti at,v0,9`, cursor up wrap `li v0,8`
    (0x001CBFE4, 0x2A420009, "raw", 0x2A42000A),
    (0x001CC170, 0x28410009, "raw", 0x2841000A),
    (0x001CC1FC, 0x24020008, "raw", 0x24020009),
    # accept dispatcher: FIGHTER TYPE / KEY CONFIG / EXIT handlers now answer rows 7 / 8 / 9 ...
    (0x001CC270, 0x24020006, "raw", 0x24020007),
    (0x001CC280, 0x24020007, "raw", 0x24020008),
    (0x001CC290, 0x24020008, "raw", 0x24020009),
    # ... and the "no handler" exit goes through the unreachable word 0x001CC4DC to cfg_accept_entry (row 6 toggles)
    (0x001CC294, 0x1462FEE2, "raw", 0x14620091),
    (0x001CC4DC, 0x00000000, "j", "cfg_accept_entry"),
    # value column: the CONTINUE lookup (0x001CBF70-0x001CBF8C) becomes s5 = cfg_value(row, continue, s5)
    (0x001CBF70, 0x24020005, "raw", 0x93858EFC),   # lbu a1, -28932(gp)
    (0x001CBF74, 0x16420006, "raw", 0x02402021),   # move a0, s2
    (0x001CBF78, 0x00000000, "jal", "cfg_value"),
    (0x001CBF7C, 0x93838EFC, "raw", 0x02A03021),   # move a2, s5 (delay slot)
    (0x001CBF80, 0x27828C40, "raw", 0x0040A821),   # move s5, v0
    (0x001CBF84, 0x00031880, "raw", 0x00000000),
    (0x001CBF88, 0x00431021, "raw", 0x00000000),
    (0x001CBF8C, 0x8C550000, "raw", 0x00000000),
    # returning from FIGHTER TYPE (two exits) and KEY CONFIG puts the cursor back on their new rows 7 / 8
    (0x001CC5E4, 0x00000000, "raw", 0x24030007),   # li v1, 7 (bne delay slot; v1 dead on the other path)
    (0x001CC5F4, 0xAF82979C, "raw", 0xAF83979C),   # sw v1, -26724(gp)
    (0x001CC68C, 0x00000000, "raw", 0x24030007),
    (0x001CC69C, 0xAF82979C, "raw", 0xAF83979C),
    (0x001CA08C, 0x24020007, "raw", 0x24020008),   # KEY CONFIG: li v0, 7 -> 8
    # help text table 0x002A9310 (9 rows, no room) -> cfg_desc (10 rows)
    (0x001CBFFC, 0x3C02002B, "hi", "cfg_desc"),
    (0x001CC004, 0x24429310, "lo", "cfg_desc"),
    (0x001CC020, 0x3C02002B, "hi", "cfg_desc", 4),
    (0x001CC024, 0x24429314, "lo", "cfg_desc", 4),
]

# ARRANGE MODE gets a PRACTICE row like ARCADE MODE's (ps2/hooks/options.c): GAME START, PRACTICE, CONFIG, EXIT.
PRACTICE_MODE_PATCHES = [
    # label table 0x002A9048: row 1 PRACTICE (retail string), rows 2-3 CONFIG, EXIT (slot 3 was spare)
    (0x002A904C, 0x00301C78, "word", 0x00301C68),
    (0x002A9050, 0x00301C50, "word", 0x00301C78),
    (0x002A9054, 0x00000000, "word", 0x00301C50),
    # ARRANGE CONFIG's title reads the CONFIG slot (0x002A904C, now PRACTICE): `lw a0,-28596(v0)` -> -28592
    (0x001CCDB8, 0x8C44904C, "raw", 0x8C449050),
    # leaving ARRANGE CONFIG (cancel 0x001CD008, EXIT 0x001CD0B4) returns to its new row 2: `li v0,1` -> 2
    (0x001CD008, 0x24020001, "raw", 0x24020002),
    (0x001CD0B4, 0x24020001, "raw", 0x24020002),
    # 4 rows: draw loop `slti v0,s1,3`, cursor down `slti at,v0,3`; the cursor-up wrap stores a0 (2 from the state
    # dispatcher, reused as the last row): `li a0,3` in the delay slot of the state's first branch 0x001CCA7C
    (0x001CCB50, 0x2A220003, "raw", 0x2A220004),
    (0x001CCA98, 0x28410003, "raw", 0x28410004),
    (0x001CCA80, 0x00000000, "raw", 0x24040003),
    # accept dispatcher: CONFIG / EXIT answer rows 2 / 3; row 1 goes through the unreachable word 0x001CC9B4 to
    # arr_accept_entry (opens the practice menu)
    (0x001CCC04, 0x24020001, "raw", 0x24020002),
    (0x001CCC14, 0x24020002, "raw", 0x24020003),
    (0x001CCC18, 0x1462FFB2, "raw", 0x1462FF66),
    (0x001CC9B4, 0x00000000, "j", "arr_accept_entry"),
    # help text: the 3-row table 0x002A93F0 -> arr_desc (4 rows)
    (0x001CCB60, 0x3C02002B, "hi", "arr_desc"),
    (0x001CCB64, 0x244293F0, "lo", "arr_desc"),
    (0x001CCB84, 0x3C02002B, "hi", "arr_desc", 4),
    (0x001CCB88, 0x244293F4, "lo", "arr_desc", 4),
    # practice start: `sw zero, -28076(gp)` (Arrange flag off) -> jal prac_start (Arrange when opened from ARRANGE)
    (0x001CB3E0, 0xAF809254, "jal", "prac_start"),
    # leaving the practice menu (cancel 0x001CB2C8, EXIT 0x001CB384): `li v0, 2` (ARCADE MODE) -> jal prac_exit_state
    # (its delay slot `li a0, 76` is the sound argument; the PRACTICE row 1 is the return row in both menus)
    (0x001CB2C8, 0x24020002, "jal", "prac_exit_state"),
    (0x001CB384, 0x24020002, "jal", "prac_exit_state"),
    # menu header (0x001C9570 `lw v1, -28056(gp)`, delay slot `li v0, 1`): ARRANGE MODE over its practice menu
    (0x001C9570, 0x8F839268, "jal", "hdr_state"),
]
PRACTICE_MODE_SITES = {a for a, *_ in PRACTICE_MODE_PATCHES}
RANK_OPTION_SITES = {a for a, *_ in RANK_OPTION_PATCHES}
BL_SYM_PATCHES = [(0x001342D8, 0x9064026A, "jal", "pod_mode_entry")]

HOOKS = {
    "h00_smoke": {
        "test_id": "C00",
        "title": "HOOK / code-injection smoke test (frame counter at 000C0000)",
        "description": ("Redirects the per-frame collision call through injected code that still calls the "
                        "retail routine, then counts frames. Watch 000C0008 increase in the debugger. "
                        "The game must play exactly as P00. RUNTIME UNTESTED."),
        "sources": ["h00_smoke.c"],
        "stubs": [("h00_entry", 0x0012AC60, "h00_frame")],
        "sites": [(0x0012E62C, 0x0C04AB18, "h00_entry")],
        # cave_free is what this test establishes, so it is the one pending fact allowed here.
        "requires": ["site_frame_collide", "player_score"],
        "establishes": ["cave_free"],
    },
    "bl_mode": {
        "test_id": "K03",
        "title": "BLACK LABEL build: XTC + Exit returns to the launcher",
        "description": "Baked into the sixth-entry executable only (never a PNACH: Exit would reload the disc).",
        "sources": ["xtc.c", "xtc_hud.c", "bl_return.c", "spawnlog.c", "bl_enemy.c", "bl_player.c", "video.c",
                    "options.c"],
        "stubs": [("xtc_entry", 0x0012AC60, "xtc_frame"), ("ret_entry", 0x001370E0, "bl_return_to_launcher"),
                  ("hud_entry", 0x0012C0E0, "xtc_hud"), ("video_entry", 0x0010E480, "video_frame", "leaf")],
        # The video site (main-loop display call) is only kept with video profile "auto" (bake_payload).
        "sites": [(0x0012E62C, 0x0C04AB18, "xtc_entry"), (0x001CA7F0, 0x0C04DC38, "ret_entry"),
                  (0x0012C394, 0x0C04B038, "hud_entry"), (0x0012C3BC, 0x0C04B038, "hud_entry"),
                  (VIDEO_SITE, 0x0C043920, "video_entry")] + VIDEO_APPLY_SITES,
        "requires": ["site_frame_collide", "player_score", "rank_inv", "cave_free", "bullet_layout",
                     "player_xy", "pad_held"],
        "establishes": [],
        "bake_only": True,
        # BL weapon stock in the Arcade game (static, 2026-11-20): option pickups take Arrange's stock path
        # (0x0012EE70 bnez -> b), the change button runs in Arcade (0x001398D8 beqz -> nop), and Arrange's
        # formation change (pressed 0x80) stays off (0x001399A0 andi 0x80 -> andi 0).
        "patches": [(0x0012EE70, 0x14800046, 0x10000046), (0x001398D8, 0x1040005C, 0x00000000),
                    (0x001399A0, 0x30420080, 0x30420000)]
        # Input mapper: per-button action lookup uses the Arrange config (mode index 1), whose button 0 is
        # the weapon change (action 3 -> bit 0x40), BL's fourth button. 8 buttons x 2 players.
        + [(a, 0x8F879254, 0x24070001) for a in (
            0x00112ED8, 0x00112F1C, 0x00112F60, 0x00112FA4, 0x00112FE8, 0x0011302C, 0x00113070, 0x001130B4,
            0x00113128, 0x0011316C, 0x001131B0, 0x001131F4, 0x00113238, 0x0011327C, 0x001132C0, 0x00113304)]
        # BL shot levels (F5): small P also raises level 5 -> 6 (per-level jump table 0x002FCF10 entry 5 goes to
        # the raise path 0x0012FBA8 instead of the bonus path 0x0012FC24), and the 5-in-a-row full-power
        # secret is gone (0x0012FB78 bnez -> nop). Level k needs k + 1 small P (table 0x00337F40).
        + [(0x002FCF24, 0x0012FC24, 0x0012FBA8), (0x0012FB78, 0x14A00038, 0x00000000)]
        # BL rank (F8, MAME oracle Phase 13): a bomb-fragment pickup makes rank harder by 0x40000 (Arrange's
        # value; PS2 Arcade uses 0x2000): Arcade path of the type-2 handler, 0x0012F4A8 li a0,0x2000 -> lui a0,4.
        + [(0x0012F4A8, 0x24042000, 0x3C040004)]
        # BL medal and rose rank rules = Arrange's (MAME Phase 13): medal harder by level x 0x20000
        # (0x0012F7FC bnez -> b), rose easier by table[level] x 1024 (0x0012F6C4 bnez -> b). Rank branches only;
        # both rejoin the Arcade code, so scoring is unchanged.
        + [(0x0012F7FC, 0x1440000B, 0x1000000B), (0x0012F6C4, 0x1440000A, 0x1000000A)]
        # BL enemy HP (G6, BL 0C0A9AE0 vs arcade 0C0A1530 / PS2 0x00126C10): BL scales a new part's HP by the
        # stage, not by rank: hp = base + base * stage / 16, stage = BL's stage byte (2..7 for stages 1..6).
        # PS2 Arrange already computes that form from $gp-28248 (a stage *id*); the PS2 scene counter
        # $gp-28244 (0x00338E9C) is 1 at the opening, 2 at stage 1, 3 at stage 2 ... = BL's byte (savestates).
        # So: Arcade takes the Arrange formula (0x00126C4C beqz -> nop), reading the counter (0x00126C54).
        + [(0x00126C4C, 0x1060000C, 0x00000000), (0x00126C54, 0x938391A8, 0x938391AC)],
        # BL enemy fire timer (BL 0C0BC1B0 / arcade 0C0A9E40 / PS2 0x00122120): `j bl_fire_timer` at the
        # retail entry (its delay slot `andi v0,v0,0x100` is harmless); see ps2/hooks/bl_enemy.c.
        # BL held fire (Phase 16, per-frame shot logs): holding shot fires every 2 frames, capped only by the
        # on-screen shot count; PS2 Arcade keeps the 8-frame interval (+0x262). PS2's shooter 0x0013B2F0 already has
        # BL's rule on its Arrange path (held >= 8 frames -> interval 2); the held-frame path is taken for Arcade too
        # (0x0013B310 lw v1,$gp-28076 -> li v1,1). The new-press path (Arcade rank on press) is unchanged.
        "patches_extra": [(0x0013B310, 0x8F839254, 0x24030001),
        # BL shot cap (Phase 16): BL's type-0 shot spawner (0C073830) allows 32 slots for one player (10 for two);
        # PS2's fire routine 0x0013ACC0 allows 32 in Arrange but halves it to 16 in Arcade (0x0013AD14
        # lw v0,$gp-28076 -> li v0,1 keeps 32). Per-frame logs: BL uses slots 0-31, PS2 Arcade only 0-15.
                          (0x0013AD14, 0x8F829254, 0x24020001)]
        # BL pods do not change rank when they fire (MAME rank-write log, research/phase13; BL pod routines
        # 0C078A70..0C078BC0 make no rank call). PS2's pod weapons call harder(n) per shot (n = 40, 20, 15, 75, 15,
        # 100, 50): `jal 0x00129DF0` -> nop (the delay slot only loads n). research/phase16.
        + [(a, 0x0C04A77C, 0x00000000) for a in (0x001330A4, 0x00133364, 0x0013370C, 0x001339AC, 0x00133BB8,
                                                   0x00133E84, 0x00134164)],
        "jumps": [(0x00122120, 0x8C820000, "bl_fire_timer")],
        "sym_patches": RANK_OPTION_PATCHES + PRACTICE_MODE_PATCHES + BL_SYM_PATCHES,
    },
    "video": {
        "test_id": "V01",
        "title": "VIDEO / Yoko interlaced, Tate 240p (frontend executable)",
        "description": "Baked into the launcher's frontend executable with video profile auto; see ps2/hooks/video.c.",
        "sources": ["video.c", "options.c"],
        "stubs": [("video_entry", 0x0010E480, "video_frame", "leaf")],
        "sites": [(VIDEO_SITE, 0x0C043920, "video_entry")] + VIDEO_APPLY_SITES,
        "requires": [],
        "establishes": [],
        "sym_patches": RANK_OPTION_PATCHES + PRACTICE_MODE_PATCHES,
        "bake_only": True,
    },
    "bl_xtc": {
        "test_id": "K01",
        "title": "BLACK LABEL / XTC graze counter (+10 per graze)",
        "description": ("Kuro BL graze: holding shot 5+ frames near enemy bullets adds 10 points per bullet. "
                        "State at 000C0000: magic XTC1, then per player quarters(s32)/timer(u16)/held(u8). "
                        "Run only after C00 passes. No HUD counter yet. RUNTIME UNTESTED."),
        "sources": ["xtc.c", "spawnlog.c"],
        "stubs": [("xtc_entry", 0x0012AC60, "xtc_frame")],
        "sites": [(0x0012E62C, 0x0C04AB18, "xtc_entry")],
        "requires": ["site_frame_collide", "player_score", "rank_inv", "cave_free", "bullet_layout",
                     "player_xy", "pad_held"],
        "establishes": [],
    },
}


def jal(target: int) -> int:
    if target & 3:
        raise AssertionError(f"unaligned jal target {target:08X}")
    return 0x0C000000 | ((target >> 2) & 0x03FFFFFF)


def have_toolchain() -> bool:
    return shutil.which(CROSS + "gcc") is not None and shutil.which(CROSS + "ld") is not None


def run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"{' '.join(cmd)}\n{p.stdout}{p.stderr}")
    return p.stdout


def read_elf_sections(path: Path) -> tuple[list[tuple[str, int, bytes, bool]], dict[str, int]]:
    """Return ([(name, addr, data, is_mutable)], symbols) from a little-endian ELF32."""
    data = path.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 1:
        raise AssertionError("expected ELF32 little-endian")
    e_shoff, = struct.unpack_from("<I", data, 0x20)
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", data, 0x2E)
    shdrs = [struct.unpack_from("<IIIIIIIIII", data, e_shoff + i * e_shentsize) for i in range(e_shnum)]
    shstr = shdrs[e_shstrndx]

    def name(off, tab):
        end = data.index(b"\0", tab[4] + off)
        return data[tab[4] + off:end].decode()

    secs, syms = [], {}
    strtab = None
    for sh in shdrs:
        n = name(sh[0], shstr)
        if n == ".strtab":
            strtab = sh
    for sh in shdrs:
        n = name(sh[0], shstr)
        sh_type, flags, addr, off, size = sh[1], sh[2], sh[3], sh[4], sh[5]
        if flags & 0x2 and size:  # SHF_ALLOC
            mutable = bool(flags & 0x1)  # SHF_WRITE
            blob = b"\0" * size if sh_type == 8 else data[off:off + size]  # SHT_NOBITS
            secs.append((n, addr, blob, mutable))
        if sh_type == 2 and strtab:  # SHT_SYMTAB
            for i in range(size // 16):
                st_name, st_value, _, _, _, _ = struct.unpack_from("<IIIBBH", data, off + i * 16)
                if st_name:
                    syms[name(st_name, strtab)] = st_value
    return secs, syms


# BL enemy part base HP (records differing from PS2), generated by tools/stage_compare/diff_part_tables.py.
_HP = ROOT / "ps2" / "bl_part_hp.json"
if _HP.exists():
    HOOKS["bl_mode"]["patches"] = HOOKS["bl_mode"]["patches"] + [
        (int(a, 16), int(p["orig"], 16), int(p["new"], 16)) for a, p in json.loads(_HP.read_text()).items()]

# Instant KURO (ps2/hooks/kuro.c): the frontend executable carries the whole image; the Black Label words of
# bl_mode (hook call sites, rule patches, part-HP tables) become a runtime table that kuro.c switches on entering and
# leaving KURO. Not in it: bl_mode's Exit-to-launcher hook (0x001CA7F0) and its video sites (static here).
KURO_PATCHES = [
    # Mode Select's KURO row: the dispatcher (research/phase04 DISPATCH 0x001D42A0: li v0,row; bne v1,v0,skip;
    # lui a0 (delay slot); addiu a0 ...; LoadExecPS2) -> its first word after the delay slot jumps to kuro_enter_entry
    (0x001D42AC, 0x248442D8, "j", "kuro_enter_entry"),
    # ARCADE MODE's way out (cancel 0x001CA958, EXIT 0x001CAAC4): `li v0,1` -> jal kuro_leave_entry, and the return
    # row `sw zero,-26724(gp)` -> `sw v1,-26724(gp)` (KURO's row when leaving KURO, else 0)
    (0x001CA958, 0x24020001, "jal", "kuro_leave_entry"),
    (0x001CA968, 0xAF80979C, "raw", 0xAF83979C),
    (0x001CAAC4, 0x24020001, "jal", "kuro_leave_entry"),
    (0x001CAAD4, 0xAF80979C, "raw", 0xAF83979C),
]
KURO_SITES = {a for a, *_ in KURO_PATCHES}
# Black Label ship kind and bombs (ps2/hooks/bl_ship.c; research/phase18), switched with KURO:
BL_SHIP_PATCHES = [
    # CONFIG > FIGHTER TYPE (state 7): 8 values (straight A-D, spread A-D) with our labels. The edit popup's list
    # (`lui s3` / `li s0,4` / `addiu s3`) comes from ship_popup_tab for the row being edited; the value column of
    # PLAYER 1 / PLAYER 2 from ship_tab_p1 / ship_tab_p2.
    (0x001C970C, 0x3C13002B, "jal", "ship_popup_tab"),
    (0x001C9710, 0x24100004, "raw", 0x24100008),
    (0x001C9714, 0x26739370, "raw", 0x00000000),
    (0x001C995C, 0x3C02002B, "hi", "ship_tab_p1"),
    (0x001C9960, 0x24429370, "lo", "ship_tab_p1"),
    (0x001C9980, 0x3C02002B, "hi", "ship_tab_p2"),
    (0x001C9984, 0x24429370, "lo", "ship_tab_p2"),
    # its help lines ([row * 8 + value * 2], 0x002A9380 / +4) from ship_help (24 entries)
    (0x001C9808, 0x3C02002B, "hi", "ship_help"),
    (0x001C980C, 0x24429380, "lo", "ship_help"),
    (0x001C9838, 0x3C02002B, "hi", "ship_help", 4),
    (0x001C9840, 0x24429384, "lo", "ship_help", 4),
    # player start: ship word = side * 4 + type -> side * 4 XOR value (values 4-7 = the other pilot's set)
    (0x001CE728, 0x00E51821, "raw", 0x00E51826),
    # type-D bomb (0x0011B460): pattern table and repeat count by ship kind instead of player side
    (0x0011B480, 0x8C790000, "jal", "bomb_d_kind"),
    (0x0011B4F4, 0x24CE0001, "raw", 0x01207021),
    # bomb trigger (0x0013B000): no rank change on bombing (Arcade's harder() calls skipped, as Arrange and BL)
    (0x0013B0C4, 0x10400053, "raw", 0x00000000),
    (0x0013B11C, 0x14400003, "raw", 0x10000003),
    (0x0013B258, 0x1440FFB4, "raw", 0x1000FFB4),
    (0x0013B274, 0x1040000C, "raw", 0x00000000),
]
HOOKS["kuro"] = {
    "test_id": "K20",
    "title": "Instant KURO: one executable, Black Label switched at runtime (frontend executable)",
    "description": "Baked into the launcher's frontend executable; see ps2/hooks/kuro.c.",
    "sources": ["video.c", "options.c", "kuro.c", "xtc.c", "xtc_hud.c", "spawnlog.c", "bl_enemy.c", "bl_player.c",
                "bl_ship.c"],
    "stubs": [("video_entry", 0x0010E480, "frame_hook", "leaf"), ("xtc_entry", 0x0012AC60, "xtc_frame"),
              ("hud_entry", 0x0012C0E0, "xtc_hud")],
    "sites": [(VIDEO_SITE, 0x0C043920, "video_entry")] + VIDEO_APPLY_SITES,
    "sym_patches": RANK_OPTION_PATCHES + PRACTICE_MODE_PATCHES + KURO_PATCHES,
    "dynamic": {
        "sites": [(0x0012E62C, 0x0C04AB18, "xtc_entry"), (0x0012C394, 0x0C04B038, "hud_entry"),
                  (0x0012C3BC, 0x0C04B038, "hud_entry")],
        "sym_patches": BL_SYM_PATCHES + BL_SHIP_PATCHES,
        "jumps": HOOKS["bl_mode"]["jumps"],
        "patches": HOOKS["bl_mode"]["patches"] + HOOKS["bl_mode"]["patches_extra"],
    },
    "requires": [],
    "establishes": [],
    "bake_only": True,
    "frontend": True,  # sites include words of the launcher builder's dispatcher (not in the retail executable)
}
KURO_EXPORTED_SYMS = ("kuro_row", "video_enabled", "kuro_tab", "kuro_tab_n")

EXTRA_DEFINES: list[str] = []  # --define NAME (test builds only; never for committed profiles)


def set_sym_word(built: dict, sym: str, value: int) -> None:
    """Change the initial value of one of our image's words (a symbol of the built image)."""
    addr = built["syms"][sym]
    for i, (place, a, _v) in enumerate(built["words"]):
        if a == addr:
            built["words"][i] = (place, a, value)
            return
    raise AssertionError(f"{sym} is not an image word")


def sym_patch_word(syms: dict, site: int, original_word: int, kind: str, target, add: int = 0) -> int:
    """New word for a sym_patches entry: word/raw value, jal/j to it, or the hi/lo half of its address."""
    value = (syms[target] if isinstance(target, str) else target) + add
    if kind == "word" or kind == "raw":
        return value
    if kind == "jal":
        return jal(value)
    if kind == "j":
        assert value % 4 == 0 and value >> 28 == site >> 28
        return 0x08000000 | (value >> 2) & 0x03FFFFFF
    if kind == "hi":
        return (original_word & 0xFFFF0000) | ((value + 0x8000) >> 16) & 0xFFFF
    if kind == "lo":
        return (original_word & 0xFFFF0000) | value & 0xFFFF
    raise AssertionError(f"unknown patch kind {kind}")


def build_hook(key: str, work: Path, base: int = CAVE_BASE, end_limit: int = CAVE_END) -> dict:
    h = HOOKS[key]
    objs = []
    stub_src = work / f"{key}_stubs.S"
    lines = [f'#include "{PS2 / "hooks" / "stub.S"}"']
    defsyms = []
    for entry, original, chook, *kind in h["stubs"]:
        sym = f"retail_{original:08X}"
        lines.append(f"{'HOOK_AFTER_LEAF' if kind == ['leaf'] else 'HOOK_AFTER'} {entry}, {sym}, {chook}")
        defsyms += ["--defsym", f"{sym}=0x{original:08X}"]
    stub_src.write_text("\n".join(lines) + "\n")
    for src in [stub_src] + [PS2 / "hooks" / s for s in h["sources"]]:
        obj = work / (src.stem + ".o")
        extra = LEAF_CFLAGS if src.name in LEAF_SOURCES else []
        run([CROSS + "gcc", *CFLAGS, *extra, *[f"-D{d}" for d in EXTRA_DEFINES], "-c", str(src), "-o", str(obj)])
        objs.append(str(obj))
    elf = work / f"{key}.elf"
    run([CROSS + "ld", "-EL", "-T", str(PS2 / "link.ld"), "--defsym", f"CAVE_BASE=0x{base:08X}",
         *defsyms, "-o", str(elf), *objs])
    secs, syms = read_elf_sections(elf)
    end = syms["__cave_end"]
    if not (base <= syms["__cave_start"] and end <= end_limit):
        raise AssertionError(f"{key}: image {syms['__cave_start']:08X}-{end:08X} outside cave")
    words = []  # (place, addr, value)
    for name, addr, blob, mutable in secs:
        blob = blob + b"\0" * (-len(blob) % 4)
        for i in range(0, len(blob), 4):
            words.append((0 if mutable else 2, addr + i, struct.unpack_from("<I", blob, i)[0]))
    sites = []
    for site, original_word, entry in h["sites"]:
        sites.append((site, original_word, jal(syms[entry])))
    for site, original_word, entry in h.get("jumps", []):  # plain `j` into a C leaf that returns to the caller
        assert syms[entry] % 4 == 0 and syms[entry] >> 28 == site >> 28
        sites.append((site, original_word, 0x08000000 | (syms[entry] >> 2) & 0x03FFFFFF))
    for site, original_word, kind, target, *add in h.get("sym_patches", []):
        sites.append((site, original_word, sym_patch_word(syms, site, original_word, kind, target, *add)))
    sites.extend(h.get("patches", []))
    sites.extend(h.get("patches_extra", []))  # plain word patches: same preimage check and application
    dyn = h.get("dynamic")
    if dyn:  # runtime-switched words: a (address, retail, new) table after the image (ps2/hooks/kuro.c)
        rows = [(a, o, jal(syms[e])) for a, o, e in dyn["sites"]]
        rows += [(a, o, 0x08000000 | (syms[e] >> 2) & 0x03FFFFFF) for a, o, e in dyn["jumps"]]
        rows += list(dyn["patches"])
        for a, o, kind, target, *add in dyn.get("sym_patches", []):
            rows.append((a, o, sym_patch_word(syms, a, o, kind, target, *add)))
        seen = {a for a, _o, _n in sites}
        clash = [f"{a:08X}" for a, _o, _n in rows if a in seen]
        if clash or len({a for a, _o, _n in rows}) != len(rows):
            raise AssertionError(f"{key}: runtime words overlap static sites or each other: {clash}")
        table = (end + 15) & ~15
        for i, (a, o, n) in enumerate(rows):
            words += [(0, table + 12 * i, a), (0, table + 12 * i + 4, o), (0, table + 12 * i + 8, n)]
        end = table + 12 * len(rows)
        if end > end_limit:
            raise AssertionError(f"{key}: runtime table ends at {end:08X}, past {end_limit:08X}")
        built_tmp = {"words": words, "syms": syms}
        set_sym_word(built_tmp, "kuro_tab", table)
        set_sym_word(built_tmp, "kuro_tab_n", len(rows))
    listing = run([CROSS + "objdump", "-d", "-m", "mips:5900", str(elf)])
    return {"key": key, "words": words, "sites": sites, "syms": syms, "size": end - base, "base": base, "listing": listing}


def pending(h: dict) -> list[str]:
    return [r for r in h["requires"] if FACTS[r] != "verified"]


def pnach_group(h: dict, built: dict) -> str:
    out = [f'[Ibara Complete\\{h["test_id"]} {h["title"]}]', f'description={h["description"]}',
           "author=Ibara Complete Research"]
    for place, addr, val in built["words"]:
        out.append(f"patch={place},EE,{addr:08X},word,{val:08X}")
    for site, _orig, new in built["sites"]:
        out.append(f"patch=2,EE,{site:08X},word,{new:08X}")
    return "\n".join(out) + "\n"


def verify_sites(elf: bytes, built: dict):
    for site, orig, _new in built["sites"]:
        off = site - build_pnach.ELF_BASE + build_pnach.ELF_FILE_OFFSET
        found, = struct.unpack_from("<I", elf, off)
        if found != orig:
            raise AssertionError(f"preimage mismatch @ {site:08X}: found {found:08X}, expected {orig:08X}")


def check_ram(path: Path, built: dict):
    ram = path.read_bytes()
    if len(ram) != 32 * 1024 * 1024:
        raise AssertionError("eeMemory dump must be exactly 32 MiB")
    lo, hi = CAVE_BASE, CAVE_BASE + built["size"]
    nz = [a for a in range(lo, hi, 4) if struct.unpack_from("<I", ram, a)[0]]
    ours = {a for _p, a, _v in built["words"]}
    foreign = [a for a in nz if a not in ours]
    if foreign:
        raise AssertionError(f"cave not free: {len(foreign)} non-zero words not written by us, first {foreign[0]:08X}")
    return len(nz)


def video_profile(name: str) -> list:
    """(address, original, new) video edits shared with the launcher builder (research/phase04)."""
    sys.path.insert(0, str(ROOT / "research" / "phase04"))
    sys.path.insert(0, str(ROOT / "research" / "phase03"))
    import build_menu_probe  # noqa: E402
    if name not in build_menu_probe.VIDEO_PROFILES:
        raise ValueError(f"unknown video profile {name}; choose from {sorted(build_menu_probe.VIDEO_PROFILES)}")
    return [tuple(e) for e in build_menu_probe.VIDEO_PROFILES[name]]


def bake_elf(retail: bytes, built: dict) -> bytes:
    """Copy of the retail ELF with the hook image as an extra PT_LOAD and the hook sites patched.

    For the sixth Mode Select entry (research/phase04/build_menu_probe.py --payload-elf): the original
    SLPM_663.01 stays untouched for Arcade/Arrange, and the copy runs with the hooks and no PNACH.
    The PS2 loader only reads the program headers right after the ELF header (a table moved to the end of
    the file killed PCSX2 during LoadExecPS2), so the table stays at 0x34 and all file data shifts by
    0x80 (the retail segment alignment) to make room; segment and section offsets are fixed up.
    Output is built locally from the user's own disc and must not be committed or distributed.
    """
    SHIFT = 0x80
    src = bytearray(retail)
    for site, orig, new in built["sites"]:
        off = site - build_pnach.ELF_BASE + build_pnach.ELF_FILE_OFFSET
        found, = struct.unpack_from("<I", src, off)
        if found != orig:
            raise AssertionError(f"bake: preimage mismatch @ {site:08X}")
        struct.pack_into("<I", src, off, new)
    phoff, = struct.unpack_from("<I", src, 0x1C)
    shoff, = struct.unpack_from("<I", src, 0x20)
    phentsize, phnum, shentsize, shnum = struct.unpack_from("<HHHH", src, 0x2A)
    first_data = min(struct.unpack_from("<I", src, phoff + i * phentsize + 4)[0] for i in range(phnum))
    if phoff != 0x34 or phoff + (phnum + 1) * phentsize > first_data + SHIFT:
        raise AssertionError("bake: unexpected retail ELF layout")
    words = sorted((a, v) for _p, a, v in built["words"])
    lo, hi = words[0][0], words[-1][0] + 4
    image = bytearray(hi - lo)
    for a, v in words:
        struct.pack_into("<I", image, a - lo, v)
    out = bytearray(src[:first_data]) + bytearray(SHIFT) + src[first_data:]
    while len(out) % 16:
        out.append(0)
    cave_off = len(out)
    out += image
    table = bytearray()
    for i in range(phnum):
        ph = list(struct.unpack_from("<8I", src, phoff + i * phentsize))
        ph[1] += SHIFT
        table += struct.pack("<8I", *ph)
    table += struct.pack("<8I", 1, cave_off, lo, lo, len(image), len(image), 7, 0x10)  # PT_LOAD RWX
    out[phoff:phoff + len(table)] = table
    struct.pack_into("<H", out, 0x2C, phnum + 1)
    if shoff and shnum:
        struct.pack_into("<I", out, 0x20, shoff + SHIFT)
        for i in range(shnum):
            at = shoff + SHIFT + i * shentsize + 16  # sh_offset
            o, = struct.unpack_from("<I", out, at)
            if o >= first_data:
                struct.pack_into("<I", out, at, o + SHIFT)
    return bytes(out)


PREBUILT = ROOT / "ps2" / "prebuilt"


def export_bake(built: dict) -> dict:
    """JSON-safe description of a baked hook set (our own code words + verified site/patch list)."""
    out = {"base": f"{built['base']:08X}",
           "words": [[f"{a:08X}", f"{v:08X}"] for _p, a, v in sorted(built["words"], key=lambda t: t[1])],
           "sites": [[f"{a:08X}", f"{o:08X}", f"{n:08X}"] for a, o, n in built["sites"]]}
    syms = {k: f"{built['syms'][k]:08X}" for k in KURO_EXPORTED_SYMS if k in built.get("syms", {})}
    if syms:
        out["syms"] = syms
    return out


def import_bake(spec: dict) -> dict:
    return {"base": int(spec["base"], 16),
            "words": [(0, int(a, 16), int(v, 16)) for a, v in spec["words"]],
            "sites": [(int(a, 16), int(o, 16), int(n, 16)) for a, o, n in spec["sites"]],
            "syms": {k: int(v, 16) for k, v in spec.get("syms", {}).items()}}


VIDEO_HOOK_PROFILES = {"auto"}

# Arcade rank gauge: the RANK gauge routine 0x00129360 (called every frame from the HUD pass at 0x0012E42C) draws
# only in Arrange (0x00338F44) or Arcade PRACTICE (0x00338FA4); its fill is the shared stored rank 0x00338EB4, so it
# already works in Arcade. Dropping the PRACTICE test's branch (beqz v1, 0x00129758) shows it in every Arcade game.
# The gauge sits where Arcade blinks "PRESS START / button" for a side not in the game (Arrange and PRACTICE never
# show it); the four string loads (0x00205F20, 0x00205F30) are pointed at the game's blank string 0x00205F40.
RANK_GAUGE_EDITS = [
    (0x00129394, 0x106000F0, 0x00000000),
    (0x0012C7C0, 0x24845F20, 0x24845F40),
    (0x0012C7E4, 0x24845F30, 0x24845F40),
    (0x0012CA00, 0x24845F20, 0x24845F40),
    (0x0012CA24, 0x24845F30, 0x24845F40),
]


def patch_retail_words(elf: bytes, edits) -> bytes:
    """Apply (address, original, new) word edits to an executable still in the retail file layout."""
    out = bytearray(elf)
    for site, orig, new in edits:
        off = site - build_pnach.ELF_BASE + build_pnach.ELF_FILE_OFFSET
        found, = struct.unpack_from("<I", out, off)
        if found != orig:
            raise AssertionError(f"patch: preimage mismatch @ {site:08X}")
        struct.pack_into("<I", out, off, new)
    return bytes(out)


def _load_hook(key: str) -> tuple[dict, str]:
    if have_toolchain() and not EXTRA_DEFINES:
        with tempfile.TemporaryDirectory() as tmp:
            return build_hook(key, Path(tmp), BAKE_BASE, BAKE_END), "built from ps2/hooks with mips-linux-gnu-gcc"
    path = PREBUILT / f"{key}.json"
    return import_bake(json.loads(path.read_text())), f"prebuilt {path.relative_to(ROOT)}"


def _select_sites(baked: dict, video: str, rank_gauge: bool) -> dict:
    """Keep the runtime video sites only with their profile, the CONFIG row only with the rank gauge."""
    drop = set()
    if video not in VIDEO_HOOK_PROFILES:
        drop |= VIDEO_SITES
    if not rank_gauge:
        drop |= RANK_OPTION_SITES
    baked["sites"] = [x for x in baked["sites"] if x[0] not in drop]
    if rank_gauge:  # starts ON; the CONFIG row (options.c) rewrites these words
        baked["sites"] = baked["sites"] + list(RANK_GAUGE_EDITS)
    return baked


def frontend_video_hook(video: str, rank_gauge: bool = False, position: int = 2):
    """Callable for build_menu_probe.build(executable_hook=...): bakes the instant-KURO image (ps2/hooks/kuro.c,
    with video.c and options.c) into the frontend executable: Black Label switched at runtime from the KURO row,
    PRACTICE in ARRANGE MODE, the runtime video switch with the auto profile, ARCADE CONFIG > RANK GAUGE with the rank
    gauge."""
    built = _load_hook("kuro")[0]
    drop = set() if rank_gauge else set(RANK_OPTION_SITES)
    if video not in VIDEO_HOOK_PROFILES:  # keep the per-frame call (KURO's switch-off); no video switching
        drop |= {a for a, _o, _e in VIDEO_APPLY_SITES}
        set_sym_word(built, "video_enabled", 0)
    built["sites"] = [x for x in built["sites"] if x[0] not in drop] + (list(RANK_GAUGE_EDITS) if rank_gauge else [])
    set_sym_word(built, "kuro_row", position)
    return lambda elf: bake_elf(elf, built)


def bake_payload(retail: bytes, key: str = "bl_mode", video: str = "retail", work: Path | None = None,
                 rank_gauge: bool = False) -> tuple[bytes, str]:
    """Baked BLACK LABEL executable. Uses the cross toolchain when present, else the committed prebuilt image."""
    if work is not None and have_toolchain() and not EXTRA_DEFINES:
        baked, source = build_hook(key, Path(work), BAKE_BASE, BAKE_END), "built from ps2/hooks with mips-linux-gnu-gcc"
    else:
        baked, source = _load_hook(key)
    baked = _select_sites(baked, video, rank_gauge)
    vid = video_profile(video)
    taken = {a for a, _o, _n in baked["sites"]}
    clash = [f"{a:08X}" for a, _o, _n in vid if a in taken]
    if clash:
        raise AssertionError(f"video profile overlaps hook sites: {clash}")
    baked["sites"] = list(baked["sites"]) + list(vid)
    return bake_elf(retail, baked), source


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--elf", type=Path, help="clean SLPM_663.01 or ISO, to verify hook-site preimages")
    ap.add_argument("--check-ram", type=Path, action="append", default=[], help="PCSX2 eeMemory.bin dump(s)")
    ap.add_argument("--output", type=Path, default=ROOT / "pnach" / "hooks")
    ap.add_argument("--listing-dir", type=Path, default=ROOT / "build" / "ee_hooks")
    ap.add_argument("--define", action="append", default=[], help="extra -D for test bakes (blocks PNACH output)")
    ap.add_argument("--bake-video", default="retail",
                    help="video profile for the baked copy (research/phase04 VIDEO_PROFILES: retail, 240p_core, "
                         "240p_halfpixel, 240p_cave_beta, auto); match the launcher's --video-profile")
    ap.add_argument("--bake-elf", nargs=2, metavar=("HOOK", "OUT"),
                    help="write a retail-ELF copy with HOOK built in (needs --elf), for the sixth menu entry")
    args = ap.parse_args(argv)
    if args.define:
        EXTRA_DEFINES.extend(args.define)
        args.output = Path(tempfile.mkdtemp())  # test defines never overwrite committed PNACH profiles
    if not have_toolchain():
        print("SKIP: mips-linux-gnu-gcc not installed (apt-get install gcc-mips-linux-gnu)")
        return 0
    elf = build_pnach.load_elf(args.elf) if args.elf else None
    args.listing_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for key, h in HOOKS.items():
            built = build_hook(key, Path(tmp))
            (args.listing_dir / f"{key}.lst").write_text(built["listing"])
            if elf and not h.get("frontend"):
                verify_sites(elf, built)
            if args.bake_elf and args.bake_elf[0] == key:
                if not elf:
                    raise ValueError("--bake-elf needs --elf (the clean retail ELF or ISO)")
                baked = build_hook(key, Path(tmp), BAKE_BASE, BAKE_END)
                video = video_profile(args.bake_video)
                taken = {site for site, _o, _n in baked["sites"]}
                clash = [f"{a:08X}" for a, _o, _n in video if a in taken]
                if clash:
                    raise AssertionError(f"video profile overlaps hook sites: {clash}")
                if args.bake_video not in VIDEO_HOOK_PROFILES:
                    baked["sites"] = [x for x in baked["sites"] if x[0] not in VIDEO_SITES]
                baked["sites"] = baked["sites"] + list(video)
                Path(args.bake_elf[1]).write_bytes(bake_elf(elf, baked))
                print(f"{h['test_id']} {key}: baked at {BAKE_BASE:08X} (video {args.bake_video}) into {args.bake_elf[1]}")
            for dump in args.check_ram:
                check_ram(dump, built)
            miss = pending(h)
            if h.get("bake_only"):
                if not EXTRA_DEFINES:
                    PREBUILT.mkdir(parents=True, exist_ok=True)
                    baked_pre = build_hook(key, Path(tmp), BAKE_BASE, BAKE_END)
                    (PREBUILT / f"{key}.json").write_text(json.dumps(export_bake(baked_pre), indent=0) + "\n")
                print(f"{h['test_id']} {key}: built {built['size']} bytes (bake-only, no PNACH; prebuilt image refreshed)")
                continue
            folder = args.output / key
            target = folder / build_pnach.NAME
            if miss:
                if target.exists():
                    target.unlink()
                print(f"{h['test_id']} {key}: built {built['size']} bytes; NOT emitted, pending facts: {', '.join(miss)}")
                continue
            folder.mkdir(parents=True, exist_ok=True)
            txt = build_pnach.HEADER + "// Injected-code profile: enable alone, cold boot, temporary memory card.\n\n" \
                + pnach_group(h, built)
            build_pnach.check_pnach(txt, min_addr=CAVE_BASE)
            target.write_text(txt, encoding="utf-8")
            print(f"{h['test_id']} {key}: {built['size']} bytes at {CAVE_BASE:08X}, "
                  f"{len(built['words'])} cave words, {len(built['sites'])} hook site(s) -> "
                  f"{target.relative_to(ROOT) if target.is_relative_to(ROOT) else target}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssertionError, ValueError, RuntimeError) as err:
        print("FAIL:", err, file=sys.stderr)
        sys.exit(1)
