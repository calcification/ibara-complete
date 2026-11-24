#!/usr/bin/env python3
"""Summarize short PCSX2 GS dumps by refresh without replaying their assets."""

import argparse
from dataclasses import asdict, dataclass
import json
import lzma
from pathlib import Path
import struct


U32 = struct.Struct("<I")
QWORD = struct.Struct("<QQ")
GS_PRIV_SIZE = 0x2000
MAX_PACKET_SIZE = 64 * 1024 * 1024
VERTEX_COUNTS = (1, 2, 2, 3, 3, 3, 2, 0)


@dataclass
class Frame:
    gif_qwords: int = 0
    image_qwords: int = 0
    vertex_kicks: int = 0
    primitives: int = 0
    filled_area: float = 0.0


class Draws:
    def __init__(self):
        self.primitive = 7
        self.vertices = []
        self.frame = Frame()
        self.double_area = 0

    def set_primitive(self, value):
        self.primitive = value & 7
        self.vertices.clear()

    def vertex(self, x, y, drawing):
        need = VERTEX_COUNTS[self.primitive]
        if not need:
            return
        self.frame.vertex_kicks += int(drawing)
        self.vertices.append((x, y))
        if len(self.vertices) < need:
            return
        if drawing:
            self.frame.primitives += 1
            if self.primitive in (3, 4, 5):
                (ax, ay), (bx, by), (cx, cy) = self.vertices
                self.double_area += abs((bx - ax) * (cy - ay) - (cx - ax) * (by - ay))
            elif self.primitive == 6:
                (ax, ay), (bx, by) = self.vertices
                self.double_area += 2 * abs((bx - ax) * (by - ay))
        if self.primitive in (2, 4):
            self.vertices.pop(0)
        elif self.primitive == 5:
            self.vertices.pop(1)
        else:
            self.vertices.clear()

    def write(self, register, low, high, packed):
        if packed and register == 14:  # A+D is a normal 64-bit register write.
            register, packed = high & 127, False
        if register == 0:
            self.set_primitive(low)
        elif register in (4, 5, 12, 13):
            x = low & 0xFFFF
            y = (low >> (32 if packed else 16)) & 0xFFFF
            drawing = register in (4, 5) and not (packed and high & (1 << 47))
            self.vertex(x, y, drawing)

    def end_frame(self):
        frame = self.frame
        # GS vertex positions have four fractional bits.
        frame.filled_area = self.double_area / (2 * 16 * 16)
        self.frame = Frame()
        self.double_area = 0
        return asdict(frame)


class GIFPath:
    def __init__(self):
        self.remaining = 0
        self.mode = 0
        self.registers = ()
        self.cursor = 0

    def transfer(self, data, draws):
        draws.frame.gif_qwords += len(data) // 16
        for low, high in QWORD.iter_unpack(data):
            if not self.remaining:
                self.mode = (low >> 58) & 3
                nloop = low & 0x7FFF
                if self.mode >= 2:
                    self.remaining = nloop
                else:
                    count = (low >> 60) or 16
                    self.registers = tuple((high >> (4 * i)) & 15 for i in range(count))
                    self.cursor = 0
                    self.remaining = nloop * count
                    if nloop and self.mode == 0 and low & (1 << 46):
                        draws.set_primitive(low >> 47)
                continue
            if self.mode >= 2:
                draws.frame.image_qwords += 1
                self.remaining -= 1
                continue
            if self.mode == 0:
                draws.write(self.registers[self.cursor], low, high, True)
                self.remaining -= 1
                self.cursor = (self.cursor + 1) % len(self.registers)
                continue
            for value in (low, high):
                if self.remaining:
                    draws.write(self.registers[self.cursor], value, 0, False)
                    self.remaining -= 1
                    self.cursor = (self.cursor + 1) % len(self.registers)


def read_frames(path):
    raw = lzma.open(path, "rb") if path.suffix == ".xz" else path.open("rb")
    with raw:
        def read(size):
            data = raw.read(size)
            if len(data) != size:
                raise ValueError("truncated GS dump")
            return data

        marker, length = struct.unpack("<II", read(8))
        if marker != 0xFFFFFFFF or not 36 <= length <= 16 * 1024 * 1024:
            raise ValueError("expected a modern uncompressed or XZ PCSX2 GS dump")
        _, state_size = struct.unpack_from("<II", read(length))
        if state_size > MAX_PACKET_SIZE:
            raise ValueError("invalid GS state size")
        read(state_size)
        read(GS_PRIV_SIZE)
        paths = [GIFPath() for _ in range(4)]
        draws = Draws()
        frames = []
        while packet := raw.read(1):
            if packet == b"\x00":
                channel = read(1)[0]
                size, = U32.unpack(read(4))
                if channel >= len(paths) or size > MAX_PACKET_SIZE or size % QWORD.size:
                    raise ValueError("invalid GIF transfer")
                paths[channel].transfer(read(size), draws)
            elif packet == b"\x01":
                read(1)
                frames.append(draws.end_frame())
            elif packet == b"\x02":
                read(4)
            elif packet == b"\x03":
                read(GS_PRIV_SIZE)
            else:
                raise ValueError(f"unknown GS dump packet {packet.hex()}")
        return frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", type=Path, help="short uncompressed .gs or .gs.xz file")
    args = parser.parse_args()
    try:
        print(json.dumps(read_frames(args.dump), indent=2))
    except (OSError, ValueError, lzma.LZMAError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
