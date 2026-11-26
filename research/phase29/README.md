# Phase 29 — Hadou drops (K56, 2026-11-26)

**The Hadou** is the bomb button held 16 frames with a full bomb in stock, then released (ibara360 notes, "the same code
in both games"): a charging column, then a blast. Its player projectiles are type 1 / 2 (side + 1; subtypes are its
phases and trail pieces). Normal bombs are records of the ship's bomb kind (3, 5, 6, 7), which end as type-0
explosions; 9 / 10 are the bomb's flash records.

**Black Label (MAME, `bl_items.lua`: stage 1, straight A, invincible, shot held, rank held 0x600000, 3 bombs).** Item
spawns (BL pool `0C3BC7CC`, 0x60 records, +4 type, +8 subtype; pickup dispatcher `0C07E160`: 2 fragment, 3 medal, 7
rose) in the 240 frames after the action:

| Action | Items |
|---|---|
| bomb (tap) | 11 roses (7), 1 type 0 |
| Hadou (held 140 frames) | no roses: 1 medal, 1 option (1/5), 2 type 0 |

**PS2.** Cancels go through `0x0012AE40`-`0x0012AF40` (phase 9): Arcade makes a rose for every cancel (`0x00121FC0`
selector 1); Arrange (`$gp-28076`) makes a medal for types 1 / 2 subtype 1 (selector 2), nothing for their other subtypes,
nothing for types 0 / 9 / 10, a rose for the rest. Noir ran Arcade's rule. PCSX2 test build `BL_ITEM_LOG`
(`ps2/hooks/xtc.c`: new items, new player projectiles of types other than 0 / 3, and button changes logged at
0x01FD0000; bombs kept at 3), Noir stage 1, ~20 s in:

| Noir build | Hadou: items during charge / 200 frames after release | Tap bomb: items in 200 frames |
|---|---|---|
| retail rule (Arcade) | 4 roses + 1 medal / **17 roses**, 1 medal, 1 option, 2 type 0 | 6 roses, 1 medal, 1 type 0 |
| Arrange's whole branch | — / medals only | **no roses** (the bomb's roses come from its type-0 explosions, which Arrange drops) |
| **K56** (Arrange's rule for types 1 / 2 only) | 1 medal / **no roses**, 3 medals, 1 type 0 | 6 roses, 1 medal, 1 type 0 |

So BL treats the Hadou like PS2 Arrange and everything else like Arcade. Noir (KURO runtime table only):
`0x0012AE50` `lw v1,$gp-28076` → `li v1,1` (into the branch that tests types 1 / 2) and `0x0012AE70`
`beqz a0,0x0012AF20` → `b 0x0012AF38` (every type but 1 / 2 → Arcade's rose call). Rank follows: the Hadou no longer
eases rank through roses, its medals harden it, as in BL (phase 24).

Note: without a bomb in stock after the press, holding the button fires a normal bomb and no Hadou (the first PS2
tests here); with bombs in stock, Noir's Hadou charges and fires as BL's.
