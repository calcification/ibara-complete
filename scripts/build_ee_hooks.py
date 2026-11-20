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
        "sources": ["xtc.c", "xtc_hud.c", "bl_return.c"],
        "stubs": [("xtc_entry", 0x0012AC60, "xtc_frame"), ("ret_entry", 0x001370E0, "bl_return_to_launcher"),
                  ("hud_entry", 0x0012C0E0, "xtc_hud")],
        "sites": [(0x0012E62C, 0x0C04AB18, "xtc_entry"), (0x001CA7F0, 0x0C04DC38, "ret_entry"),
                  (0x0012C394, 0x0C04B038, "hud_entry"), (0x0012C3BC, 0x0C04B038, "hud_entry")],
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
        + [(0x002FCF24, 0x0012FC24, 0x0012FBA8), (0x0012FB78, 0x14A00038, 0x00000000)],
    },
    "bl_xtc": {
        "test_id": "K01",
        "title": "BLACK LABEL / XTC graze counter (+10 per graze)",
        "description": ("Kuro BL graze: holding shot 5+ frames near enemy bullets adds 10 points per bullet. "
                        "State at 000C0000: magic XTC1, then per player quarters(s32)/timer(u16)/held(u8). "
                        "Run only after C00 passes. No HUD counter yet. RUNTIME UNTESTED."),
        "sources": ["xtc.c"],
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


EXTRA_DEFINES: list[str] = []  # --define NAME (test builds only; never for committed profiles)


def build_hook(key: str, work: Path, base: int = CAVE_BASE, end_limit: int = CAVE_END) -> dict:
    h = HOOKS[key]
    objs = []
    stub_src = work / f"{key}_stubs.S"
    lines = [f'#include "{PS2 / "hooks" / "stub.S"}"']
    defsyms = []
    for entry, original, chook in h["stubs"]:
        sym = f"retail_{original:08X}"
        lines.append(f"HOOK_AFTER {entry}, {sym}, {chook}")
        defsyms += ["--defsym", f"{sym}=0x{original:08X}"]
    stub_src.write_text("\n".join(lines) + "\n")
    for src in [stub_src] + [PS2 / "hooks" / s for s in h["sources"]]:
        obj = work / (src.stem + ".o")
        run([CROSS + "gcc", *CFLAGS, *[f"-D{d}" for d in EXTRA_DEFINES], "-c", str(src), "-o", str(obj)])
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
    sites.extend(h.get("patches", []))  # plain word patches: same preimage check and application
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--elf", type=Path, help="clean SLPM_663.01 or ISO, to verify hook-site preimages")
    ap.add_argument("--check-ram", type=Path, action="append", default=[], help="PCSX2 eeMemory.bin dump(s)")
    ap.add_argument("--output", type=Path, default=ROOT / "pnach" / "hooks")
    ap.add_argument("--listing-dir", type=Path, default=ROOT / "build" / "ee_hooks")
    ap.add_argument("--define", action="append", default=[], help="extra -D for test bakes (blocks PNACH output)")
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
            if elf:
                verify_sites(elf, built)
            if args.bake_elf and args.bake_elf[0] == key:
                if not elf:
                    raise ValueError("--bake-elf needs --elf (the clean retail ELF or ISO)")
                baked = build_hook(key, Path(tmp), BAKE_BASE, BAKE_END)
                Path(args.bake_elf[1]).write_bytes(bake_elf(elf, baked))
                print(f"{h['test_id']} {key}: baked at {BAKE_BASE:08X} into {args.bake_elf[1]}")
            for dump in args.check_ram:
                check_ram(dump, built)
            miss = pending(h)
            if h.get("bake_only"):
                print(f"{h['test_id']} {key}: built {built['size']} bytes (bake-only, no PNACH)")
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
