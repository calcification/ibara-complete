#!/usr/bin/env python3
"""Minimal EE (MIPS R5900, little-endian) function extractor for the retail Ibara ELF.

Standard library only. Decodes just what cross-ISA matching needs: function starts (jal targets, code
pointers in data, prologues after returns), direct calls, 32-bit constants built with lui+addiu/ori,
small immediates, absolute and $gp-relative data references, and load/store displacements.
Unknown opcodes (MMI, COP2...) are skipped, never fatal.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

SP, GP, RA = 29, 28, 31
DATA_SLACK = 0x00400000


@dataclass
class Segment:
    vaddr: int
    data: bytes
    exec: bool


@dataclass
class MFunc:
    addr: int
    end: int = 0
    calls: list[int] = field(default_factory=list)
    consts: list[int] = field(default_factory=list)
    data_refs: list[int] = field(default_factory=list)
    mem_offsets: list[int] = field(default_factory=list)

    @property
    def n_insns(self) -> int:
        return (self.end - self.addr) // 4


def elf_entry(path_or_bytes) -> int:
    data = path_or_bytes if isinstance(path_or_bytes, (bytes, bytearray)) else Path(path_or_bytes).read_bytes()
    return struct.unpack_from("<I", data, 0x18)[0]


def load_elf(path_or_bytes) -> list[Segment]:
    data = path_or_bytes if isinstance(path_or_bytes, (bytes, bytearray)) else Path(path_or_bytes).read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 1:
        raise ValueError("expected ELF32 little-endian")
    phoff, = struct.unpack_from("<I", data, 0x1C)
    phentsize, phnum = struct.unpack_from("<HH", data, 0x2A)
    segs = []
    for i in range(phnum):
        p_type, off, vaddr, _pa, filesz, memsz, flags, _al = struct.unpack_from("<8I", data, phoff + i * phentsize)
        if p_type != 1 or not memsz:
            continue
        blob = data[off:off + filesz] + b"\0" * (memsz - filesz)
        segs.append(Segment(vaddr, bytes(blob), bool(flags & 1)))
    return segs


def _s16(v: int) -> int:
    return v - 0x10000 if v & 0x8000 else v


def find_gp(words: dict[int, int]) -> int | None:
    """Look for `lui $gp,hi` followed within 4 insns by `addiu/ori $gp,$gp,lo` (crt0 style)."""
    for a, w in words.items():
        if w >> 26 == 0x0F and (w >> 16) & 31 == GP:
            hi = (w & 0xFFFF) << 16
            for k in range(1, 5):
                w2 = words.get(a + 4 * k)
                if w2 is None:
                    break
                op = w2 >> 26
                if op in (0x09, 0x0D) and (w2 >> 21) & 31 == GP and (w2 >> 16) & 31 == GP:
                    lo = _s16(w2 & 0xFFFF) if op == 0x09 else (w2 & 0xFFFF)
                    return (hi + lo) & 0xFFFFFFFF
    return None


def elf_gp(path_or_bytes) -> int | None:
    """$gp from the .reginfo section (ri_gp_value), if present."""
    data = path_or_bytes if isinstance(path_or_bytes, (bytes, bytearray)) else Path(path_or_bytes).read_bytes()
    shoff, = struct.unpack_from("<I", data, 0x20)
    shentsize, shnum = struct.unpack_from("<HH", data, 0x2E)
    for i in range(shnum):
        sh = struct.unpack_from("<10I", data, shoff + i * shentsize)
        if sh[1] == 0x70000006 and sh[5] >= 24:  # SHT_MIPS_REGINFO
            return struct.unpack_from("<I", data, sh[4] + 20)[0]
    return None


def _is_prologue(w: int | None) -> bool:
    return w is not None and w >> 16 == 0x27BD and bool(w & 0x8000)


def _extent(words: dict[int, int], start: int, new_starts: set[int]) -> int | None:
    """End address (exclusive) of the function at start; records call/tail-call targets."""
    a, maxt = start, start
    while True:
        w = words.get(a)
        if w is None or a - start > 0x20000:
            return None
        op = w >> 26
        if op in (4, 5, 6, 7, 20, 21, 22, 23) or (op == 1 and ((w >> 16) & 31) in (0, 1, 2, 3, 16, 17, 18, 19)):
            maxt = max(maxt, a + 4 + (_s16(w & 0xFFFF) << 2))
        elif op in (2, 3):
            t = ((a + 4) & 0xF0000000) | ((w & 0x03FFFFFF) << 2)
            if op == 3 or not start <= t <= a:
                new_starts.add(t)
            if op == 2 and a + 4 >= maxt and not start <= t <= a:
                return a + 8  # tail call
        elif w == 0x03E00008 and a + 4 >= maxt:
            return a + 8
        a += 4


def extract(segs: list[Segment], extra_starts: set[int] | None = None,
            gp: int | None = None) -> tuple[dict[int, MFunc], int | None]:
    """Recursive descent from extra_starts (entry point...) plus code pointers found in the image."""
    code = [s for s in segs if s.exec]
    words: dict[int, int] = {}
    for s in code:
        for i in range(0, len(s.data) - 3, 4):
            words[s.vaddr + i] = struct.unpack_from("<I", s.data, i)[0]
    lo_code = min(s.vaddr for s in code)
    hi_code = max(s.vaddr + len(s.data) for s in code)

    def in_code(a: int) -> bool:
        return lo_code <= a < hi_code and a % 4 == 0

    pending = {a for a in (extra_starts or ()) if in_code(a)} or {code[0].vaddr}
    extents: dict[int, int] = {}
    for _round in range(3):
        while pending:
            st = pending.pop()
            if st in extents or not in_code(st):
                continue
            found: set[int] = set()
            end = _extent(words, st, found)
            if end is None:
                continue
            extents[st] = end
            pending.update(t for t in found if in_code(t) and t not in extents)
        # every jal word in the image (code reached only through pointers to frameless leaves);
        # a target is kept only if it decodes to a well-formed function in _extent
        for a, w in words.items():
            if w >> 26 == 3:
                t = ((a + 4) & 0xF0000000) | ((w & 0x03FFFFFF) << 2)
                if t not in extents and in_code(t):
                    pending.add(t)
        # code pointers anywhere in the image (dispatch tables, lui/addiu pairs) that land on a prologue
        for s in segs:
            for i in range(0, len(s.data) - 3, 4):
                ptr = struct.unpack_from("<I", s.data, i)[0]
                if ptr not in extents and in_code(ptr) and _is_prologue(words.get(ptr)):
                    pending.add(ptr)
        if not pending:
            break
    if gp is None:
        gp = find_gp(words)
    ranges = [(s.vaddr, s.vaddr + len(s.data)) for s in segs]

    def is_data(v: int) -> bool:
        # loaded segments (bss included) plus heap-like globals just past them; values such as
        # 0x00FFFFFF / 0x01000000 (rank arithmetic) stay constants
        return any(lo <= v < hi + DATA_SLACK for lo, hi in ranges)

    funcs: dict[int, MFunc] = {}
    for st, end in sorted(extents.items()):
        f = MFunc(st, end)
        hi_regs: dict[int, int] = {}
        a = st
        while a < end:
            w = words.get(a, 0)
            op, rs, rt, imm = w >> 26, (w >> 21) & 31, (w >> 16) & 31, w & 0xFFFF
            if op == 0x03:
                f.calls.append(((a + 4) & 0xF0000000) | ((w & 0x03FFFFFF) << 2))
            elif op == 0x0F:  # lui
                hi_regs[rt] = imm << 16
            elif op in (0x09, 0x0D) and rs in hi_regs:  # addiu/ori completing lui
                v = (hi_regs[rs] + (_s16(imm) if op == 0x09 else imm)) & 0xFFFFFFFF
                (f.data_refs if is_data(v) else f.consts).append(v)
                if rt != rs:
                    hi_regs.pop(rt, None)
            elif op in (0x09, 0x08, 0x0D, 0x0C, 0x0E, 0x0A, 0x0B) and rs not in (SP, GP):
                v = _s16(imm) if op in (0x08, 0x09, 0x0A, 0x0B) else imm
                if not -16 <= v <= 16:
                    f.consts.append(v & 0xFFFFFFFF)
                hi_regs.pop(rt, None)
            elif op in (0x20, 0x21, 0x23, 0x24, 0x25, 0x27, 0x37, 0x1E, 0x28, 0x29, 0x2B, 0x3F, 0x1F):
                off = _s16(imm)
                if rs in hi_regs:  # absolute access lui+lw/sw
                    f.data_refs.append((hi_regs[rs] + off) & 0xFFFFFFFF)
                elif rs == GP and gp is not None:
                    f.data_refs.append((gp + off) & 0xFFFFFFFF)
                elif rs != SP:
                    f.mem_offsets.append(off)
                if op in (0x20, 0x21, 0x23, 0x24, 0x25, 0x27, 0x37, 0x1E):  # loads clobber rt
                    hi_regs.pop(rt, None)
            elif op == 0 and (w & 0x3F) in (0x21, 0x23, 0x25, 0x2D, 0x24):
                hi_regs.pop((w >> 11) & 31, None)
            a += 4
        funcs[st] = f
    return funcs, gp
