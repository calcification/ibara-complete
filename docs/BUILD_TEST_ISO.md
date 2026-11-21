# Build a testable Black Label ISO

**Easiest: the patcher.** `patcher/apply_kuro_patch.py` (Python 3.8+, no extra packages) turns your
`Ibara (Japan).iso` into `Ibara KURO.iso` in about 30 seconds; on Windows drag the ISO onto
`patcher/apply_kuro_patch.bat`. See `patcher/README.md`. The rest of this page builds the same disc from source,
with options.

One command turns your own clean Japanese disc image into a separate test ISO whose Mode Select has an extra
row, **KURO** (third, right after Arcade and Arrange), that starts the Black Label build. Your original ISO is only read.

```bash
pip install -r requirements-assets.txt           # Pillow, numpy (once)
python3 scripts/build_black_label_iso.py 'Ibara (Japan).iso' --output 'Ibara Black Label test.iso'
```

Windows: `py -3 scripts\build_black_label_iso.py "Ibara (Japan).iso" --output "Ibara Black Label test.iso"`.

* Input must be the exact retail `SLPM-66301` image (ELF SHA-256 `263d3079…`, PCSX2 CRC `420C7FAB`); anything
  else is refused. CHD/CSO: convert back to ISO first.
* Default video is `auto` (below). `--video-profile 240p_cave_beta` is 240p in every mode (matches the published
  Cave 240p patch; verified on one real PS2); `--video-profile retail` is the original interlaced output.
* Default `--rank-gauge arcade`: ARCADE MODE → CONFIG has a **RANK GAUGE** ON/OFF row (starts ON). ON shows
  Arrange's RANK gauge (top right) in Arcade, in the launcher and in KURO, and hides the blinking "PRESS START
  button" for the empty side (Arrange and Practice hide it too). The setting carries between the launcher and KURO
  but is not saved to the memory card. `--rank-gauge arrange` keeps the retail behaviour (no row).
* ARCADE MODE → PRACTICE has a **GAME MODE** row: ARCADE or ARRANGE (inside KURO: KURO or ARRANGE). ARRANGE
  practises Arrange from the chosen stage.
* No MIPS compiler needed: the committed `ps2/prebuilt/bl_mode.json` is used (byte-identical to a source
  build; a test keeps it in sync). With `gcc-mips-linux-gnu` installed the hooks are rebuilt from `ps2/hooks`.
* Output is ~3.7 GB and contains game data: keep it local; never upload it.

## Playing it

Boot the new ISO (PCSX2 with **cheats off**, or your usual loader). Start at the title → Mode Select → **Down** twice
to **KURO** → **Circle**. (`--label` changes the text, `--position 5` puts the row at the bottom as before.)

Video (default `--video-profile auto`): **Yoko** keeps the retail interlaced output, with texture filtering off;
**Tate R / Tate L** switch to 240p progressive (the cave-ps2-240p geometry), live, when you change OPTION →
SCREEN SETTING → SCREEN MODE. The screen mode is carried between the launcher and KURO in both directions.
`--video-profile 240p_cave_beta` gives the previous behaviour (240p in every mode). Inside: Circle confirms, Cross cancels; in game Cross = shot, Circle = bomb,
**Square = weapon change**. Play Arcade as usual. EXIT in its Mode Select returns to the launcher.

What the BLACK LABEL build currently does (see `docs/BLACK_LABEL_FEATURES.md`, results in
`tests/results/2026-11-20_RUNTIME.md`): XTC graze counter with HUD and bomb wipe; weapon stock, weapon-change
button and weapon name on the HUD; BL shot levels (small P to level 6, no secret); BL rank rules for fragments,
medals and roses; BL enemy HP and fire timer (stages 1–2); held fire and 32-shot cap; return to the launcher. Not yet: BL enemy behaviour, ship select, graze sphere.

Report what you see with `tests/manual/RESULT_TEMPLATE.md` (PCSX2 version or hardware/loader, video profile,
what happened, screenshots).
