# Phase 34 — Stage-6 first core (Claude, 26 November 2026, in progress)

Same 359 HP in both games, but the first core lasts ~5,660 frames in BL (17 seeded runs, 4,964–6,552) against
~3,620 ticks on the PS2 (6 runs, 3,004–3,936). Rank 0x800000, shot level 2, stationary player, as phase 33.

## HP over time (BL checkpoint replay vs PS2 mode-3 seed 7)

| Frames after the core appears | BL HP | PS2 HP |
|---|---:|---:|
| 400 | 358 | 354 |
| 1,000 | 358 | 284 |
| 1,400 | 358 | 237 |
| 2,000 | 338 | 166 |
| 3,000 | 307 | 81 |
| 3,800 | 250 | 0 |

The core sits at the same place (x 240, y 512 from frame 400) and moves alike in both. BL's core flag word is
D3008100 throughout (no invulnerable window).

## Parts (type 74) during the first core

`bl_stage_log.lua PARTS=1` (BL) and `BL_PART_STATS` (PS2): spawns and HP lost per subtype.

| Subtype | BL spawns / HP lost / start HP | PS2 spawns / HP lost / start HP |
|---|---|---|
| 0x10 | 5 / 215 / 71 | 5 / 195 / 71 |
| 0x11 | 9 / 291 / 71 | 8 / 363 / 71 |
| 0x12–0x18 | start HP 40 / 37 | start HP 27 |
| 0x18 | 9 / 97 | 6 / 48 |
| 0x1A–0x1F | start HP ~71, appear ~2,020 after the core | start HP 71, appear ~2,044 after |
| 0x20 | 16 / **359** / 66 | 15 / **254** / 71 |
| 0x28 | 10 / 179 / 43 | 13 / 174 / 43 |
| 0x29 | start HP 23 | start HP 13 |

The shields (0x10, 0x11, 0x28) exist and absorb about the same in both. In BL the 0x20 parts lose exactly the core's
359 HP, and the core only starts dropping once they appear: BL's core seems to take its damage through the linked
0x20 parts, hardly directly. The PS2's core is hit directly from the start.

## BL damage function (0C0A8E90) vs PS2 (0x001278B0)

* Parent links: both follow +0x7C while flag 0x4000 is set.
* Both refuse damage with flag 0x20000000, and for parts past x 0x120 unless a global is set.
* BL only: no damage when the part's HP ≤ 14 and bit 15 of (caller's mask & part flags) is set (0C0A8F5A). The PS2
  creates parts without bit 0x8000 (e.g. rose linked part BL 0xD300C100 vs PS2 0xD3004100). Not the core's cause
  (HP 359), but a real difference.

## Next

Compare the core's own hit area / collision settings, then trace which part each player hit lands on (Codex's
`research/phase31/bl_contacts.lua`).
