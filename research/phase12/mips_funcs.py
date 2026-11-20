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


def extract(segs: list[Segment], extra_starts: set[int] | None = None) -> tuple[dict[int, MFunc], int | None]:
    code = [s for s in segs if s.exec]
    words: dict[int, int] = {}
    for s in code:
        for i in range(0, len(s.data) - 3, 4):
            words[s.vaddr + i] = struct.unpack_from("<I", s.data, i)[0]
    lo_code = min(s.vaddr for s in code)
    hi_code = max(s.vaddr + len(s.data) for s in code)

    def in_code(a: int) -> bool:
        return lo_code <= a < hi_code and a % 4 == 0

    starts: set[int] = set(extra_starts or ())
    starts.update(s.vaddr for s in code)
    for a, w in words.items():
        if w >> 26 == 0x03:  # jal
            t = ((a + 4) & 0xF0000000) | ((w & 0x03FFFFFF) << 2)
            if in_code(t):
                starts.add(t)
        # prologue right after `jr $ra` + delay slot
        if w == 0x03E00008:
            nxt = a + 8
            while words.get(nxt) == 0:  # alignment nops
                nxt += 4
            w2 = words.get(nxt)
            if w2 is not None and w2 >> 16 == 0x27BD and w2 & 0x8000:
                starts.add(nxt)
    for s in segs:  # code pointers in data (dispatch tables)
        if s.exec:
            continue
        for i in range(0, len(s.data) - 3, 4):
            p = struct.unpack_from("<I", s.data, i)[0]
            w = words.get(p)
            if w is not None and in_code(p) and w >> 16 == 0x27BD and w & 0x8000:
                starts.add(p)
    gp = find_gp(words)
    ranges = [(s.vaddr, s.vaddr + len(s.data)) for s in segs]

    def is_data(v: int) -> bool:
        # loaded segments (bss included) plus heap-like globals just past them; values such as
        # 0x00FFFFFF / 0x01000000 (rank arithmetic) stay constants
        return any(lo <= v < hi + DATA_SLACK for lo, hi in ranges)

    order = sorted(starts)
    funcs: dict[int, MFunc] = {}
    for i, st in enumerate(order):
        end = order[i + 1] if i + 1 < len(order) else hi_code
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
