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
| F1 | **Ship select: straight / spread** per pilot | ship byte = side·8 + ship·4 + type (ibara: side·4 + type); ship-select screen holds invincibility at 240 while flag `0C3C86AC` ≠ 0 [spec] | **Mechanics already on PS2 (Phase 13):** BL straight A–D = Bond's shots/speeds, spread A–D = Dyne's (shot table `0x00212E50`, speeds `0x00205F50`, exact match). To do: let the BL build choose pilot and kind separately (mechanics index = kind·4 + type) |
| F2 | **Weapon stock** replaces arcade L/R/B option slots | u32[7] at `0C22E028` (non-zero = owned, per side), current weapon = player `+0x26F`; HUD order M.G, 5WAY, GATLING / ROCKET, BURNAR, NAPALM / HOMING [spec] | [PS2] **Arrange already implements it** (static, `0x00139850`): player `+0x270` current weapon, `+0x271..0x277` owned flags (weapon ids 0 rocket, 1 burner, 2 gatling, 3 homing, 4 napalm, 5 MG, 6 5way), `+0x278` count owned (cycling needs ≥ 2), `+0x26D..0x26F` the three option slots set to the current weapon on a change; next-weapon table `0x00212FD0` = `[1,4,0,5,3,6,2]`, i.e. MG→5WAY→GATLING→ROCKET→BURNER→NAPALM→HOMING, **exactly BL's order**. The path is gated by the Arrange flag (`$gp-0x6DAC`, test at `0x001398CC`) |
| F3 | **Weapon change button** (4th button) | extra input "WEAPON CHANGE" [spec] | [PS2] Arrange's change is newly-pressed bit `0x40` at player `+0x24E` (`0x001398E4`), sound 74; **done in the BLACK LABEL build (K04):** input mapper uses the Arrange button config (button 0 = change), change code enabled in Arcade, formation change kept off |
| F4 | **XTC — Xtreme Terror Counter** (graze) | graze test `0C06EF50`, timer `0C071110`; +10 score per bullet in box while shot held ≥5 frames, pods out, hittable; counter ≤ 9999 (quarters ≤ 39996); 128-frame wipe timer; bomb wipes 16 frames in; box 14+e+1 × 19+e+1, e = 4·held·rank_share px [spec] | [PS2] `ps2/hooks/xtc.c` + HUD `xtc_hud.c`: runs in PCSX2 (K01–K03); +10/graze and box axes verified; bomb wipe done (K05); graze sphere still [todo] |
| F5 | **Shot levels** | top level 5, no full-power secret (ibara: 4 + secret) [spec] | shot patterns per level identical to PS2's (Phase 13); **done (K06):** small P raises to level 6, secret removed |
| F6 | **Player record** | stride 0x2A0 (ibara 0x280, PS2 0x290); lives +0x25A, shot +0x25B, bombs +0x25D, fragments +0x25E, extend +0x294, invincibility +0x288 [spec] | PS2 keeps its own 0x290 record; BL-only state lives in the cave |
| F7 | **Bombs** | bomb spawn `0C073600` (ibara `0C062550`) [spec][delta]; blast length fixed by ship kind and power spent (straight A 103 frames, straight D 231, spread A ~201) [spec] | [todo] |
| F8 | **Rank** | same stored-rank format (0 hardest, 2^24 scale) at `0C297A3C` [spec]; BL lets bomb cancels lower rank, but rank climbs faster (README of ibara360, shmups.wiki) | [PS2] rank global `0x00338EB4`, Arrange already lowers rank on cancels (Phases 7–9). BL rank events measured in MAME (Phase 13); **fragment (K07), medal and rose (K09) done** — BL uses Arrange's pickup rank rules; bomb/Hadou cancel rules [todo] |
| F9 | **Score items / medals** | same medal ladder concept; next medal `0C3C53E0`; item pickup routine BL-only `0C07D100` (arcade `0C06BB60`) [spec][delta] | [PS2] medal ladder `0x0020B100`, pickup table `0x0020BF60` |
| F10 | **Bullet cancel after bosses and mid-bosses** | erases all enemy bullets [spec]; MAME: BL-only cancel-all `0C0BC310` runs from the main loop while counter `0C2B07FC` ≠ 0; 25 death paths set it to 16; no score | **Done (K24):** `bl_boss_cancel_frame` (`ps2/hooks/bl_enemy.c`): 21 (stage, type, subtype) part kills taken from MAME stages 1–6, same parts on PS2; clears enemy bullets for 16 frames (held through the stage-1 tanks' and boss's death animations, as BL). One BL write with no part kill (stage 5, MAME frame 55448) not covered |

## 1b. Worklist: ship select (F1), shot tables (F5), bombs (F7)

BL routines that touch the player shot table or the ship-select flag (Phase 11), with their arcade Ibara
originals and Phase 12 PS2 candidates (candidates only). Known PS2 roles: `0x0013B2F0` is a per-frame
shooting routine (reads held `0x10`), `0x0011A580` the projectile writer from Phase 9, `0x0012AC60` the
shot-vs-bullet pass. **Caution:** BL `0C06D170` reads as a player start/continue setup (shot level
`+0x25B/0x25C`, a 7-entry stock loop, current weapon `+0x26F`, input words, ship-select flag, rank), so its
Phase 12 pairing with the per-frame shooter `0x0013B2F0` is probably wrong; verify each pair before porting. The ship-select screen itself is BL-only code (`0C0B8210`, 1,618 instructions, plus
`0C070DC0`, `0C0703C0`, `0C0734D0`); the BL ship byte is side·8 + ship·4 + type (ship 0 straight, 1 spread).

| BL | status | insns | arcade Ibara | PS2 candidate | structures |
|---|---|---|---|---|---|
| `0C06A3C0` | changed | 556 | `0C0588C0` | `00191B90` (mutual_best 0.438) | attract_flag, player_records, ship_select_flag, stage, stage_record_id |
| `0C06D170` | changed | 208 | `0C05B260` | `0013B2F0` (mutual_best 0.510) | player_records, rank, ship_select_flag, weapon_stock |
| `0C06D950` | changed | 496 | `0C05DE00` | — | attract_flag, player_records, ship_select_flag |
| `0C06E810` | operands | 244 | `0C05ED70` | `0012AF90` (mutual_best 0.462) | enemy_parts, player_records, player_shots |
| `0C06EAC0` | changed | 183 | `0C05F020` | `0012AC60` (anchor 1.000) | enemy_bullets, player_records, player_shots |
| `0C077090` | changed | 53 | `0C066150` | `0012D840` (mutual_best 0.452) | camera, player_records, ship_select_flag |
| `0C078E40` | changed | 112 | `0C067DC0` | `0011C380` (mutual_best 0.616) | player_records, player_shots |
| `0C078F70` | changed | 578 | `0C067EE0` | `0011B850` (mutual_best 0.548) | enemy_parts, player_records, player_shots |
| `0C079600` | changed | 126 | `0C068570` | — | player_records, player_shots |
| `0C077230` | changed | 155 | `0C068F40` | `0011A580` (mutual_best 0.633) | player_records, player_shots |
| `0C07A100` | operands | 149 | `0C069060` | — | player_records, player_shots |
| `0C07A280` | operands | 157 | `0C0691E0` | `00119F20` (mutual_best 0.535) | player_records, player_shots |
| `0C07A410` | changed | 166 | `0C069370` | `00119BC0` (mutual_best 0.554) | player_records, player_shots |
| `0C07A7B0` | operands | 144 | `0C069710` | — | player_records, player_shots |
| `0C07A920` | operands | 144 | `0C069880` | — | player_records, player_shots |
| `0C07AA90` | operands | 109 | `0C0699F0` | `001190A0` (mutual_best 0.553) | player_records, player_shots |
| `0C07B590` | changed | 42 | `0C06A4F0` | — | player_records, player_shots |
| `0C07B620` | operands | 59 | `0C06A560` | `0011AA30` (mutual_best 0.544) | player_records, player_shots |
| `0C07B750` | changed | 39 | `0C06A690` | `0011A9A0` (mutual_best 0.431) | player_shots |
| `0C0703C0` | b_only | 212 | BL-only | — | camera, player_records, rank, ship_select_flag |
| `0C070DC0` | b_only | 296 | BL-only | — | camera, player_records, ship_select_flag, weapon_stock |
| `0C0734D0` | b_only | 121 | BL-only | — | player_records, ship_select_flag |
| `0C07B7C0` | b_only | 69 | BL-only | — | player_shots |
| `0C0B8210` | b_only | 1618 | BL-only | — | camera, enemy_parts, player_records, ship_select_flag |

Approach: port each "changed" routine's BL difference into the PS2 counterpart as a hook or word patch in the
BLACK LABEL build (as done for the weapon stock), starting with the shooting routine and the straight/spread
branch on the ship byte; implement the BL-only select screen with the game's own menu/text layer.

## 2. Game flow

| # | Feature | BL facts | PS2 status |
|---|---|---|---|
| G1 | No Normal/Harder/Extended modes; single loop of 6 stages, stage byte 2–7 | [spec] | PS2 Arcade has modes; BL mode forces one |
| G2 | Opening / stage record id 0 before stage 1 | `0C23E0A6` = 0 [spec] | [todo] |
| G3 | Start menu side select (1P/2P) | [spec] | [todo] |
| G4 | Music = Ibara's list minus "Show Time" (seq 15/16) | [spec] | [PS2] PS2 soundtrack already on disc |
| G5 | Bosses | run Ibara's boss code with Ibara's constants (checked constant by constant in ibara360 notes) [spec] | [PS2] reuse PS2 Arcade bosses; verify timing |
| G6 | Stage content (regular enemies, scripts) | ~288 changed routines touching enemy parts, ~17k-instruction delta [delta]; stage 1 boss arena at scroll 2449.25 [spec] | Stage 1 placement equals PS2 Arcade (Phase 14); **enemy HP formula (K11) and fire timer (K12) ported**; stage-1 boss logic matches (spiral order is random); player shot damage/reach and stages 2–6 [todo] |
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
