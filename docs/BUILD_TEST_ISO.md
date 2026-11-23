# Build a testable Black Label ISO

**Easiest: the patcher.** `patcher/apply_kuro_patch.py` (Python 3.8+, no extra packages) turns your
`Ibara (Japan).iso` into `Ibara KURO.iso` in about 30 seconds; on Windows drag the ISO onto
`patcher/apply_kuro_patch.bat`. See `patcher/README.md`. The rest of this page builds the same disc from source,
with options.

One command turns your own clean Japanese disc image into a separate test ISO whose Mode Select has an extra
row, **KURO** (third, right after Arcade and Arrange): Black Label, switched on instantly (no reload). Your original ISO is only read.

```bash
pip install -r requirements-assets.txt           # Pillow, numpy (once)
python3 scripts/build_black_label_iso.py 'Ibara (Japan).iso' --output 'Ibara Black Label test.iso' --bl-rom ibarablk.zip
```

Windows: `py -3 scripts\build_black_label_iso.py "Ibara (Japan).iso" --output "Ibara Black Label test.iso" --bl-rom ibarablk.zip`.

* Input must be the exact retail `SLPM-66301` image (ELF SHA-256 `263d3079…`, PCSX2 CRC `420C7FAB`); anything
  else is refused. CHD/CSO: convert back to ISO first.
* Default video is `auto_full_frame` (below). `--video-profile auto` uses the earlier 224-active-line Tate crop.
  `--video-profile 240p_cave_beta` is progressive in every mode (matches the published
  Cave 240p patch; verified on one real PS2); `--video-profile retail` is the original interlaced output.
* Default `--rank-gauge arcade` adds a **RANK GAUGE** toggle to Arcade and KURO CONFIG. Arcade starts OFF and
  KURO starts ON. Attract mode suppresses the gauge. `--rank-gauge arrange` hides the toggle.
* `--bl-rom` adds the Black Label artwork for ship select before takeoff and the RANK bar. KURO skips the retail
  ranking and autosave flow, and restores retail settings when leaving.
* ARRANGE MODE has its own **PRACTICE** row (GAME START, PRACTICE, CONFIG, EXIT), like ARCADE MODE: the same
  practice menu (stage select, start position, play data) under the ARRANGE MODE header, playing Arrange. Inside
  KURO's rules are practised from KURO → PRACTICE.
* No MIPS compiler needed: the committed `ps2/prebuilt/kuro.json` is used (byte-identical to a source
  build; a test keeps it in sync). With `gcc-mips-linux-gnu` installed the hooks are rebuilt from `ps2/hooks`.
* Output is ~3.7 GB and contains game data: keep it local; never upload it.

## Playing it

Boot the new ISO (PCSX2 with **cheats off**, or your usual loader). Start at the title → Mode Select → **Down** twice
to **KURO** → **Circle**. (`--label` changes the text, `--position 5` puts the row at the bottom as before.)

The default `--video-profile auto_full_frame` keeps **Yoko** interlaced and uses all 240 active lines for
**Tate R / Tate L** on NTSC. All orientations use nearest-neighbor filtering. Switch live in OPTION → SCREEN
SETTING → SCREEN MODE.
`--video-profile 240p_cave_beta` gives the previous behaviour (240p in every mode). Inside: Circle confirms, Cross cancels; in game Cross = shot, Circle = bomb,
**Square = weapon change**. KURO opens a menu like ARCADE MODE's (GAME START, PRACTICE, CONFIG, EXIT; the header still reads ARCADE MODE)
with the Black Label rules switched on; EXIT (or cancel) switches them off and returns to Mode Select on KURO. They
also switch off at the title / Mode Select and when the attract sequence starts after a Game Over.

What the BLACK LABEL build currently does (see `docs/BLACK_LABEL_FEATURES.md`, results in
`tests/results/2026-11-20_RUNTIME.md`): XTC graze scoring and bomb wipe, Arrange's seven-slot weapon
bar below the bomb stock and fragments, BL shot levels (small P to level 6, no secret), BL rank rules for fragments,
medals and roses, BL enemy HP and fire timing, held fire and 32-shot cap. `--bl-rom` also adds the graze sphere.

Report what you see with `tests/manual/RESULT_TEMPLATE.md` (PCSX2 version or hardware/loader, video profile,
what happened, screenshots).
