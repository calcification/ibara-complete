"""Packet-boundary checks for the source-only PCSX2 graphics audit."""

import lzma
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "phase22"))
from gs_workload import read_frames


def tag(loops, register, flags=0, primitive=None):
    control = 1 << 60 | flags << 58 | loops
    if primitive is not None:
        control |= 1 << 46 | primitive << 47
    return struct.pack("<QQ", control, register)


def transfer(data, channel=3):
    return struct.pack("<BBI", 0, channel, len(data)) + data


def packet(x, y, adc=False):
    return struct.pack("<QQ", x | (y << 32), int(adc) << 47)


def dump_bytes(packets):
    return struct.pack("<II9I", 0xFFFFFFFF, 36, 1, 0, 0, 36, 0, 0, 0, 36, 0) + bytes(0x2000) + packets


class GraphicsWorkloadTests(unittest.TestCase):
    def test_sprite_tag_split_between_transfers_and_image_payload(self):
        geometry = tag(2, 5, primitive=6) + packet(16, 32, adc=True)
        payload = transfer(geometry) + transfer(packet(64, 96))
        payload += transfer(tag(3, 0, flags=2) + bytes(48), 2) + b"\x01\x00"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.gs"
            path.write_bytes(dump_bytes(payload))
            self.assertEqual(read_frames(path), [
                {"gif_qwords": 7, "image_qwords": 3, "vertex_kicks": 1,
                 "primitives": 1, "filled_area": 12.0},
            ])

    def test_odd_reglist_blocks_and_ads(self):
        # PRIM via A+D, then packed-in-pairs register writes. The unused
        # half-qword after the final vertex is padding and must be ignored.
        prim = tag(1, 14) + struct.pack("<QQ", 6, 0)
        geometry = tag(3, 5, flags=1) + struct.pack("<4Q", 0, 32 | (32 << 16), 64, 64 | (64 << 16))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.gs.xz"
            path.write_bytes(lzma.compress(dump_bytes(transfer(prim + geometry) + b"\x01\x00")))
            self.assertEqual(read_frames(path), [
                {"gif_qwords": 5, "image_qwords": 0, "vertex_kicks": 3,
                 "primitives": 1, "filled_area": 4.0},
            ])

    def test_rejects_partial_transfer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.gs"
            path.write_bytes(dump_bytes(transfer(tag(1, 5))[:-1]))
            with self.assertRaisesRegex(ValueError, "truncated"):
                read_frames(path)


if __name__ == "__main__":
    unittest.main()
