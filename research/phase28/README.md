# Phase 28 — XTC graze sound and rank glow (2026-11-25)

## Graze sound: already on the disc (K49)

Black Label's graze test plays sound 89 on every graze (`0C06F10E`: `0C0C20A0(side, 89)`). That routine only queues
the code in a request table (`0C28EC84 + code`), exactly like the PS2's `0x001372B0(side, code)` (`0x00497650 +
code`; the PS2 extend sound is `0x001372B0(side, 98)` at `0x0013AC84`).

* **Arcade:** a MAME probe (`ymzreq.lua`-style: write the request byte during a game, log the YMZ770 channels) shows
  code 89 starting **phrase 89** one frame later. Sound codes are phrase numbers. Phrase 89 decodes
  (`patcher/amm_decode.py`) to 7,008 samples at 16 kHz (0.44 s).
* **PS2:** the sound-effect bank is resource-archive entry **1129** (`IBARAR.PDM`, loaded at `0x0010FAE0`): header
  `SE00`, 0x800, 129 entries, then (start, end) pairs; each entry is a VAGp sample (16 kHz). The player
  `0x0010F620` maps a code to an entry: e = code − 57; if e ≥ 71, e −= 2; then if e ≥ 101, e −= 5; then if e ≥ 104,
  e −= 1 (gaps where the arcade has codes the port dropped). Code 89 → **entry 32**: 7,056 samples, 0.44 s.
* **Same sound:** cross-correlation 0.968 at a lag of 229 samples (the MPEG decoder delay), spectral correlation
  0.964. The port kept BL's/Ibara's graze sample and never played it.

`ps2/hooks/xtc.c` now queues code 89 for the side on every graze. Check in PCSX2 (release builds have no WAV dump):
with the test define `BL_TEST_XTC_POPUP` (one graze per frame while shot is held) the SPU2 savestate's voice state
(`SPU2.bin`: id, 64 KiB registers, 2 MiB sound RAM at 0x10004, then `V_Core[2]`) holds a voice whose start address
is sample 32's (SPU byte 0x43CA0) and whose play address moves between two savestates; none after the shot is
released, and none in an Arrange game.

## Rank glow (not built)

`0C0713F2`-`0C071500`, after the graze sphere, while player `+0x289` (pods deployed) is non-zero:

* Drawn only when `2 × ((0xFFFFFF − stored rank) >> 16) − 255 ≥ 0`, i.e. in the harder half of the rank range
  (stored rank below ~0x800000). At the stage-1 rank of a normal run (~0xE00000) it never shows.
* A level 0-15 from the rank term and a per-player byte (+0x274; 0x42–0xBE in the runs below, not decoded yet),
  clamped at 15; the colour word `0x02070000 | …` mixes the rank into the tint. (Read from the listing only; to be
  confirmed with the draw-op capture before porting.)
* Four quadrant descriptors `0C1752A8[level × 4 + q]`, sprite ids from `0C1754E8[(~(frame >> 2) & 7) | level << 3]`
  (8 animation frames), offsets from `0C1754E0[kind]` as the sphere.
* What it looks like: MAME `-nodrc` (the code patch `0C0713F6` → `sett`, skip, is not seen by the recompiler),
  rank held at 0x300000, the same frame with and without: a faint additive ring about 68 px across around the ship,
  orange at this rank, with a cross pattern.

Porting it is the same kind of work as the graze sphere (phase 21): capture the 8 frames × 16 levels of quadrant
art from the ROM into the atlas, then draw four sprites from the HUD pass. Open questions: the texture budget for
the frames (64 × 64 per frame before quadrant mirroring) and whether the PS2's additive blend matches.
