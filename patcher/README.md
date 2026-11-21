# Ibara KURO patcher

Turns your own Japanese **Ibara** disc image (`Ibara (Japan).iso`, SLPM-66301,
3,932,848,128 bytes, MD5 `6ba671b5d23155b8254b6f4cefc90ae2`) into **Ibara KURO.iso**: the retail game plus everything
this project has done so far. Your ISO is only read; no game data is in this folder.

## Use

* **Windows:** install Python 3 (python.org), then drag `Ibara (Japan).iso` onto `apply_kuro_patch.bat`.
  `Ibara KURO.iso` appears next to it.
* **Any system:** `python3 apply_kuro_patch.py "Ibara (Japan).iso" "Ibara KURO.iso"`

Needs ~3.7 GB of free space. The output is checked against the SHA-256 of the disc the patch was made from, and
deleted if it doesn't match. Keep it to yourself: it contains the game.

## What's on the disc

* **Mode Select:** ARCADE, ARRANGE, **KURO** (Black Label, third row), GALLERY, OPTION, EXIT. EXIT inside KURO
  returns to the normal game.
* **Video:** Yoko stays interlaced with texture filtering off; TATE R / TATE L switch to 240p progressive, live from
  OPTION → SCREEN SETTING → SCREEN MODE. The setting carries between the normal game and KURO.
* **RANK gauge in Arcade:** Arrange's RANK gauge (top right) also shows in Arcade, in both the normal game and
  KURO. The blinking "PRESS START" for the empty side is hidden, as in Arrange and Practice.
* **KURO (Black Label, work in progress):** XTC graze counter and HUD, bomb wipe, weapon stock with weapon change
  (Square) and weapon name on the HUD, BL shot levels, BL rank rules for fragments, medals and roses, BL enemy HP
  and fire timing (stages 1–2), held fire, 32-shot cap. Practice works inside KURO. Not yet: later stages' bosses,
  BL weapon behaviour (MG pod aiming and others), ship select, graze sphere.

In game: Cross = shot, Circle = bomb, Square = weapon change (KURO). Menus: Circle confirms, Cross cancels.

## For maintainers

`ibara_kuro.patch` is made by `scripts/make_patch.py` from a disc built with `scripts/build_black_label_iso.py`
(default options). It holds copy instructions into your disc plus the bytes that exist nowhere in the retail
executable (our hook code, edited words, directory records, the menu label); `make_patch.py` refuses to write a
patch with more than 64 KiB of such bytes or any run over 4 KiB. Regenerate it whenever the build changes:

```bash
python3 scripts/build_black_label_iso.py 'Ibara (Japan).iso' --output built.iso
python3 scripts/make_patch.py 'Ibara (Japan).iso' built.iso --output patcher/ibara_kuro.patch --note "<commit>: <options>"
```
