# Build a testable Black Label ISO

One command turns your own clean Japanese disc image into a separate test ISO whose Mode Select has an extra
row, **KURO** (third, right after Arcade and Arrange), that starts the Black Label build. Your original ISO is only read.

```bash
pip install -r requirements-assets.txt           # Pillow, numpy (once)
python3 scripts/build_black_label_iso.py 'Ibara (Japan).iso' --output 'Ibara Black Label test.iso'
```

Windows: `py -3 scripts\build_black_label_iso.py "Ibara (Japan).iso" --output "Ibara Black Label test.iso"`.

* Input must be the exact retail `SLPM-66301` image (ELF SHA-256 `263d3079…`, PCSX2 CRC `420C7FAB`); anything
  else is refused. CHD/CSO: convert back to ISO first.
* Default video is `auto`. Use `--video-profile 240p_cave_beta` to apply the published Cave patch in all screen
  modes, or `--video-profile retail` for the original interlaced output.
* Without a MIPS compiler, the builder uses the checked-in hook images. With `gcc-mips-linux-gnu` installed it
  rebuilds the hooks from `ps2/hooks`. The byte-for-byte regression check uses the Debian 12 cross toolchain.
* Output is ~3.7 GB and contains game data: keep it local; never upload it.
* For an optical timing comparison, build a separate ISO with `--near-assets` to put KURO next to the original IOP
  files. This reduces the distance between the files on disc. Time Kuro entry and stage loading separately on the
  same hardware and medium to measure any change.

## Playing it

Boot the new ISO (PCSX2 with **cheats off**, or your usual loader). Start at the title → Mode Select → **Down** twice
to **KURO** → **Circle**. (`--label` changes the text, `--position 5` puts the row at the bottom as before.)

Video (default `--video-profile auto`): **Yoko** keeps the retail interlaced output, with texture filtering off;
**Tate R / Tate L** switch to 240p progressive (the cave-ps2-240p geometry), live, when you change OPTION →
SCREEN SETTING → SCREEN MODE. The screen mode is carried between the launcher and KURO in both directions.
An explicit memory-card load applies the mode stored on that card.
`--video-profile 240p_cave_beta` gives the previous behaviour (240p in every mode). Inside: Circle confirms, Cross cancels; in game Cross = shot, Circle = bomb,
**Square = weapon change**. Play Arcade as usual. EXIT in its Mode Select returns to the launcher.

For training, choose **KURO → Arcade → Practice**. The stock practice menu provides Stage Select, Start Position,
and Play Data List. Stage 2 was checked in PCSX2 with the Kuro hooks active.

What the BLACK LABEL build currently does (see `docs/BLACK_LABEL_FEATURES.md`, results in
`tests/results/2026-11-20_RUNTIME.md`): XTC graze counter with HUD and bomb wipe; weapon stock, weapon-change
button and weapon name on the HUD; BL shot levels (small P to level 6, no secret); BL rank rules for fragments,
medals and roses; return to the launcher. Not yet: BL enemy behaviour, ship select, graze sphere.

Report what you see with `tests/manual/RESULT_TEMPLATE.md` (PCSX2 version or hardware/loader, video profile,
what happened, screenshots).
