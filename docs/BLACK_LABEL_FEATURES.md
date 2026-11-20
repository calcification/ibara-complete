# Ibara Kuro: Black Label — feature specification for the PS2 port

What Black Label (BL) does differently from arcade Ibara, with BL arcade anchors. This is the checklist a
"BL mode" on the PS2 engine must reproduce. Sources: Phase 11 measured code delta, and behaviour that
ibara360's author recorded from live traces of the BL arcade program (cited as *ibara360 notes*; facts and
addresses only, no code). Addresses `0C......` are **arcade SH-3**; PS2 EE addresses appear only where
this repository verified them.

Confidence tags: **[spec]** behaviour documented by ibara360 notes from traces · **[delta]** measured by
Phase 11 · **[PS2]** PS2 counterpart known · **[todo]** PS2 counterpart not yet located.

## 1. Player systems

| # | Feature | BL arcade facts | PS2 status |
|---|---|---|---|
| F1 | **Ship select: straight / spread** per pilot | ship byte = side·8 + ship·4 + type (ibara: side·4 + type); ship-select screen holds invincibility at 240 while flag `0C3C86AC` ≠ 0 [spec] | [todo] new select screen; PS2 has pilot/type select only |
| F2 | **Weapon stock** replaces arcade L/R/B option slots | u32[7] at `0C22E028` (non-zero = owned, per side), current weapon = player `+0x26F`; HUD order M.G, 5WAY, GATLING / ROCKET, BURNAR, NAPALM / HOMING [spec] | [PS2] Arrange stores sub-weapons and offers them in BL's HUD order — closest base; mapping [todo] |
| F3 | **Weapon change button** (4th button) | extra input "WEAPON CHANGE" [spec] | [todo] PS2 pad bit free for it; Phase 6 masks `0x40/0x80/0x100` seen |
| F4 | **XTC — Xtreme Terror Counter** (graze) | graze test `0C06EF50`, timer `0C071110`; +10 score per bullet in box while shot held ≥5 frames, pods out, hittable; counter ≤ 9999 (quarters ≤ 39996); 128-frame wipe timer; bomb wipes 16 frames in; box 14+e+1 × 19+e+1, e = 4·held·rank_share px [spec] | [PS2] implemented as `ps2/hooks/xtc.c` (K01), build-only until fields located |
| F5 | **Shot levels** | top level 5, no full-power secret (ibara: 4 + secret) [spec] | [todo] |
| F6 | **Player record** | stride 0x2A0 (ibara 0x280, PS2 0x290); lives +0x25A, shot +0x25B, bombs +0x25D, fragments +0x25E, extend +0x294, invincibility +0x288 [spec] | PS2 keeps its own 0x290 record; BL-only state lives in the cave |
| F7 | **Bombs** | bomb spawn `0C073600` (ibara `0C062550`) [spec][delta]; blast length fixed by ship kind and power spent (straight A 103 frames, straight D 231, spread A ~201) [spec] | [todo] |
| F8 | **Rank** | same stored-rank format (0 hardest, 2^24 scale) at `0C297A3C` [spec]; BL lets bomb cancels lower rank, but rank climbs faster (README of ibara360, shmups.wiki) | [PS2] rank global `0x00338EB4`, Arrange already lowers rank on cancels (Phases 7–9); BL tuning [todo] |
| F9 | **Score items / medals** | same medal ladder concept; next medal `0C3C53E0`; item pickup routine BL-only `0C07D100` (arcade `0C06BB60`) [spec][delta] | [PS2] medal ladder `0x0020B100`, pickup table `0x0020BF60` |
| F10 | **Bullet cancel after a boss** | erases all enemy bullets [spec] | [todo] |

## 2. Game flow

| # | Feature | BL facts | PS2 status |
|---|---|---|---|
| G1 | No Normal/Harder/Extended modes; single loop of 6 stages, stage byte 2–7 | [spec] | PS2 Arcade has modes; BL mode forces one |
| G2 | Opening / stage record id 0 before stage 1 | `0C23E0A6` = 0 [spec] | [todo] |
| G3 | Start menu side select (1P/2P) | [spec] | [todo] |
| G4 | Music = Ibara's list minus "Show Time" (seq 15/16) | [spec] | [PS2] PS2 soundtrack already on disc |
| G5 | Bosses | run Ibara's boss code with Ibara's constants (checked constant by constant in ibara360 notes) [spec] | [PS2] reuse PS2 Arcade bosses; verify timing |
| G6 | Stage content (regular enemies, scripts) | ~288 changed routines touching enemy parts, ~17k-instruction delta [delta]; stage 1 boss arena at scroll 2449.25 [spec] | [todo] the bulk of the port |
| G7 | Enemy bullet pool | 256 × 0x54 at `0C297B40`; BL reaches the 256 cap at stage 1 boss [spec] | [PS2] pool `0x004682EC`, stride 0x54 (Phase 9) |

## 3. Presentation / assets

| # | Item | Source |
|---|---|---|
| A1 | BL title logo, ship-select art, straight/spread ship sprites, weapon icons, XTC digits/sphere | user's own `ibarablk` ROM (u2 NAND, CRC `5e46be44`), converted locally; never committed |
| A2 | Everything shared with Ibara | already on the PS2 disc (`IBARAR.PDM`, Phase 2 catalog) |
| A3 | Third menu entry | Phase 4 selector map; dormant button slot in PDM #946 |

## 4. Order of implementation (by risk retired per hour)

1. **C00** code-injection smoke test (proves the toolchain on real PS2 code).
2. Field discovery from savestates → unblock **K01 XTC** (self-contained, spec complete).
3. **F2/F3** weapon stock + change button on top of Arrange's sub-weapon store.
4. **F1** ship select + **F5/F7** shot/bomb tables.
5. **G6** stage-content delta, stage 1 first, ported routine by routine from the Phase 11 list after
   mapping arcade routines to PS2 routines (Phase 12 cross-ISA matcher, needs the ELF).
6. **G1–G3, A1–A3** mode entry, menus and art.
