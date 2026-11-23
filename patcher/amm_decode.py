#!/usr/bin/env python3
"""Decode a Yamaha YMZ770 "AMM" phrase (Cave CV1000 sound ROMs) to 16-bit PCM. Python standard library only.

A port of MAME's mpeg_audio (layer II / AMM part) and of the phrase lookup in MAME's ymz770 device:

    mpeg_audio.cpp  license: BSD-3-Clause, copyright-holders: Olivier Galibert
    ymz770.cpp      license: BSD-3-Clause, copyright-holders: Olivier Galibert, R. Belmont, MetalliC

    Redistribution and use in source and binary forms, with or without modification, are permitted provided that
    the following conditions are met: (1) Redistributions of source code must retain the above copyright notice,
    this list of conditions and the following disclaimer. (2) Redistributions in binary form must reproduce the
    above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other
    materials provided with the distribution. (3) Neither the name of the copyright holder nor the names of its
    contributors may be used to endorse or promote products derived from this software without specific prior
    written permission. THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS
    OR IMPLIED WARRANTIES ... ARE DISCLAIMED. (Full text: https://opensource.org/license/bsd-3-clause)

The sound ROM is the board's two chips u23 + u24 concatenated with each 16-bit word byte-swapped (MAME loads them
ROM_LOAD16_WORD_SWAP). Phrase p: table entry at 4 p (top nibble of byte 0 bits 4-6 = atbl, bytes 1-3 = offset).
"""
from __future__ import annotations

import math
import struct

SAMPLE_RATES = (44100, 48000, 32000, 0, 22050, 24000, 16000, 0)
TOTAL_BANDS = (27, 30, 8, 12, 30)
JOINT_BANDS = (4, 8, 12, 16)

_V1 = (0, 1, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17)
_V2 = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 17)
_V3 = (0, 1, 2, 3, 4, 5, 6, 17)
_V4 = (0, 1, 2, 17)
_V5 = (0, 1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)
_V6 = (0, 1, 2, 4, 5, 6, 7, 8)
_V7 = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)
_V8 = (0, 1, 2, 4)
_Z = (0,)
BAND_VALUES = (
    [_V1] * 3 + [_V2] * 8 + [_V3] * 12 + [_V4] * 4 + [_Z] * 5,
    [_V1] * 3 + [_V2] * 8 + [_V3] * 12 + [_V4] * 7 + [_Z] * 2,
    [_V5] * 2 + [_V6] * 6 + [_Z] * 24,
    [_V5] * 2 + [_V6] * 10 + [_Z] * 20,
    [_V7] * 4 + [_V6] * 7 + [_V8] * 19 + [_Z] * 2,
)
BAND_BITS = (
    (4,) * 11 + (3,) * 12 + (2,) * 4 + (0,) * 5,
    (4,) * 11 + (3,) * 12 + (2,) * 7 + (0,) * 2,
    (4, 4) + (3,) * 6 + (0,) * 24,
    (4, 4) + (3,) * 10 + (0,) * 20,
    (4,) * 4 + (3,) * 7 + (2,) * 19 + (0,) * 2,
)
# band infos: modulo, bits, cube_bits, scale, offset
BAND_INFO = [(0, 0, 0, 0.0, 0.0)] + [
    (m, b, cb, 1 / (1 - r), o) for m, b, cb, r, o in (
        (0x0003, 2, 5, 1.0 / 4, 1.0 / 2), (0x0005, 3, 7, 3.0 / 8, 1.0 / 2), (0x0007, 3, 9, 1.0 / 8, 1.0 / 4),
        (0x0009, 4, 10, 7.0 / 16, 1.0 / 2), (0x000f, 4, 12, 1.0 / 16, 1.0 / 8), (0x001f, 5, 15, 1.0 / 32, 1.0 / 16),
        (0x003f, 6, 18, 1.0 / 64, 1.0 / 32), (0x007f, 7, 21, 1.0 / 128, 1.0 / 64),
        (0x00ff, 8, 24, 1.0 / 256, 1.0 / 128), (0x01ff, 9, 27, 1.0 / 512, 1.0 / 256),
        (0x03ff, 10, 30, 1.0 / 1024, 1.0 / 512), (0x07ff, 11, 33, 1.0 / 2048, 1.0 / 1024),
        (0x0fff, 12, 36, 1.0 / 4096, 1.0 / 2048), (0x1fff, 13, 39, 1.0 / 8192, 1.0 / 4096),
        (0x3fff, 14, 42, 1.0 / 16384, 1.0 / 8192), (0x7fff, 15, 45, 1.0 / 32768, 1.0 / 16384),
        (0xffff, 16, 48, 1.0 / 65536, 1.0 / 32768))]
SCALEFACTORS = [2.0 * 2 ** (-i / 3) for i in range(63)] + [0.0]

# MPEG-1 synthesis window (ISO 11172-3 table 3-B.3 "D"), as in mpeg_audio.cpp
WINDOW = (
    0.000000000, -0.000015259, -0.000015259, -0.000015259, -0.000015259, -0.000015259, -0.000015259, -0.000030518,
    -0.000030518, -0.000030518, -0.000030518, -0.000045776, -0.000045776, -0.000061035, -0.000061035, -0.000076294,
    -0.000076294, -0.000091553, -0.000106812, -0.000106812, -0.000122070, -0.000137329, -0.000152588, -0.000167847,
    -0.000198364, -0.000213623, -0.000244141, -0.000259399, -0.000289917, -0.000320435, -0.000366211, -0.000396729,
    -0.000442505, -0.000473022, -0.000534058, -0.000579834, -0.000625610, -0.000686646, -0.000747681, -0.000808716,
    -0.000885010, -0.000961304, -0.001037598, -0.001113892, -0.001205444, -0.001296997, -0.001388550, -0.001480103,
    -0.001586914, -0.001693726, -0.001785278, -0.001907349, -0.002014160, -0.002120972, -0.002243042, -0.002349854,
    -0.002456665, -0.002578735, -0.002685547, -0.002792358, -0.002899170, -0.002990723, -0.003082275, -0.003173828,
    0.003250122, 0.003326416, 0.003387451, 0.003433228, 0.003463745, 0.003479004, 0.003479004, 0.003463745,
    0.003417969, 0.003372192, 0.003280640, 0.003173828, 0.003051758, 0.002883911, 0.002700806, 0.002487183,
    0.002227783, 0.001937866, 0.001617432, 0.001266479, 0.000869751, 0.000442505, -0.000030518, -0.000549316,
    -0.001098633, -0.001693726, -0.002334595, -0.003005981, -0.003723145, -0.004486084, -0.005294800, -0.006118774,
    -0.007003784, -0.007919312, -0.008865356, -0.009841919, -0.010848999, -0.011886597, -0.012939453, -0.014022827,
    -0.015121460, -0.016235352, -0.017349243, -0.018463135, -0.019577026, -0.020690918, -0.021789550, -0.022857666,
    -0.023910522, -0.024932861, -0.025909424, -0.026840210, -0.027725220, -0.028533936, -0.029281616, -0.029937744,
    -0.030532837, -0.031005860, -0.031387330, -0.031661987, -0.031814575, -0.031845093, -0.031738280, -0.031478880,
    0.031082153, 0.030517578, 0.029785156, 0.028884888, 0.027801514, 0.026535034, 0.025085450, 0.023422241,
    0.021575928, 0.019531250, 0.017257690, 0.014801025, 0.012115479, 0.009231567, 0.006134033, 0.002822876,
    -0.000686646, -0.004394531, -0.008316040, -0.012420654, -0.016708374, -0.021179200, -0.025817871, -0.030609130,
    -0.035552980, -0.040634155, -0.045837402, -0.051132202, -0.056533813, -0.061996460, -0.067520140, -0.073059080,
    -0.078628540, -0.084182740, -0.089706420, -0.095169070, -0.100540160, -0.105819700, -0.110946655, -0.115921020,
    -0.120697020, -0.125259400, -0.129562380, -0.133590700, -0.137298580, -0.140670780, -0.143676760, -0.146255500,
    -0.148422240, -0.150115970, -0.151306150, -0.151962280, -0.152069090, -0.151596070, -0.150497440, -0.148773200,
    -0.146362300, -0.143264770, -0.139450070, -0.134887700, -0.129577640, -0.123474120, -0.116577150, -0.108856200,
    0.100311280, 0.090927124, 0.080688480, 0.069595340, 0.057617188, 0.044784546, 0.031082153, 0.016510010,
    0.001068115, -0.015228271, -0.032379150, -0.050354004, -0.069168090, -0.088775635, -0.109161380, -0.130310060,
    -0.152206420, -0.174789430, -0.198059080, -0.221984860, -0.246505740, -0.271591200, -0.297210700, -0.323318480,
    -0.349868770, -0.376800540, -0.404083250, -0.431655880, -0.459472660, -0.487472530, -0.515609740, -0.543823240,
    -0.572036740, -0.600219700, -0.628295900, -0.656219500, -0.683914200, -0.711318970, -0.738372800, -0.765029900,
    -0.791214000, -0.816864000, -0.841949460, -0.866363500, -0.890090940, -0.913055400, -0.935195900, -0.956481930,
    -0.976852400, -0.996246340, -1.014617900, -1.031936600, -1.048156700, -1.063217200, -1.077117900, -1.089782700,
    -1.101211500, -1.111373900, -1.120224000, -1.127746600, -1.133926400, -1.138763400, -1.142211900, -1.144287100,
    1.144989000, 1.144287100, 1.142211900, 1.138763400, 1.133926400, 1.127746600, 1.120224000, 1.111373900,
    1.101211500, 1.089782700, 1.077117900, 1.063217200, 1.048156700, 1.031936600, 1.014617900, 0.996246340,
    0.976852400, 0.956481930, 0.935195900, 0.913055400, 0.890090940, 0.866363500, 0.841949460, 0.816864000,
    0.791214000, 0.765029900, 0.738372800, 0.711318970, 0.683914200, 0.656219500, 0.628295900, 0.600219700,
    0.572036740, 0.543823240, 0.515609740, 0.487472530, 0.459472660, 0.431655880, 0.404083250, 0.376800540,
    0.349868770, 0.323318480, 0.297210700, 0.271591200, 0.246505740, 0.221984860, 0.198059080, 0.174789430,
    0.152206420, 0.130310060, 0.109161380, 0.088775635, 0.069168090, 0.050354004, 0.032379150, 0.015228271,
    -0.001068115, -0.016510010, -0.031082153, -0.044784546, -0.057617188, -0.069595340, -0.080688480, -0.090927124,
    0.100311280, 0.108856200, 0.116577150, 0.123474120, 0.129577640, 0.134887700, 0.139450070, 0.143264770,
    0.146362300, 0.148773200, 0.150497440, 0.151596070, 0.152069090, 0.151962280, 0.151306150, 0.150115970,
    0.148422240, 0.146255500, 0.143676760, 0.140670780, 0.137298580, 0.133590700, 0.129562380, 0.125259400,
    0.120697020, 0.115921020, 0.110946655, 0.105819700, 0.100540160, 0.095169070, 0.089706420, 0.084182740,
    0.078628540, 0.073059080, 0.067520140, 0.061996460, 0.056533813, 0.051132202, 0.045837402, 0.040634155,
    0.035552980, 0.030609130, 0.025817871, 0.021179200, 0.016708374, 0.012420654, 0.008316040, 0.004394531,
    0.000686646, -0.002822876, -0.006134033, -0.009231567, -0.012115479, -0.014801025, -0.017257690, -0.019531250,
    -0.021575928, -0.023422241, -0.025085450, -0.026535034, -0.027801514, -0.028884888, -0.029785156, -0.030517578,
    0.031082153, 0.031478880, 0.031738280, 0.031845093, 0.031814575, 0.031661987, 0.031387330, 0.031005860,
    0.030532837, 0.029937744, 0.029281616, 0.028533936, 0.027725220, 0.026840210, 0.025909424, 0.024932861,
    0.023910522, 0.022857666, 0.021789550, 0.020690918, 0.019577026, 0.018463135, 0.017349243, 0.016235352,
    0.015121460, 0.014022827, 0.012939453, 0.011886597, 0.010848999, 0.009841919, 0.008865356, 0.007919312,
    0.007003784, 0.006118774, 0.005294800, 0.004486084, 0.003723145, 0.003005981, 0.002334595, 0.001693726,
    0.001098633, 0.000549316, 0.000030518, -0.000442505, -0.000869751, -0.001266479, -0.001617432, -0.001937866,
    -0.002227783, -0.002487183, -0.002700806, -0.002883911, -0.003051758, -0.003173828, -0.003280640, -0.003372192,
    -0.003417969, -0.003463745, -0.003479004, -0.003479004, -0.003463745, -0.003433228, -0.003387451, -0.003326416,
    0.003250122, 0.003173828, 0.003082275, 0.002990723, 0.002899170, 0.002792358, 0.002685547, 0.002578735,
    0.002456665, 0.002349854, 0.002243042, 0.002120972, 0.002014160, 0.001907349, 0.001785278, 0.001693726,
    0.001586914, 0.001480103, 0.001388550, 0.001296997, 0.001205444, 0.001113892, 0.001037598, 0.000961304,
    0.000885010, 0.000808716, 0.000747681, 0.000686646, 0.000625610, 0.000579834, 0.000534058, 0.000473022,
    0.000442505, 0.000396729, 0.000366211, 0.000320435, 0.000289917, 0.000259399, 0.000244141, 0.000213623,
    0.000198364, 0.000167847, 0.000152588, 0.000137329, 0.000122070, 0.000106812, 0.000106812, 0.000091553,
    0.000076294, 0.000076294, 0.000061035, 0.000061035, 0.000045776, 0.000045776, 0.000030518, 0.000030518,
    0.000030518, 0.000030518, 0.000015259, 0.000015259, 0.000015259, 0.000015259, 0.000015259, 0.000015259,
)


class BitReader:
    __slots__ = ("data", "pos", "limit")

    def __init__(self, data: bytes, pos: int, limit: int):
        self.data, self.pos, self.limit = data, pos, limit

    def gb(self, n: int) -> int:
        if self.pos + n > self.limit:
            raise EOFError
        v = 0
        d, p = self.data, self.pos
        for _ in range(n):
            v = (v << 1) | ((d[p >> 3] >> (7 - (p & 7))) & 1)
            p += 1
        self.pos = p
        return v


class AmmDecoder:
    def __init__(self, rom: bytes, window: list[float] | None = None):
        self.rom = rom
        self.cos = [[math.cos(i * (2 * j + 1) * math.pi / 64) for j in range(32)] for i in range(32)]
        self.win = list(window if window is not None else WINDOW)
        self.buf = [[0.0] * (32 * 32) for _ in range(2)]
        self.bpos = [16 * 32, 16 * 32]

    # one frame (1152 samples per channel, fewer at the end of a phrase); returns (samples, rate, channels) or None
    def frame(self, br: BitReader, atbl: int):
        sync = br.gb(12)
        while sync != 0xFFF:
            sync = ((sync << 1) | br.gb(1)) & 0xFFF
        while True:
            variant = br.gb(3)
            if variant in (2, 6):
                break
            br.pos -= 3
            sync = ((sync << 1) | br.gb(1)) & 0xFFF
            while sync != 0xFFF:
                sync = ((sync << 1) | br.gb(1)) & 0xFFF
        layer25 = variant == 2
        ammsl = br.gb(1)
        full_packets = br.gb(4)
        rate_index = br.gb(2) + 4 * layer25
        last_packet = br.gb(2)
        stereo_mode = br.gb(2)
        stereo_ext = br.gb(2)
        if ammsl:
            last_frame = 36
            param = atbl
            br.gb(3)
        else:
            last_frame = 3 * full_packets + last_packet
            param = br.gb(3)
        br.gb(1)
        nch = 2 if stereo_mode != 3 else 1
        total = TOTAL_BANDS[param]
        joint = total
        if stereo_mode == 1:
            joint = min(JOINT_BANDS[stereo_ext], total)
        # band params
        bp = [[0] * 32 for _ in range(2)]
        for band in range(total):
            bits = BAND_BITS[param][band]
            vals = BAND_VALUES[param][band]
            if band < joint:
                for ch in range(nch):
                    bp[ch][band] = vals[br.gb(bits)]
            else:
                v = vals[br.gb(bits)]
                bp[0][band] = bp[1][band] = v
        scfsi = [[0] * 32 for _ in range(2)]
        for band in range(total):
            for ch in range(nch):
                if bp[ch][band]:
                    scfsi[ch][band] = br.gb(2)
        scf = [[[0] * 32 for _ in range(3)] for _ in range(2)]
        for band in range(total):
            for ch in range(nch):
                if bp[ch][band]:
                    s = scfsi[ch][band]
                    if s == 0:
                        a, b, c = br.gb(6), br.gb(6), br.gb(6)
                    elif s == 1:
                        a = b = br.gb(6)
                        c = br.gb(6)
                    elif s == 2:
                        a = b = c = br.gb(6)
                    else:
                        a = br.gb(6)
                        b = c = br.gb(6)
                    scf[ch][0][band], scf[ch][1][band], scf[ch][2][band] = a, b, c
        if not last_frame:
            return [], SAMPLE_RATES[rate_index], nch
        amp = [[[SCALEFACTORS[scf[ch][step][band]] if bp[ch][band] else 0.0 for band in range(32)]
                for step in range(3)] for ch in range(2)]
        out: list[int] = []
        frame_number = 0
        bdata = [[[0.0] * 32 for _ in range(3)] for _ in range(2)]

        def triplet(ch, band):
            idx = bp[ch][band]
            if idx == 0:
                return 0.0, 0.0, 0.0
            modulo, bits, cube_bits, scale, offset = BAND_INFO[idx]
            if idx in (1, 2, 4):
                v = br.gb(cube_bits)
                b0 = v % modulo
                v //= modulo
                b1 = v % modulo
                v //= modulo
                b2 = v % modulo
            else:
                b0, b1, b2 = br.gb(bits), br.gb(bits), br.gb(bits)
            half = 1 << (bits - 1)
            return (((b0 - half) / half + offset) * scale, ((b1 - half) / half + offset) * scale,
                    ((b2 - half) / half + offset) * scale)

        for upper in range(3):
            for _middle in range(4):
                for band in range(32):
                    if band < joint:
                        for ch in range(nch):
                            t = triplet(ch, band)
                            a = amp[ch][upper][band]
                            bdata[ch][0][band], bdata[ch][1][band], bdata[ch][2][band] = t[0] * a, t[1] * a, t[2] * a
                    elif band < total:
                        t = triplet(0, band)
                        for ch in range(nch):
                            a = amp[ch][upper][band]
                            bdata[ch][0][band], bdata[ch][1][band], bdata[ch][2][band] = t[0] * a, t[1] * a, t[2] * a
                    else:
                        for ch in range(2):
                            bdata[ch][0][band] = bdata[ch][1][band] = bdata[ch][2][band] = 0.0
                for lower in range(3):
                    pcm = [self._synth(ch, bdata[ch][lower]) for ch in range(nch)]
                    if nch == 2:
                        for i in range(32):
                            out.append(pcm[0][i])
                            out.append(pcm[1][i])
                    else:
                        out.extend(pcm[0])
                    frame_number += 1
                    if frame_number == last_frame:
                        return out, SAMPLE_RATES[rate_index], nch
        return out, SAMPLE_RATES[rate_index], nch

    def _synth(self, ch: int, sub: list[float]) -> list[int]:
        buf, pos = self.buf[ch], self.bpos[ch]
        cos = self.cos
        for i in range(32):
            ci = cos[i]
            buf[pos + i] = sum(s * c for s, c in zip(sub, ci))
        base = pos + 16
        w = self.win
        res = [0.0] * 32
        for j in range(0, 512, 64):
            b = base + j
            for i in range(16):
                res[i] += buf[b + i] * w[i + j] - buf[b + 32 - i] * w[32 + i + j]
            res[16] -= buf[b + 16] * w[48 + j]
            for i in range(17, 32):
                res[i] -= buf[b + 32 - i] * w[i + j] + buf[b + i] * w[32 + i + j]
        out = []
        for v in res:
            v = v * 32768 + 0.5
            out.append(-32768 if v <= -32768 else 32767 if v >= 32767 else int(v))
        pos -= 32
        if pos < 0:
            buf[17 * 32:17 * 32 + 15 * 32] = buf[0:15 * 32]
            pos = 16 * 32
        self.bpos[ch] = pos
        return out


def sound_rom(u23: bytes, u24: bytes) -> bytes:
    """The YMZ770 ROM as MAME maps it: u23 then u24, every 16-bit word byte-swapped."""
    raw = u23 + u24
    sw = bytearray(len(raw))
    sw[0::2] = raw[1::2]
    sw[1::2] = raw[0::2]
    return bytes(sw)


def decode_phrase(rom: bytes, phrase: int, window: list[float] | None = None):
    """PCM (interleaved int16 list), sample rate, channels of a whole phrase (until its last, short frame)."""
    atbl = rom[4 * phrase] >> 4 & 7
    offset = rom[4 * phrase + 1] << 16 | rom[4 * phrase + 2] << 8 | rom[4 * phrase + 3]
    dec = AmmDecoder(rom, window)
    br = BitReader(rom, 8 * offset, len(rom) * 8)
    pcm: list[int] = []
    rate = nch = 0
    while True:
        try:
            samples, rate_f, nch_f = dec.frame(br, atbl)
        except EOFError:
            break
        if samples:
            pcm.extend(samples)
            rate, nch = rate_f, nch_f
        if len(samples) < 1152 * nch_f:
            break
    return pcm, rate, nch


def write_wav(path, pcm, rate, nch):
    with open(path, "wb") as f:
        data = struct.pack("<%dh" % len(pcm), *pcm)
        f.write(b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " +
                struct.pack("<IHHIIHH", 16, 1, nch, rate, rate * nch * 2, nch * 2, 16) + b"data" +
                struct.pack("<I", len(data)) + data)


if __name__ == "__main__":
    import sys
    import time
    u23, u24, phrase, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    t = time.time()
    rom = sound_rom(open(u23, "rb").read(), open(u24, "rb").read())
    pcm, rate, nch = decode_phrase(rom, phrase)
    write_wav(out, pcm, rate, nch)
    print(f"phrase {phrase}: {len(pcm) // max(nch, 1)} samples x {nch} ch at {rate} Hz "
          f"({len(pcm) / max(nch, 1) / max(rate, 1):.1f} s) in {time.time() - t:.1f} s")
