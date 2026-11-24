# Phase 17 — ibara360 feature review; Arcade RANK gauge

## ibara360 features compared with this project (2026-11-21)

Read from ibara360's README, PATCH_NOTES (v1.04) and its menu strings (study only; no code copied). It runs on
the Xbox 360 from the arcade ROMs, so some features belong to that platform.

| ibara360 feature | Here | Notes |
|---|---|---|
| Ibara (Normal / Harder / Extended), PS2 Arrange | retail PS2 | already on the disc |
| Black Label | **in progress** (KURO) | see `docs/BLACK_LABEL_FEATURES.md` |
| Arcade slowdown (timing model fitted to the real board) | no | PS2 port has almost none; would need a per-frame load model in the EE — large |
| TATE, scanlines, integer scaling, picture options | Tate 240p / Yoko unfiltered | scanlines etc. are the display's job on PS2 |
| **Rank display in Arcade** ("DETAILED RANK DISPLAY", Arrange's RANK gauge) | **done** (below) | numeric % still possible (HUD text, as the XTC counter) |
| Training: any stage, skip to boss, starting rank, rank lock / RANK %, invincible, infinite bombs, starting lives / bombs / medal value / options, formation, hitbox viewer, game speed | PS2 PRACTICE has stage select only | candidates: rank lock, invincibility, start at boss, hitbox view — each a small hook; needs a menu page or button combo |
| BOSS HP AND TIMER | no | boss HP is in the part records (`+0x3C`); the timer exists in the game |
| Save states, replays | no | emulator features (PCSX2 has save states) |
| Button remap, AUTO SHOT 7.5–30 Hz | retail KEY CONFIG | autofire rates: candidate (pad hook) |
| Arcade YMZ770 soundtrack | no | PS2 soundtrack only |
| GADGETS side panels, STAGE MAP, STORY | no | 16:9 Xbox layout; no room on a 4:3 PS2 picture |
| Debug: initialize rankings, attract demos on/off | no | small; low priority |
| Achievements | no | n/a |

## Arcade slowdown investigation (2026-11-23)

The target is the cadence of **gameplay updates per video refresh**. A repeated gameplay frame during a
busy attack changes how much time the player has to react. The normal video refresh, emulator wall-clock
speed, loading time, and a single effect's animation speed are separate measurements.
The [S01 retail Arcade probe](../phase22/README.md) tests whether that cadence can be controlled.

### Retail PS2 timing points

| Address | Meaning in clean SLPM-66301 (`420C7FAB`) |
|---|---|
| `0x00338CDC` | Outer game-loop counter. Increments at `0x001133B0` in the routine called at `0x0012E09C`. That routine also polls the pad via `0x00112A80`. |
| `0x00338EA0` | Stage gameplay tick. Cleared at `0x0012DD48` and incremented at `0x0012E664` after the gameplay update calls. Collision code uses its low bit to alternate players. |
| `0x0012E1E4` | Native gate for the core gameplay pass at `0x0012E5CC`. It checks pause through `0x0012C220` and two transition states. Both paths reach the draw/HUD path at `0x0012E1EC`. |

The audited gate has no workload input. In PCSX2 2.8.2 on the retail disc, a no-shot Stage 1 window advanced
3,417 gameplay ticks in 3,417 outer-loop iterations, with up to 46 live hostile bullets. The two-second native
Pause control advanced the outer loop 105 times and the gameplay tick zero times.

Two further no-shot runs used the clean retail code, held inverted rank at `0x200000` and refreshed
P1 invulnerability (`0x0044C380 + 0x27A`) in RAM. Each started after its stage transition cleared.

| Retail Arcade scene | VSyncs | Outer loops | Gameplay ticks | Peak sampled hostile bullets |
|---|---:|---:|---:|---:|
| Normal Stage 1 | 2,311 | 2,311 | 2,311 | 249 |
| Practice Stage 5 | 2,632 | 2,632 | 2,632 | 176 |

PCSX2 stores `g_FrameCount` immediately after the 32-byte `InputRecording` tag in
`PCSX2 Internal Structures.dat`. Read that field and the EE counters from the same save state. The emulator’s
wall-clock rate varied during concurrent captures. [PCSX2 VSync counter](https://github.com/PCSX2/pcsx2/blob/v2.8.2/pcsx2/Counters.cpp#L565-L569)

### Original arcade reference

MAME 0.276 verified the supplied `ibara` set, program U4 CRC `d5fb6657`. A no-shot Stage 1 run with P1
invulnerability (`0x0C283794 + 0x269`) and inverted rank `0x200000` reached 252 live hostile bullets. Across
2,989 consecutive-frame intervals sampled at 125 or more bullets, each VBlank advanced outer counter
`0x0C392964` once and had one blitter submission and one or more game rank writes. The scene byte is
`0x0C392B08`, the rank address is `0x0C27DFF8`, and the blitter submission register is at `0x18000004`.
The Stage 1 measurements show normal cadence on both emulators even under high bullet load. Use late
Stage 3 and the Stage 5 and 6 bosses to capture the reported PCB slowdown and calibrate the timing model.

MAME’s CV1000 driver runs Ibara at 60.024 Hz and its EP1C12 device models blitter busy time based on the
draw list. The driver labels the set’s timing imperfect. The `ibara360` author describes fitting the timing
model to recordings of the original board. Treat MAME as a controlled reference and use the PCB recording
for rates and attack landmarks. [MAME driver](https://github.com/mamedev/mame/blob/mame0276/src/mame/cave/cv1k.cpp) ·
[MAME blitter](https://github.com/mamedev/mame/blob/mame0276/src/mame/cave/ep1c12.cpp) ·
[ibara360 approach](https://github.com/PaulAtreides67/ibara360)

### What a PS2 prototype would take

1. Anchor a single boss pattern by state and attack step. Capture display refreshes, stage ticks, rank,
   inputs, hostile bullet counts, and active enemies and effects. Use the same ship and firing pattern.
2. Test delaying one core gameplay update at the native gate. Keep video, pad polling, and audio running.
   Audit mutations outside the gate, especially rank, scrolling, and input edges. Buffer an actionable
   shot or bomb edge through a held update so it can be consumed once on the next tick.
3. Fit a bounded timing model against busy and quiet reference windows. Include drawing cost such as
   effects, sprite coverage and blending alongside simulation load. Use bullet counts as telemetry.
   Start with Arcade and fit Black Label separately to its own reference. Check the retained cadence
   and input timing on PCSX2 and original PS2 before changing release behavior.

## Arcade RANK gauge

The RANK gauge Arrange shows at the top right is drawn by `0x00129360`, called every frame from the HUD pass
(`0x0012E42C`, between the boss bar `0x00128960` and the formation label `0x001285C0`). It returns early unless
Arrange (`0x00338F44`, `$gp-28076`) or Arcade PRACTICE (`0x00338FA4`, `$gp-27980`, set by the Practice menu
`0x001CB3C8`) is on. Its fill is `0xFFFFFF - 0x00338EB4` (`$gp-28220`), the stored rank Arcade uses too, so the
retail game already shows a correct gauge in Arcade PRACTICE.

Edits (`scripts/build_ee_hooks.py` `RANK_GAUGE_EDITS`, builder option `--rank-gauge arcade`, default):

* `0x00129394` `beqz v1, 0x00129758` → `nop`: draw in every Arcade game.
* The gauge sits on Arcade's blinking "PRESS START / button" for the side not playing (string loads at
  `0x0012C7C0/C7E4/CA00/CA24` of `0x00205F20` / `0x00205F30`); they load the game's blank string `0x00205F40`
  instead, as Arrange and Practice show nothing there. Only the text changes; a 2P join with Start was not re-tested.

Applied to both executables (launcher Arcade and KURO). PCSX2: gauge drawn in Arcade and in KURO's Arcade, fill
matching the stored rank (`0xDFBA87` → about 12 %), no text under it (R01).

## Patcher

`patcher/` (stdlib Python) applies `ibara_kuro.patch` made by `scripts/make_patch.py`. xdelta3 was tried first: its
source window is capped at 2 GiB, KURO.ELF lies ~2.9 GB before the retail executable it copies, and the delta came
out with ~300 KB of literal game code, so it was not used. `make_patch.py` instead copies from anywhere in the
retail executable and refuses literal runs over 4 KiB (8 KiB since phase 19) or 64 KiB in total. Current patch: 4.3 KB, 7.5 KB of literal
bytes (hook images, edited HP-table words, the KURO label, directory records, zero runs).

## In-game options (2026-11-21)

**ARCADE MODE > CONFIG > RANK GAUGE** (ps2/hooks/options.c, `RANK_OPTION_PATCHES`): a 10th row (row 6, after
CONTINUE). Label table `0x002A9220` (rows 7-9 moved into its spare slot), row count 9 → 10 (`0x001CBFE4`,
`0x001CC170`, `0x001CC1FC`), dispatcher rows 6/7/8 → 7/8/9 and row 6 through the unreachable word `0x001CC4DC` to a
toggle; value column through `cfg_value` at the CONTINUE lookup `0x001CBF70`; help text from our own 10-row table;
FIGHTER TYPE / KEY CONFIG return to rows 7 / 8 (`0x001CC5E4/5F4`, `0x001CC68C/69C`, `0x001CA08C`). The toggle rewrites
the 5 gauge words and flushes the caches; the value travels in the LoadExecPS2 argument ("S=<mode><gauge>").
PCSX2: row shown with its help text; OFF → retail HUD (PRESS START, no gauge); ON → gauge; OFF carried into KURO;
FIGHTER TYPE and KEY CONFIG open and return to their rows (O01).

**ARRANGE MODE > PRACTICE** (`PRACTICE_MODE_PATCHES`; replaces a first version that put a GAME MODE row in Arcade's
practice menu — the user preferred practice nested in each mode). The practice start `0x001CB3C0` sets PRACTICE
(`0x00338FA4`) and clears the Arrange flag (`0x00338F44`) at `0x001CB3E0`; that store now writes `prac_arrange`.
With both flags the game runs Arrange from the chosen stage (Arrange HUD, formation label, sub-weapon plates, Arrange
high score; Game Over returns to the practice menu). ARRANGE MODE (state 9) gets 4 rows: label slot 3 was spare,
help text moved to our own table, rows 3 → 4 (`0x001CCB50`, `0x001CCA98`; the up-wrap stores a0 = 2 from the
dispatcher, so `li a0,3` at `0x001CCA80`), CONFIG/EXIT → rows 2/3, row 1 via the unreachable `0x001CC9B4` opens state 4
with `prac_arrange` = 1. Leaving the practice menu (`0x001CB2C8`, `0x001CB384`) goes back to state 9 or 2 on row 1
and clears the flag. The header selector (`0x001C9570`: states 2-8 ARCADE MODE, 9-12 ARRANGE MODE) sees state 4 as 9
while practising Arrange. ARRANGE CONFIG's title read its old label slot (`0x001CCDB8` → slot 2) and its exits return
to row 2 (`0x001CD008`, `0x001CD0B4`). PCSX2: ARRANGE → PRACTICE (ARRANGE MODE header), STAGE 3 → flags 1/1, scene 4,
Arrange HUD; Game Over → practice menu; EXIT → ARRANGE MODE on PRACTICE; ARCADE → PRACTICE afterwards: ARCADE MODE
header, flags 0/1; ARRANGE CONFIG title and return row; up-wrap to EXIT; ARRANGE GAME START: flags 1/0; inside KURO,
ARRANGE → PRACTICE runs Arrange (O02).

KURO is practised inside KURO (KURO → ARCADE MODE → PRACTICE). Settings are not saved to the memory card.

The frontend executable now carries ~1.8 KB of hook code, more than the 976 bytes left in its disc extent, so the
launcher builder writes it to the free extent after KURO.ELF and points the boot record there (the retail copy is
left in place).

## Instant KURO (2026-11-21)

KURO is no longer a second executable started with LoadExecPS2. The frontend executable carries the whole hook
image (`ps2/hooks/kuro.c` with video.c, options.c and the Black Label sources); the builder turns bl_mode's 83 Black
Label words (3 hook call sites, the fire-timer jump, rule patches, 51 part-HP words) into a table after the image,
(address, retail, Black Label). `kuro_set` writes one column (only over the other column's value) and flushes the
caches. KURO.ELF is gone from the disc.

* Entering: Mode Select's KURO dispatcher (launcher builder DISPATCH 0x001D42A0) jumps at 0x001D42AC — after its
  branch's delay slot — to `kuro_enter_entry`: XTC reset, table on, state 2 (ARCADE MODE's menu), as the Arcade row.
  First try patched 0x001D42A8, the delay slot itself: LoadExecPS2 still ran and the console rebooted.
* Leaving: ARCADE MODE's cancel (0x001CA958) and EXIT (0x001CAAC4) call `kuro_leave_entry` (table off; Mode Select
  row = KURO's when leaving KURO, else 0, through `sw v1,-26724(gp)` at 0x001CA968 / 0x001CAAD4).
* Safety net, every frame: off at state <= 1 (title, Mode Select) or on the attract flag `$gp-28276` rising (set
  with the demo's Arcade rules at 0x0013DDBC); a game keeps its submenu's state (3 / 4), so state alone misses the
  attract sequence after a Game Over.
* The per-frame wrapper (`frame_hook`: video_frame then kuro_frame) is assembly with a 16-byte frame: as C it had a
  24-byte frame and the game hung at its first NOW LOADING (bisected: the same image with the stub calling
  video_frame directly booted).

PCSX2 (K20): KURO opens in ~0.3 s; inside, all 83 words Black Label, XTC 126 grazes holding shot; EXIT / cancel →
Mode Select on KURO, all 83 retail, next Arcade game retail; KURO game left to Game Over → attract: all retail; KURO
again: all Black Label; KURO PRACTICE stage 2: Black Label, scene 3; Tate from a saved card: 224p in Mode Select,
KURO's menu and a KURO game. Not done: a KURO header picture (needs new artwork in the header texture).

## Enemy part HP, all stages (2026-11-21)

`run_stage.py --stage 6 --all-tables` (new: both loggers list every stage's part-record tables): BL 68 tables, PS2
69. `diff_part_tables.py`: types 8 and 45 (the 51 stage-2 HP words already patched) and **type 52, 7 entries**
(12→14, 8→10 ×2, 5→6 ×3, 10→12; `0x00284E6C`–`0x00284EEC`) — now in `ps2/bl_part_hp.json` (58 words). No score
differences. Tables that matched on few or no scores were checked entry by entry: effect parts with 1-entry tables
(HP equal) and records past the logged range. So stages 3–6 need no other part-HP change.

## Bullet cancel after bosses and mid-bosses (2026-11-21)

MAME (`tools/stage_compare/bl_cancel_log.lua`, write tap with `-nodrc`): BL erases every enemy bullet when certain
parts die (stage-1 boss: 19 → 0 two frames after the core, no score change). The erasing is BL-only code:
cancel-all `0C0BC310` (per bullet `0C0BB980` / `0C0BB9F0`) called from the main loop `0C06C630` while counter
`0C2B07FC` is non-zero. Logging every write of 16 to the counter and every kill (HP > 0 → 0, record alive or
freed, score ≥ 1000) through stages 1–6, each write but one follows the kill of one part (stage byte, type, subtype):

| Stage | Parts (type/subtype) | Notes |
|---|---|---|
| 1 | 11/0, 11/1 (tanks, 5,000) | counter rewritten every frame of the 141-frame death |
| 1 | 5/0 (boss core) | rewritten every 3 frames for ~216 frames |
| 2 | 34/0, 33/0 (mid-boss cores, record freed at once) | 33/0 also dies in stage 5 there with no cancel |
| 2 | 45/3D, 45/31, 45/2A, 45/0 (boss parts and core) | 45/33 dies without a cancel |
| 3 | 48/4, 48/7, 48/0, 51/2, 51/0 | |
| 4 | 41/0, 42/0 | |
| 5 | 65/0, 65/6 | one more write at frame 55448 with no part kill — not covered |
| 6 | 69/0, 74/0, 74/2 | |

The PS2 kill log (`run_stage.py --stage 6 --define BL_MIDLOG`) shows the same parts dying in the same order (the
type-11 death animation is 141 frames there too), so the types and subtypes carry over. `bl_boss_cancel_frame`
(KURO, every game frame) keeps each part's HP from the previous frame; a listed part (for the current stage
byte `0x00338E9C`) whose HP goes from > 0 to 0, or a HOLD part alive with HP 0, arms 16 frames of clearing every
enemy bullet record. A first version keyed on the Arrange boss gauge (`0x00338B5C/60`) only covered the 6 bosses.

PCSX2, stages 1–6 with the hook (K24): 20 clears, each the frame after the listed kill; enemy bullets left the
frame after the first clear: 0 in 18, 6 and 5 in the stage-5 and stage-6 boss deaths (cleared over the next
frames); stage 5's 33/0 kill no longer clears. Stage 3 showed one clear fewer than the five parts (48/4 and 48/7
were not both killed in that run). The game played on through the stage-6 boss.
