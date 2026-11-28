#!/usr/bin/env python3
"""Read a PCSX2 / PS2 memory card image (8 MB, raw pages with or without ECC): list folders and files, extract one,
or check the file system's consistency. Standard library only (research/phase46).

    python3 tools/mc_read.py Mcd001.ps2                     # tree with sizes
    python3 tools/mc_read.py Mcd001.ps2 --get BISLPM-66301KURO/REPLAY1.DAT out.bin
    python3 tools/mc_read.py Mcd001.ps2 --check             # FAT chains vs directory sizes, lost / shared clusters
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

MAGIC = b"Sony PS2 Memory Card Format "


class Card:
    def __init__(self, data: bytes):
        if not data.startswith(MAGIC):
            raise ValueError("not a PS2 memory card image")
        self.d = data
        (self.page_len, self.ppc, self.ppb) = struct.unpack_from("<HHH", data, 0x28)
        self.clusters_per_card, self.alloc_offset, self.alloc_end, self.root = struct.unpack_from("<IIII", data, 0x30)
        self.ifc = [x for x in struct.unpack_from("<32I", data, 0x50)]
        raw_pages = len(data) // self.page_len
        self.raw = self.page_len + 16 if len(data) % (self.page_len + 16) == 0 and len(data) != raw_pages * self.page_len \
            else self.page_len
        if len(data) == 0x840000:
            self.raw = self.page_len + 16
        self.csize = self.page_len * self.ppc
        self.per = self.csize // 4  # FAT entries per cluster

    def cluster(self, n: int) -> bytes:
        """Absolute cluster n (without ECC)."""
        out = b""
        for p in range(self.ppc):
            off = (n * self.ppc + p) * self.raw
            out += self.d[off:off + self.page_len]
        return out

    def fat(self, rel: int) -> int:
        i = rel // self.per
        ind = struct.unpack_from("<I", self.cluster(self.ifc[i // self.per]), (i % self.per) * 4)[0]
        return struct.unpack_from("<I", self.cluster(ind), (rel % self.per) * 4)[0]

    def chain(self, rel: int) -> list[int]:
        out, seen = [], set()
        while rel != 0x7FFFFFFF and rel != 0xFFFFFFFF:
            if rel in seen:
                raise ValueError(f"FAT loop at cluster {rel}")
            seen.add(rel)
            out.append(rel)
            e = self.fat(rel)
            if not e & 0x80000000:
                raise ValueError(f"cluster {rel} in a chain is marked free")
            rel = e & 0x7FFFFFFF
            if rel == 0x7FFFFFFF:
                break
        return out

    def read(self, rel: int, length: int) -> bytes:
        data = b"".join(self.cluster(self.alloc_offset + c) for c in self.chain(rel))
        return data[:length]

    def entries(self, rel: int, count: int):
        raw = self.read(rel, count * 512)
        for k in range(count):
            e = raw[k * 512:(k + 1) * 512]
            mode, length = struct.unpack_from("<HxxI", e, 0)
            cl = struct.unpack_from("<I", e, 0x10)[0]
            name = e[0x40:0x60].split(b"\0")[0].decode("ascii", "replace")
            yield mode, length, cl, name

    def walk(self, rel=None, count=None, path=""):
        if rel is None:
            rel = self.root
            count = struct.unpack_from("<I", self.cluster(self.alloc_offset + rel), 4)[0]
        for mode, length, cl, name in self.entries(rel, count):
            if not mode & 0x8000 or name in (".", ".."):
                continue
            full = f"{path}/{name}" if path else name
            if mode & 0x20:  # directory
                yield full, None, cl, length
                yield from self.walk(cl, length, full)
            else:
                yield full, length, cl, length


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("card", type=Path)
    ap.add_argument("--get", nargs=2, metavar=("PATH", "OUT"))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    c = Card(a.card.read_bytes())
    if a.get:
        for full, size, cl, _ in c.walk():
            if full == a.get[0] and size is not None:
                Path(a.get[1]).write_bytes(c.read(cl, size))
                print(f"{full}: {size} bytes")
                return 0
        print("not found", file=sys.stderr)
        return 1
    used = {}
    problems = 0
    for full, size, cl, length in c.walk():
        try:
            ch = c.chain(cl)
        except ValueError as e:
            print(f"BAD {full}: {e}")
            problems += 1
            continue
        need = -(-(size if size is not None else length * 512) // c.csize)
        if len(ch) < need:
            print(f"BAD {full}: {len(ch)} clusters for {need}")
            problems += 1
        for x in ch:
            if x in used:
                print(f"BAD {full}: cluster {x} also in {used[x]}")
                problems += 1
            used[x] = full
        if not a.check:
            print(f"{full}/" if size is None else f"{full}  {size}")
    if a.check:
        print(f"{len(used)} clusters in use, {problems} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
