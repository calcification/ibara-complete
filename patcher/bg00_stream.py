#!/usr/bin/env python3
"""Build a PS2 Ibara BGM stream ("BG00", as the 16 tracks in IBARAR.PDM) from 16-bit PCM. Standard library only.

Layout (read from the retail tracks): a 0x40-byte BG00 header ("BG00", 0x40, 1, 0, 0x2800), the left and right
"VAGp" headers (version 0x20, per-channel data bytes and the rate, big-endian; name "sdbgstrm.tmp"), zeros up to
0x800; then Sony 4-bit ADPCM, 0x2800-byte blocks alternating left / right, each channel starting with a zero
frame and ending with an end frame (flag 1) and a terminator frame (flag 7); 44,100 Hz stereo. The entry is
0x800 + 2 * ceil(bytes / 0x2800) * 0x2800 bytes. The game loops a track by restarting it (its track record).
"""
from __future__ import annotations

import math
import struct

RATE = 44100
BLOCK = 0x2800
FILTERS = ((0.0, 0.0), (60 / 64, 0.0), (115 / 64, -52 / 64), (98 / 64, -55 / 64), (122 / 64, -60 / 64))


def resample(pcm: list[int], src: int, dst: int = RATE, taps: int = 4) -> list[float]:
    """Lanczos resampling (a = taps) of mono PCM; returns floats in sample units."""
    n_out = int(len(pcm) * dst / src)
    ratio = src / dst
    out = [0.0] * n_out
    n_in = len(pcm)
    for i in range(n_out):
        x = i * ratio
        k0 = int(x)
        acc = wsum = 0.0
        for k in range(k0 - taps + 1, k0 + taps + 1):
            d = x - k
            if d == 0:
                w = 1.0
            elif abs(d) < taps:
                pd = math.pi * d
                w = taps * math.sin(pd) * math.sin(pd / taps) / (pd * pd)
            else:
                continue
            if 0 <= k < n_in:
                acc += pcm[k] * w
            wsum += w
        out[i] = acc / wsum if wsum else 0.0
    return out


def encode_adpcm(samples: list[float]) -> bytes:
    """Sony 4-bit ADPCM, 28 samples per 16-byte frame, starting with a zero frame and ending with the end and
    terminator frames (flags 1, 7)."""
    out = bytearray(16)  # leading zero frame
    s1 = s2 = 0.0
    n = len(samples)
    for start in range(0, n, 28):
        blk = [max(-32768.0, min(32767.0, v)) for v in samples[start:start + 28]]
        blk += [0.0] * (28 - len(blk))
        best = None
        for fi, (c1, c2) in enumerate(FILTERS):
            # choose the shift from the residual peak, then quantise with real feedback
            p1, p2, peak = s1, s2, 0.0
            for v in blk:
                r = v - (c1 * p1 + c2 * p2)
                peak = max(peak, abs(r))
                p2, p1 = p1, v
            shift = 12
            while shift > 0 and peak > (7 << (12 - shift)) - 0.5:
                shift -= 1
            p1, p2, err = s1, s2, 0.0
            nib = []
            for v in blk:
                pred = c1 * p1 + c2 * p2
                q = int(round((v - pred) / (1 << (12 - shift))))
                q = -8 if q < -8 else 7 if q > 7 else q
                dec = q * (1 << (12 - shift)) + pred
                dec = -32768.0 if dec < -32768 else 32767.0 if dec > 32767 else dec
                err += (dec - v) ** 2
                nib.append(q & 15)
                p2, p1 = p1, dec
            if best is None or err < best[0]:
                best = (err, fi, shift, nib, p1, p2)
        _err, fi, shift, nib, s1, s2 = best
        frame = bytearray(16)
        frame[0] = (fi << 4) | shift
        for i in range(14):
            frame[2 + i] = nib[2 * i] | (nib[2 * i + 1] << 4)
        out += frame
    out[-16 + 1] = 1  # the last data frame ends the sound
    out += bytes([0x11, 0x07]) + bytes(14)
    return bytes(out)


def decode_adpcm(data: bytes) -> list[int]:
    """Decode Sony 4-bit ADPCM (for checks)."""
    out = []
    s1 = s2 = 0.0
    for f in range(0, len(data) - 15, 16):
        fi, shift, flags = data[f] >> 4, data[f] & 15, data[f + 1]
        if flags == 7:
            break
        c1, c2 = FILTERS[fi] if fi < 5 else (0.0, 0.0)
        for b in data[f + 2:f + 16]:
            for q in (b & 15, b >> 4):
                q = q - 16 if q > 7 else q
                v = q * (1 << (12 - shift)) + c1 * s1 + c2 * s2
                v = -32768.0 if v < -32768 else 32767.0 if v > 32767 else v
                out.append(int(v))
                s2, s1 = s1, v
    return out


def vag_header(nbytes: int) -> bytes:
    return (b"VAGp" + struct.pack(">IIII", 0x20, 0, nbytes, RATE) + bytes(12) + b"sdbgstrm.tmp" + bytes(4))


def build_stream(adpcm: bytes) -> bytes:
    """A stereo BG00 entry with the same ADPCM in both channels."""
    n = len(adpcm)
    blocks = (n + BLOCK - 1) // BLOCK
    head = bytearray(0x800)
    head[0:0x14] = b"BG00" + struct.pack("<IIII", 0x40, 1, 0, BLOCK)
    head[0x40:0x70] = vag_header(n)
    head[0x70:0xA0] = vag_header(n)
    body = bytearray()
    for b in range(blocks):
        chunk = adpcm[b * BLOCK:(b + 1) * BLOCK].ljust(BLOCK, b"\0")
        body += chunk + chunk
    return bytes(head + body)


def stream_from_pcm(pcm: list[int], rate: int, gain: float = 1.0) -> bytes:
    up = resample(pcm, rate, RATE)
    if gain != 1.0:
        up = [v * gain for v in up]
    return build_stream(encode_adpcm(up))
