# Ibara KURO patcher

Turns your own Japanese **Ibara** disc image (`Ibara (Japan).iso`, SLPM-66301,
3,932,848,128 bytes, MD5 `6ba671b5d23155b8254b6f4cefc90ae2`) into **Ibara KURO.iso**: the retail game plus everything
this project has done so far. Your ISO is only read; no game data is in this folder.

## Use

* **Windows:** install Python 3 (python.org), then drag `Ibara (Japan).iso` onto `apply_kuro_patch.bat` — select
  your `ibarablk.zip` too and drag both together to get the Black Label RANK bar and select screen artwork. `Ibara KURO.iso` appears
  next to the ISO.
* **Any system:** `python3 apply_kuro_patch.py "Ibara (Japan).iso" "Ibara KURO.iso" [--bl-rom ibarablk.zip]`

**`--bl-rom` (optional):** your own Ibara Kuro Black Label arcade ROM set (MAME's `ibarablk.zip`, or the
`ibarablk_u2` file from it; checked by size and CRC `5e46be44`). KURO's centred Black Label RANK bar and its ship
select screen use that ROM's artwork, copied from your ROM into the new ISO after verification; nothing from that ROM
is in this folder. Without it, KURO shows Arrange's RANK gauge instead and has no select screen (FIGHTER TYPE in
CONFIG still picks the ship).

Needs ~3.7 GB of free space. The output is checked against the SHA-256 of the disc the patch was made from, and
deleted if it doesn't match. Keep it to yourself: it contains the game.

## What's on the disc

* **Mode Select:** ARCADE, ARRANGE, **KURO** (Black Label, third row), GALLERY, OPTION, EXIT. KURO switches the
  Black Label rules on instantly (no reload) and opens its menu: GAME START, PRACTICE, CONFIG, EXIT (the header still
  reads ARCADE MODE). EXIT switches them off again.
* **Video:** Yoko stays interlaced with texture filtering off; TATE R / TATE L switch to 240p progressive, live from
  OPTION → SCREEN SETTING → SCREEN MODE.
* **RANK gauge in Arcade:** ARCADE MODE → CONFIG → RANK GAUGE ON/OFF (starts ON). ON shows Arrange's RANK gauge
  (top right) in Arcade (and in KURO when no `--bl-rom` was given), and hides the blinking "PRESS START" for the empty side,
  as in Arrange and Practice. Not saved to the memory card.
* **Practice in every mode:** ARRANGE MODE now has PRACTICE (row 2), like ARCADE MODE; KURO's practice is
  KURO → PRACTICE.
* **KURO Black Label RANK bar** (with `--bl-rom`): always shown in KURO, centred under the high score as in Black
  Label — fill length, rank colours, the white flash at maximum rank and the fade when your ship is near it follow
  Black Label's code; the frame and plate use your ROM's artwork, colours exact. The PS2 stage-name line is hidden there in KURO (Black Label has none).
* **KURO ship select screen** (with `--bl-rom`): starting a KURO game (player 1) opens Black Label's 武機選択
  screen, drawn from your ROM's artwork with Black Label's layout: left / right picks the straight
  (シスター・シミリス) or spread (ディオ・スピロッソ) ship, Circle or Cross opens TYPE A–D (up / down, with the
  SPEED / POWER / bomb panel), Circle or Cross starts; a 60-second timer keeps the current choice. The choice is
  also stored as FIGHTER TYPE. Stage one of the port: no element animation or ship fly-in yet, a black background
  instead of the girder wall, player 2 still joins with FIGHTER TYPE.
* **KURO (Black Label, work in progress):** XTC graze counter and HUD, bomb wipe, weapon stock with weapon change
  (Square) and weapon name on the HUD, BL shot levels, BL rank rules for fragments, medals and roses, BL enemy HP
  (stages 1–6) and fire timing, held fire, 32-shot cap, MG pod aiming and BL pod fire rules, BL hit sparks (a
  shot that hits slows to a quarter speed, as in Black Label), enemy bullets
  cleared when a boss or mid-boss dies, no rank penalty for bombing. **Straight or spread:** the select screen, or KURO → CONFIG →
  FIGHTER TYPE offers STRAIGHT A–D and SPREAD A–D for each player. Practice works inside KURO. With `--bl-rom` the
  graze sphere (BL's orb on the ship while the shot is held) is drawn too. Not yet: the XTC number popup next to
  the ship, the select screen's animation and background.

In game: Cross = shot, Circle = bomb, Square = weapon change (KURO). Menus: Circle confirms, Cross cancels.

## For maintainers

`ibara_kuro.patch` is made by `scripts/make_patch.py` from a disc built with `scripts/build_black_label_iso.py`
(default options). It holds copy instructions into your disc plus the bytes that exist nowhere in the retail
executable (our hook code, edited words, directory records, the menu label); `make_patch.py` refuses to write a
patch with more than 64 KiB of such bytes or any run over 16 KiB. Regenerate it whenever the build changes:

```bash
python3 scripts/build_black_label_iso.py 'Ibara (Japan).iso' --output built.iso
python3 scripts/make_patch.py 'Ibara (Japan).iso' built.iso --output patcher/ibara_kuro.patch --note "<commit>: <options>"
```
