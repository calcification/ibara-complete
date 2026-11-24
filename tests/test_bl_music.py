"""Black Label select theme tooling (research/phase23) on synthetic data only: the BGM stream encoder and the
resource-table rebuild."""
import math
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "patcher"))

import bg00_stream  # noqa: E402
import bl_music  # noqa: E402


def synthetic_tbl(offsets, lengths):
    n = len(offsets)
    rs = 20 + 4 * n
    off_tab = rs + 8 * n
    out = bytearray(b"TBL\x04" + struct.pack("<IIII", 1, (n << 16) | rs, 0x7BAC, 0x8D60))
    out += b"".join(struct.pack("<I", rs + 8 * i) for i in range(n))
    out += b"".join(struct.pack("<II", off_tab + 4 * i, lengths[i]) for i in range(n))
    out += b"".join(struct.pack("<I", o) for o in offsets)
    return bytes(out)


def read_tbl(tbl):
    u = lambda o: struct.unpack_from("<I", tbl, o)[0]
    n = u(8) >> 16
    rows = []
    for i in range(n):
        rp = u(20 + 4 * i)
        rows.append((u(u(rp)), u(rp + 4)))
    return rows


class TblTest(unittest.TestCase):
    def test_rebuild_shifts_offsets_and_appends_entry(self):
        offs, lens = [0, 0x1000, 0x5800], [0x1000, 0x4800, 0x800]
        out = bl_music.rebuild_tbl(synthetic_tbl(offs, lens), 0x30000, 0x2000)
        self.assertEqual(out[:4], b"TBL\x04")
        self.assertEqual(out[12:20], synthetic_tbl(offs, lens)[12:20])
        self.assertEqual(read_tbl(out), [(o + 0x30000, n) for o, n in zip(offs, lens)] + [(0, 0x2000)])
        self.assertEqual(len(out), len(synthetic_tbl(offs, lens)) + 16)
        self.assertEqual(out, synthetic_tbl([o + 0x30000 for o in offs] + [0], lens + [0x2000]))


class StreamTest(unittest.TestCase):
    def test_adpcm_round_trip(self):
        tone = [8000 * math.sin(2 * math.pi * 440 * i / 44100) + 3000 * math.sin(2 * math.pi * 97 * i / 44100)
                for i in range(44100 // 4)]
        adpcm = bg00_stream.encode_adpcm(tone)
        self.assertEqual(adpcm[:16], bytes(16))
        self.assertEqual(adpcm[-32 + 1], 1)
        self.assertEqual(adpcm[-16:-14], b"\x11\x07")
        dec = bg00_stream.decode_adpcm(adpcm)[28:28 + len(tone)]
        sig = sum(v * v for v in tone)
        err = sum((a - b) ** 2 for a, b in zip(tone, dec))
        self.assertGreater(10 * math.log10(sig / err), 30)

    def test_stream_layout(self):
        adpcm = bytes(range(256)) * 200  # 51,200 bytes = 5 blocks
        s = bg00_stream.build_stream(adpcm)
        self.assertEqual(s[:4], b"BG00")
        self.assertEqual(struct.unpack_from("<IIII", s, 4), (0x40, 1, 0, 0x2800))
        for at in (0x40, 0x70):
            self.assertEqual(s[at:at + 4], b"VAGp")
            self.assertEqual(struct.unpack_from(">II", s, at + 12), (len(adpcm), 44100))
        blocks = -(-len(adpcm) // 0x2800)
        self.assertEqual(len(s), 0x800 + 2 * blocks * 0x2800)
        self.assertEqual(s[0x800:0x800 + 0x2800], s[0x3000:0x3000 + 0x2800])
        self.assertEqual(s[0x800:0x800 + 0x2800], adpcm[:0x2800])


if __name__ == "__main__":
    unittest.main()
