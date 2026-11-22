# Debug handoff — 22 November 2026

For the next model: **debug only, add no features.** This lists what was changed recently, what is verified, and
where bugs are most likely. Status overview: `docs/PROGRESS.md`. Feature spec: `docs/BLACK_LABEL_FEATURES.md`.
Tests: `TEST_MATRIX.csv` (K-rows = KURO).

## Ground rules (from the user)

* Never commit ISO / ELF / ROM / savestates / MAME output or anything copied from the game; run
  `python3 scripts/check_repository_safety.py` before every commit. Art reaches the disc only from the user's own
  ROM through the patcher (`--bl-rom`); the repository holds coordinates and offsets only.
* KURO = Black Label rules; Arrange must stay as on the original disc (only addition: its PRACTICE row).
* ibara360 is a study reference only; copy none of its code.
* Work on branch `claude/ibara-black-label-ps2-rm9qnw`; no pull request unless asked.

## Build / check loop

```bash
python3 -m pytest -q tests                      # 48 tests; includes the 16-byte stack-frame check
python3 scripts/build_ee_hooks.py               # rebuilds hooks + refreshes ps2/prebuilt/*.json (commit those)
python3 scripts/build_black_label_iso.py 'Ibara (Japan).iso' --output built.iso [--bl-rom ibarablk.zip]
python3 scripts/make_patch.py 'Ibara (Japan).iso' built.iso --output patcher/ibara_kuro.patch --note "..."
python3 patcher/apply_kuro_patch.py 'Ibara (Japan).iso' out.iso --bl-rom ibarablk.zip   # must equal built --bl-rom disc (cmp)
```

PCSX2 driving: `tools/pcsx2_session/` (README there). Savestate RAM: `scripts/p2s_tools.py` (`load_ee`; CPU regs are in
"PCSX2 Internal Structures.dat" after the `cpuRegs` tag). MAME loggers: `research/phase20/*.lua`,
`research/phase21/bl_graze_log.lua`, `tools/stage_compare/*.lua` (`mame ibarablk -nodrc -rompath ... -video none
-autoboot_script X.lua`, env `OUT`). BL program RAM can be dumped from MAME and disassembled with
`sh4-linux-gnu-objdump -D -b binary -m sh3 -EB --adjust-vma=0x0C000000`.

## Lessons that explain past bugs (check these first when something hangs)

1. **Stack alignment.** Hooks are now built **n32** (`-mabi=n32`, `ld -m elf32ltsmipn32`) so every frame is 16-byte
   aligned. With o32 (8-byte frames) a thread switch inside our code restored `gp` as garbage (seen as TLB misses at
   0x4C/0x50 in the sprite routine `0x00110B70`). Any new asm stub must keep `sp` 16-aligned.
2. n32 passes arguments 5-8 in `$8-$11` (e.g. `ktex_sprite` in `ps2/hooks/bl_tex.c`).
3. Leaf hook sources (`LEAF_SOURCES` in `scripts/build_ee_hooks.py`) must not use s-registers (the game keeps
   128-bit values there); a test enforces it.
4. Never save `ra` in a `jal` delay slot (`ra` is already overwritten there).
5. Symbol addresses move with every build: re-read them (`build_hook(...)['syms']`) before poking RAM.

## Debug targets, most likely first

| # | Area | What to check | Where |
|---|---|---|---|
| 1 | n32 switch side effects | All hook code was rebuilt as n32. Re-tested: KURO stage 1, select screen, Arrange stage 1 + PRACTICE row, Mode Select. **Not re-tested:** the PNACH profile `pnach/hooks/bl_xtc/` (K01, cave 0x000C0000), Tate/Yoko video switch and memory-card restore (V01/V02), CONFIG > RANK GAUGE (O01), the old BLACK LABEL launcher build (K02-K10). | `scripts/build_ee_hooks.py` CFLAGS; `ps2/hooks/video.c`, `options.c` |
| 2 | Select screen opening | `sel_start_stub` marks a start on **every** player start (continues, P2 join). A P1 continue probably reopens the screen mid-game; whether BL does so is unverified. Also untested: P2 joining while the screen is up, opening in stages 2-6, pausing (Start) while it is up. | `ps2/hooks/bl_select.c` (`bl_select_tick`, `pausable`, `finish`) |
| 3 | Stage hidden while selecting | `sel_layers_stub` makes `jal 0x00112500` return to `0x0012E424`, skipping the 24-layer draw loop. Check that nothing drawn later depends on that loop (first frame after closing). | `bl_select.c` asm; patch row in `BL_SHIP_PATCHES` |
| 4 | Texture objects | `bl_tex.c` borrows empty object slots (1107-1112 seen) and page-table row 6 while the select screen is up; KT_BAR uses object 1114 + entry row 1/col 5 permanently (`refresh()` rewrites them every draw). Only stage 1 tested: check later stages don't load textures into those slots/entries (wrong pixels, hangs). | `ps2/hooks/bl_tex.c` |
| 5 | GS texture cache | Rank bar, graze sphere and XTC popup all draw through KT_BAR (page 5) every frame, beside the stage's textures. Watch for flicker / wrong pixels in busy stages (cache has 19 slots, second-chance eviction `0x001BB090`). | `bl_tex.c`, `bl_rankbar.c` |
| 6 | XTC rules | `XTC_REQUIRE_PODS` is 0: BL also requires player +0x289 (very likely "pods out") — KURO may count grazes BL would not. 110 points per graze at rank 0 is untested in play. Popup / sphere for player 2 untested (ship-kind = `((ship word >> 2) ^ side) & 1` assumption). | `ps2/hooks/xtc.c`, `bl_rankbar.c`; research/phase21 |
| 7 | Pod shot counts | Same-day PCSX2 vs BL (per 1,000 frames): 5-way 1540 vs 817, homing 64 vs 123, napalm 72 vs 38 — sparks are ruled out (K30); suspect targeting or fire rules. | research/phase16 README ("Shot sparks"); `tools/stage_compare/bl_pod_rate.lua`, `run_stage.py --define BL_RATE_TEST` |
| 8 | Patch size limit | `scripts/make_patch.py` `MAX_DATA_RUN` raised to 16 KiB (longest literal run now 9,888 bytes). Confirm the run is only our hook image. | `scripts/make_patch.py` |
| 9 | HUD while selecting | The HUD ("♪Show Time" track line, score) still draws over the select screen; BL has no Show Time. Cosmetic. | `bl_select.c` |

## Recently changed files (last commits on the branch)

`ps2/hooks/bl_select.c`, `bl_select.h`, `bl_select_data.c` (generated), `bl_tex.c`, `bl_rankbar.c`, `xtc.c`,
`ps2/include/ibara_ps2.h` (GAME_CALL macros), `scripts/build_ee_hooks.py` (n32, KURO patch rows incl. sparks
`0x0013BD0C`/`0x0013BD28`), `scripts/make_patch.py`, `patcher/apply_kuro_patch.py`, `patcher/bl_select_atlas.json`
(select art + sphere rows 96-111 + XTC digits rows 112-127 on page 5), `research/phase20/make_select_data.py`.

Test-only defines worth knowing: `BL_TEST_XTC_POPUP` (xtc.c: one graze per frame while shot held),
`BL_RATE_TEST`, `BL_TRACE_WEAPON`/`BL_TRACE_TYPE`, `BL_TEST_ALL_WEAPONS` (spawnlog.c / xtc.c). With `--define`, the ISO
builder uses the prebuilt image, so put a test define at the top of the source temporarily (and remove it).
