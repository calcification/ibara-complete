#!/usr/bin/env python3
"""Ibara Complete Phase 9 -- read-only PS2 bullet cancellation / rose-score audit.

Input: unmodified Japanese Ibara SLPM_663.01, or retail ISO containing that ELF.
Does not patch, modify, or distribute game data. No external Python dependencies.

Findings are *static* instruction/dataflow results, not proven runtime behavior.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path

ELF_SHA256 = "263d3079dee66af82815219351553075340a4d9f42aceaa7bb8ef2bfb812ffac"
ELF_SIZE = 2_329_648
ELF_LBA = 1_919_173
ELF_LOAD = 0x00100000
SEGMENT_OFFSET = 0x80

# Independent instruction fingerprints from user's exact unmodified retail ELF.
# These are individual 32-bit words, not game logic or distributed executable data.
ANCHORS = {
  0x0012E62C:0x0C04AB18,
  0x0012AC60:0x27BDFF90, 0x0012AC74:0x2463C380, 0x0012AC7C:0x24A5EA40,
  0x0012AD1C:0x3C110047, 0x0012AD28:0x263182EC,
  0x0012AE40:0x8E430000, 0x0012AE44:0x30638000,
  0x0012AE48:0x10600019, 0x0012AE50:0x8F839254, 0x0012AE54:0x10600038,
  0x0012AE5C:0x8E440004, 0x0012AE60:0x2483FFFF,
  0x0012AE64:0x2C610002, 0x0012AE68:0x1420001B,
  0x0012AE70:0x1080002B, 0x0012AE78:0x2482FFF7,
  0x0012AE7C:0x2C410002, 0x0012AE80:0x14200027,
  0x0012AE8C:0x0C0487F0, 0x0012AE90:0x24050001,
  0x0012AED8:0x8E440008, 0x0012AEE0:0x10830009,
  0x0012AEE8:0x1080FF9F, 0x0012AEF4:0x0C0487F0,
  0x0012AEF8:0x0000282D, 0x0012AF0C:0x0C0487F0,
  0x0012AF10:0x24050002, 0x0012AF24:0x0C0487F0,
  0x0012AF28:0x0000282D, 0x0012AF3C:0x0C0487F0,
  0x0012AF40:0x24050001,
  0x00121FC0:0x27BDFFD0, 0x00122074:0x1202001B,
  0x00122080:0x16020009, 0x00122088:0x8F829254,
  0x0012208C:0x24040003, 0x001220A0:0x0C04C1B4,
  0x001220E4:0x8F829254, 0x001220E8:0x24040007,
  0x001220FC:0x0C04C1B4,
  0x001306D0:0x27BDFF80, 0x001307AC:0xAE020000,
  0x001307B0:0x0C04C228, 0x001307BC:0xAE130028,
  0x001307C0:0xAE12002C, 0x00130810:0x24030007,
  0x00130814:0x16830018, 0x0013081C:0x8F8291C4,
  0x00130820:0x3C030100, 0x00130824:0x00621023,
  0x00130828:0x00021402, 0x0013082C:0xAE020054,
  0x00130840:0x28420100, 0x0013084C:0x2402012C,
  0x00130850:0xAE020054, 0x001308A0:0x27BDFFE0,
  0x001308DC:0xAE050004, 0x001308E0:0xAE000008,
  0x0012F6C4:0x1440000A, 0x0012F6E0:0x0C04A77C,
  0x0012F708:0x0C04A770, 0x0012F720:0x0C04BAFC,
  0x0012F730:0x8E040008, 0x0012F734:0x8E020054,
  0x0012F738:0x00041880, 0x0012F73C:0x00641821,
  0x0012F740:0x00031840, 0x0012F744:0x2463001E,
  0x0012F748:0x00433818, 0x0012F764:0x3C020045,
  0x0012F780:0x8C620000, 0x0012F784:0x00471021,
  0x0012A61C:0x0C04BF40, 0x0012FD00:0x27BDFFC0,
}

# MIPS JAL paths are checked independently of raw-word fingerprints.
JAL_EDGES = {
    0x0012E62C:0x0012AC60,  # main update -> projectile/bullet collision pass
    0x0012AE8C:0x00121FC0,  # one conversion selector
    0x0012AEF4:0x00121FC0,
    0x0012AF0C:0x00121FC0,
    0x0012AF24:0x00121FC0,
    0x0012AF3C:0x00121FC0,
    0x001220A0:0x001306D0,  # selector 2 -> item type 3
    0x001220FC:0x001306D0,  # selector 1 -> item type 7
    0x001307B0:0x001308A0,  # item initializer
    0x0012A61C:0x0012FD00,  # pickup intersection -> item dispatcher
    0x0012F6E0:0x00129DF0,  # type 7, Arcade rank-hardening
    0x0012F708:0x00129DC0,  # type 7, Arrange rank-relief
    0x0012F720:0x0012EBF0,  # type 7, Arcade item-score table
}

ITEM_TYPES = {0: "none", 3: "medal (item type 3)", 7: "rose/score item (type 7)"}


def extract_elf(path: Path) -> tuple[bytes, str]:
    with path.open("rb") as f:
        if f.read(4) == b"\x7fELF":
            if path.stat().st_size != ELF_SIZE:
                raise ValueError("not the expected original ELF size")
            f.seek(0)
            return f.read(), "ELF"
        f.seek(16 * 2048 + 1)
        if f.read(5) != b"CD001":
            raise ValueError("input is neither a supported ELF nor ISO9660")
        f.seek(ELF_LBA * 2048)
        data = f.read(ELF_SIZE)
    if len(data) != ELF_SIZE or data[:4] != b"\x7fELF":
        raise ValueError("retail ELF not found at expected sector")
    return data, "ISO"


def get_word(elf: bytes, addr: int) -> int:
    off = addr - ELF_LOAD + SEGMENT_OFFSET
    if addr % 4 or off < SEGMENT_OFFSET or off + 4 > len(elf):
        raise ValueError("invalid executable virtual address 0x%08X" % addr)
    return struct.unpack_from("<I", elf, off)[0]


def jal_target(inst: int, addr: int) -> int:
    if inst >> 26 != 3:
        raise ValueError("no JAL at 0x%08X" % addr)
    return ((addr + 4) & 0xF0000000) | ((inst & 0x03FFFFFF) << 2)


def selector_for_collision(arrange: bool, projectile_type: int, subtype: int) -> int | None:
    """Model of *one conditional bullet-hit branch* in 0x12AE50..0x12AF40.

    Only applies after the collision passed the relevant object-flag and hitbox
    guards. None means skip the conversion call (not universal bullet survival).
    Selector 0 calls the helper but does not spawn an item in that helper.
    """
    if not arrange:
        return 1
    if projectile_type in (1, 2):
        if subtype == 0:
            return None
        return 2 if subtype == 1 else 0
    if projectile_type in (0, 9, 10):
        return 0
    return 1


def item_from_selector(selector: int | None) -> int | None:
    return {1: 7, 2: 3}.get(selector)


def rank_factor(stored_rank: int) -> int:
    """PS2 Arrange type-7 item factor stored at item+0x54 on spawn.

    Derived from 0x13081C..0x130850. For a *valid*, nonnegative 24-bit
    game rank; 0x00000000 is special and maps to 300, not 256.
    """
    if not 0 <= stored_rank <= 0xFFFFFF:
        raise ValueError("expected 24-bit nonnegative rank value")
    x = (0x1000000 - stored_rank) >> 16
    if x == 0:
        x = 1
    elif x >= 256:
        x = 300
    return x


def arrange_rose_points(level: int, spawn_factor: int) -> int:
    """The type-7 Arrange collection formula, not a standalone cancel bonus.

    0x12F730..0x12F784: (10 * item[+8] + 30) * item[+0x54].
    Mult is a R5900/EE rd,rs,rt 3-register MULT (0x00433818, rd=7).
    """
    if not 0 <= level <= 0xFFFF or not 1 <= spawn_factor <= 300:
        raise ValueError("input outside modeled range")
    return (10 * level + 30) * spawn_factor


def audit(elf: bytes, verify_sha: bool = True) -> dict:
    sha = hashlib.sha256(elf).hexdigest()
    if verify_sha and sha != ELF_SHA256:
        raise ValueError("ELF SHA-256 mismatch: not the unmodified supported retail revision")
    if len(elf) != ELF_SIZE:
        raise ValueError("ELF size mismatch")
    for addr, expected in ANCHORS.items():
        actual = get_word(elf, addr)
        if actual != expected:
            raise ValueError("opcode mismatch at 0x%08X: 0x%08X expected 0x%08X" % (addr,actual,expected))
    for addr, expected in JAL_EDGES.items():
        actual = jal_target(get_word(elf, addr), addr)
        if actual != expected:
            raise ValueError("JAL mismatch at 0x%08X: target 0x%08X" % (addr,actual))
    # R5900 extended MULT writes result to rd=$a3. Confirms arithmetic in
    # subsequent score update; verify the R-type encoding as well as fingerprint.
    mul = get_word(elf, 0x12F748)
    if ((mul >> 21)&31, (mul >> 16)&31, (mul>>11)&31, mul&63)!=(2,3,7,0x18):
        raise ValueError("unexpected R5900 multiply register mapping")
    # Verify two decoder-visible identity constants rather than imply an entire
    # static machine-code CFG is executable or benchmarked.
    if get_word(elf,0x12208C) != 0x24040003 or get_word(elf,0x1220E8) != 0x24040007:
        raise ValueError("item-type creation constants have changed")
    table = []
    for mode in ("Arcade", "Arrange"):
        for t in (0,1,2,3,8,9,10,11):
            for s in (0,1,2):
                selector = selector_for_collision(mode=="Arrange",t,s)
                table.append({"mode":mode,"projectile_type":t,"projectile_subtype":s,
                              "conversion_selector":selector,
                              "item_spawned":item_from_selector(selector),
                              "note": "conditional path only; collision guards must already pass"})
    examples = []
    for rank in (0xFFFFFF,0xF00000,0x800000,0x010000,0x000001,0x000000):
        f=rank_factor(rank)
        examples.append({"stored_rank":f"0x{rank:06X}","factor_at_spawn":f,
                         "points_at_collection_level0":arrange_rose_points(0,f),
                         "points_at_collection_level3":arrange_rose_points(3,f)})
    return {
      "status":"static exact-original-ELF audit; no emulator or console execution",
      "elf_sha256":sha,
      "verified_opcode_count":len(ANCHORS),"verified_jal_edges":len(JAL_EDGES),
      "call_chain":["0x0012E62C -> 0x0012AC60 (projectile/bullet collision pass)",
        "0x0012AE8C/EF4/F0C/F24/F3C -> 0x00121FC0 (selector-specific conversion helper)",
        "selector 1 -> item type 7; selector 2 -> item type 3; 0 -> no spawn in helper",
        "0x001220FC/0x001220A0 -> 0x001306D0 (item spawn)",
        "0x001307B0 -> 0x001308A0 (initialize item)",
        "0x0012A61C -> 0x0012FD00 (later player-item pickup)",
        "type 7 handler 0x0012F680 -> Arcade generic points or Arrange rank-weighted points"],
      "projectile_pool_base":"0x0044EA40","projectile_record_stride":"0x50",
      "bullet_pool_base":"0x004682EC","bullet_record_stride":"0x54",
      "item_pool_base":"0x00453A40","item_record_stride":"0x58",
      "type7_spawning_rank_factor":"item[+0x54] = ((0x01000000 - stored_rank) >> 16); floor 1, and 256 maps to 300",
      "type7_arrange_collection_points":"(10 * item[+0x08] + 30) * item[+0x54]",
      "type7_arcade_points":"fixed item reward metadata; initial samples 100,200,400,800 (Phase 8)",
      "conversion_is_direct_score":"no direct player score award established inside the verified 0x12AC60 -> 0x121FC0 -> 0x1306D0 path; pickup does award points",
      "hypotheses_not_yet_verified":["precise projectile-type names (bomb/Hadou/etc)",
         "whether the collision helper always retires a bullet with associated pointers",
         "full late-stage boss cancellation and extra scoring paths",
         "Kuro XTC/Baradise arithmetic transplanted into the native PS2 engine"],
      "conditional_branch_cases":table,"rank_factor_examples":examples}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image",type=Path,help="Original SLPM_663.01 ELF or Ibara (Japan).iso")
    parser.add_argument("--json",type=Path,help="Write machine-readable report")
    parser.add_argument("--csv",type=Path,help="Write conditional selector truth table")
    args=parser.parse_args()
    elf,source=extract_elf(args.image)
    report=audit(elf)
    report["input_kind"]=source
    if args.json:
        args.json.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    if args.csv:
        with args.csv.open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(report["conditional_branch_cases"][0]))
            w.writeheader();w.writerows(report["conditional_branch_cases"])
    print("PASS: exact retail %s; %d instruction anchors and %d JAL edges" % (source,len(ANCHORS),len(JAL_EDGES)))
    print("PS2 Arrange type-7 rose score: (10 * level + 30) * factor-at-spawn")
    print("No input executable/ISO modified; no runtime/console test claimed.")

if __name__=="__main__":
    main()
