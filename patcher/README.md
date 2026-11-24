# Ibara KURO patcher

Turns your own Japanese **Ibara** disc image (`Ibara (Japan).iso`, SLPM-66301,
3,932,848,128 bytes, MD5 `6ba671b5d23155b8254b6f4cefc90ae2`) into **Ibara KURO.iso**: the retail game plus everything
this project has done so far. Your ISO is only read; no game data is in this folder.

## Use

* **Windows:** install Python 3 (python.org), then drag `Ibara (Japan).iso` onto `apply_kuro_patch.bat` — select
  your `ibarablk.zip` too and drag both together to get the Black Label RANK bar and select screen artwork. `Ibara KURO.iso` appears
  next to the ISO.
* **Any system:** `python3 apply_kuro_patch.py "Ibara (Japan).iso" "Ibara KURO.iso" --bl-rom ibarablk.zip`

**`--bl-rom` (optional):** your own Ibara Kuro Black Label arcade ROM set (MAME's `ibarablk.zip`, or the
`ibarablk_u2` file from it; checked by size and CRC `5e46be44`). KURO's centred Black Label RANK bar and its ship
select screen use that ROM's artwork, copied from your ROM into the new ISO after verification; nothing from that ROM
is in this folder. If the same zip (or folder) also holds the sound ROMs `u23` and `u24` (CRCs `a436bb22`,
`d11ab6b6`), the select screen also plays Black Label's ship-select theme: the patcher decodes it from those ROMs
(about a minute) and stores it in the disc's resource archive; the disc does not grow. Without it, KURO shows Arrange's RANK gauge instead and has no select screen (FIGHTER TYPE in
CONFIG still picks the ship).

Needs ~3.7 GB of free space. The output is checked against the SHA-256 of the disc the patch was made from, and
deleted if it doesn't match. Keep it to yourself: it contains the game.

## What's on the disc

* **Mode Select:** ARCADE, ARRANGE, **NOIR MODE** (KURO / Black Label, third row), GALLERY, OPTION, EXIT. The row
  label and the blue NOIR MODE header use original letterforms from the PS2 disc. Selecting it switches on
  Black Label rules instantly. EXIT switches them off again.
* **Video.** Yoko stays interlaced and filtering is off in all orientations. TATE R / TATE L switch to full-frame
  240p with 240 active lines on NTSC output. Change the orientation in OPTION → SCREEN SETTING → SCREEN MODE.
* **RANK gauge:** Arcade defaults to OFF and KURO defaults to ON. Change either setting in its CONFIG menu.
  Both settings last for the current session. Attract mode suppresses the gauge.
* **Arcade slowdown test:** In ARCADE MODE → CONFIG, select SLOWDOWN just above EXIT and press Circle.
  It starts OFF and uses the original PS2 timing. With it ON, press **L2 + R2** together during active
  Arcade gameplay or Arcade Practice to switch between normal and forced half-speed. Release the chord
  before pressing it again. Returning to the frontend clears half-speed, so the next run starts at
  normal speed. The Config setting lasts until reboot. This build provides the manual test.
  Automatic arcade slowdown is still being calibrated. [MAME findings](../research/phase22/README.md#check-the-draw-deadline-in-mame) · [Original PS2 checklist](../tests/manual/ARCADE_SLOWDOWN_PS2.md)
* **Practice in every mode:** ARRANGE MODE now has PRACTICE (row 2), like ARCADE MODE. For Black Label, choose
  NOIR MODE → PRACTICE. Noir can select a stage and uses the default start data. PLAY DATA LIST is
  available in Arcade and Arrange Practice.
* **KURO Black Label RANK bar** (with `--bl-rom`): shown when enabled, centred under the high score as in Black
  Label — fill length, rank colours, the white flash at maximum rank and the fade when your ship is near it follow
  Black Label's code. The frame and plate use your ROM's artwork. KURO hides the stage-name line with either gauge.
* **KURO saves:** KURO skips the retail ranking and autosave flow. Leaving KURO restores the retail game,
  pad settings and Practice selections so changes made in KURO stay out of a later retail save.
* **KURO ship select screen** (with `--bl-rom`): starting a KURO game (player 1) opens Black Label's 武機選択
  screen before takeoff. Left / right picks the straight
  (シスター・シミリス) or spread (ディオ・スピロッソ) ship, Circle or Cross opens TYPE A–D (up / down, with the
  SPEED / POWER / bomb panel), then Circle or Cross starts takeoff. A 60-second timer keeps the current choice. The choice is
  also stored as FIGHTER TYPE. Player 2 presses Start once gameplay begins and joins with the ship chosen in
  CONFIG → FIGHTER TYPE. The opening art is static and uses a black background. With the sound ROMs, Black
  Label's ship-select theme plays on a loop while the screen is up and stops at takeoff; the stage music
  then starts as usual.
* **KURO weapon bar.** Arrange's seven-slot stock bar appears at the bottom. It marks the weapons you have
  collected and highlights the equipped one. Bomb stock and fragments sit above the bar. Press Square to cycle
  through your stock.
* **Gameplay scores.** The 1P label and score have a left margin.
* **KURO (Black Label, work in progress):** XTC graze scoring, bomb wipe, BL shot levels,
  BL rank rules for fragments, medals and roses, BL enemy HP
  (stages 1–6) and fire timing, held fire, 32-shot cap, MG pod aiming and BL pod fire rules, BL hit sparks (a
  shot that hits slows to a quarter speed, as in Black Label), enemy bullets
  cleared when a boss or mid-boss dies, no rank penalty for bombing. **Straight or spread:** the select screen, or NOIR MODE → CONFIG →
  FIGHTER TYPE offers STRAIGHT A–D and SPREAD A–D for each player. Practice works inside KURO. With `--bl-rom` the
  graze sphere (BL's orb on the ship while the shot is held) is drawn too. So is the XTC number popup ("+123" near
  the ship, fading). Not yet: the select screen's animation and background.

In game: Cross = shot, Circle = bomb, Square = weapon change (KURO). Menus: Circle confirms, Cross cancels.

## For maintainers

`ibara_kuro.patch` is made by `scripts/make_patch.py` from a disc built with `scripts/build_black_label_iso.py`
(default options). It holds disc copy instructions, including the source atlas coordinates for the NOIR MODE art,
alongside generated hook code, edited words, and directory records. `make_patch.py` caps the generated bytes
at 64 KiB total and 16 KiB per run. Regenerate it whenever the build changes:

```bash
python3 scripts/build_black_label_iso.py 'Ibara (Japan).iso' --output built.iso
python3 scripts/make_patch.py 'Ibara (Japan).iso' built.iso --output patcher/ibara_kuro.patch --note "<commit>: <options>"
```
