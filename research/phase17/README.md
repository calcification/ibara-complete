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
retail executable and refuses literal runs over 4 KiB or 64 KiB in total. Current patch: 4.3 KB, 7.5 KB of literal
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

**ARCADE MODE > PRACTICE > GAME MODE** (`PRACTICE_MODE_PATCHES`): practice start `0x001CB3C0` sets PRACTICE
(`0x00338FA4`) and clears the Arrange flag (`0x00338F44`) at `0x001CB3E0`; that store now writes the chosen mode. With
both flags the game runs Arrange from the chosen stage: Arrange HUD, formation label, sub-weapon plates, Arrange high
score; Game Over returns to PRACTICE; Arcade's GAME START clears the flag again (`0x001CAD04`). Row 4 before EXIT
(label slot 5 was spare, help table had 2 spare slots), 6 rows (`0x001CB0A4`, `0x001CB298`; the up-wrap stores a2 =
the state number 4, so `li a2,5` at `0x001CAD48`), EXIT → row 5, row 4 via the unreachable `0x001CBB4C` to a toggle,
values via `prac_value` at `0x001CB058`. PCSX2: ARRANGE stage 3 (flags 1/1, scene 4) in the launcher; KURO shows
KURO / ARRANGE and runs Arrange practice; a later Arcade game has both flags 0 (O02).

Not done: KURO in the launcher's PRACTICE (KURO is a separate executable; practising it means KURO → ARCADE →
PRACTICE, or the planned merge of KURO into the main executable). Settings are not saved to the memory card.

The frontend executable now carries ~1.8 KB of hook code, more than the 976 bytes left in its disc extent, so the
launcher builder writes it to the free extent after KURO.ELF and points the boot record there (the retail copy is
left in place).
