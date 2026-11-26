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

### Volume and cadence (K57, hardware report: "I don't hear a graze sound")

PS2 sound driver (0x001374A0, every frame): a request byte per code (0x00497650 + code, set by 0x001372B0) starts
the code on one of channels 3–7 by priority (0x00497450 + code), unless its cooldown (0x00497350 + code) is running;
the volume byte comes from 0x00497550 + code when it plays. Code 89: cooldown 6, priority 96, **volume 18**.

BL (MAME, `bl_sound_log.lua`: stage 1, invincible, shot held; YMZ770 save items per frame): phrase 89 plays at
volume2 **28** and restarts every 6 frames while grazing (76 of 119 restarts 6 frames apart, most others 12), the
same cadence as the PS2's cooldown. Over the 25 sounds both games play, PS2 volume / BL volume has a median of ~1.4;
code 89 is 0.64, so the PS2's graze sound is about half as loud as BL's relative to everything else. Noir writes 40
(28 × 1.4) to code 89's volume byte when it queues a graze; leaving Noir puts 18 back (retail also uses code 89, in
the bomb code at 0x0012A924 / 0x0012ABD0).

## Rank glow (K50)

BL `0C0713F2`-`0C071500`, inside the routine that draws the graze sphere (so only while the shot is held, held count
player `+0x270` > 0), when pods are deployed (`+0x289`):

* **Rank gate and tint.** h = (0xFFFFFF − stored rank) >> 16. Drawn only when 2h − 255 ≥ 0 (the harder half of the
  rank range). Tint R = 2h − 255, G = 510 − 2h, B = 0 (green at the gate, red at rank 0).
* **Level** = min(15, held × (h >> 4) >> 3): levels 8–15 with the shot held 8 frames; lower levels only in the first
  frames of a press.
* **Strength** (`+0x274`, the alpha of both blend factors): a graze ORs 0x8000 into it (`0C06F0DE`); the per-frame
  update (`0C07114E`) adds 16 (max 0xC0) when that flag is set, otherwise takes 2 off (min 0). Grazes are tested on
  alternate frames, so it sits at 0xBE / 0xC0 while grazing steadily.
* **Sprites.** Four quadrants around the sphere's centre + 1 px along game x: quadrant 0 right / +y, 1 right / −y
  (flip y, attr 0x400), 2 left / +y (flip x, 0x800), 3 both; blend attr 0x307 (PS2 flags `0x12070000`). Each level
  has 8 quadrant frames (32 × 32 for levels 8–11, 40 × 40 for 12–15; levels 10 and 11 share theirs), all in the ROM
  block x 0x1500–0x16FF, y 0x700–0x7FF; quadrants 1 and 2 show frame seq[p], quadrants 0 and 3 seq[7 − p],
  p = (~(frame >> 2)) & 7. BL draws each frame in up to four pieces; the pieces tile the whole square.

**How it was found.** `glow_log.lua`-style MAME runs: the same session with and without the branch at `0C0713F6`
forced to skip (`-nodrc`; the recompiler ignores the code patch) gives the glow as the frame difference and as the
extra blitter ops. `glow_cap.lua` (rank held per level, `+0x274` = 0xC0, `+0x289` = 3) logged 32 frames per level;
the per-(level, phase, quadrant) tiles are in `glow_tiles.json` (coordinates only). Levels 8 and 9 missed two or
three phases in the capture; their order follows the identity pattern of the captured phases (as levels 10–11).

**PS2.** 56 distinct tiles (24 small, 32 large, 75,776 px) do not fit the free space of the existing pages, so:

* the select art moved off page 5 (it fits pages 0–4, 6, 7), making page 5 — the rank bar's always-registered object
  — the in-game page: rank bar (rows 0–17, cols 0–79), 19 small glow tiles, sphere, XTC digits;
* the art segment grows from 8 to 10 pages (`0x01F20000`–`0x01FBFFFF`; RAM there was zero in every savestate);
  pages 8 and 9 hold the other 32 large and 5 small tiles and are registered in-game as objects 1113 and 1115 under
  the empty texture-table row 6, columns 8 and 9 (`ps2/hooks/bl_tex.c`);
* `research/phase20/make_select_data.py` places the tiles and generates `ps2/hooks/bl_glow_data.c`; the patcher
  copies the pixels from the user's ROM with the rest of the atlas;
* `xtc.c` keeps the strength per side (`xtc_glow`), `bl_rankbar.c` `bl_glow()` draws after the sphere, with PS2 pods
  (`+0x27B`) for BL's `+0x289`.

**Levels below 8** (`glow_cap_low.lua`, held count forced): BL draws the glow only from a held count of 4, so levels
4–7 appear on frames 4–7 of a press. Level 7 uses exactly level 9's frames (same order) and is now drawn; levels 4–5
(24 × 24) and 6 (32 × 32) have art of their own (≈17,400 px) that would need a third extra texture page, and no
texture object slot is left — not drawn (at most frames 4–6 of a press). PCSX2 (test defines `BL_TEST_XTC_POPUP`,
`BL_TEST_GLOW_LEVELS`: rank stepped through levels 8–15, pod check off): the ring is drawn around the ship with the
cross pattern, seamless quadrants, red at the top levels and green at level 8, as BL.
