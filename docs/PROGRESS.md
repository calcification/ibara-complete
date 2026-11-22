# Progress report — 22 November 2026

Where Ibara Complete stands: the retail PS2 Ibara (SLPM-66301) plus **KURO**, the Black Label rules switched on
from Mode Select. Arrange stays as on the original disc, with one addition: a PRACTICE row. Delivered as
`patcher/` (a 9.8 KB patch; no game data in the repository). Black Label art comes from the user's own `ibarablk`
ROM (`--bl-rom`).

## How far along

The percentages below are an estimate from the feature checklist (`docs/BLACK_LABEL_FEATURES.md`) and the test
matrix. They are not a measurement.

| Area | Done | Estimate |
|---|---|---|
| Disc, menus, delivery | KURO row in Mode Select, switched on instantly without a reload; patcher (Windows drag-and-drop / Python); `--bl-rom` art injection; byte-identical rebuild check; repository safety check | ~95 % |
| Video | Yoko interlaced without filtering, Tate 240p progressive, switched live and kept on the memory card | done in PCSX2; real hardware partly |
| Player rules (F1–F7, F10) | XTC graze counter + HUD + bomb wipe; weapon stock + change button; shot levels to 6, no secret; held fire every 2 frames; 32-shot cap; pod aiming, pod fire rules, no rank per pod shot; BL hit sparks; bombs (no rank, type D by ship); straight/spread A–D; bullet cancel after bosses and mid-bosses | ~85 % |
| Rank (F8) | stored-rank format, fragment / medal / rose rules, enemy fire timer from rank, RANK bar | ~70 % (bomb and Hadou cancel rank rules open) |
| Enemies and stages (G5–G7) | BL enemy HP formula, enemy part HP stages 1–6, fire timer, stage-1 placement and boss checked against MAME | ~35 % — the largest open area: ~288 BL routines that touch enemy parts changed; stages 2–6 behaviour not compared routine by routine |
| Presentation (F11, A1) | BL RANK bar (exact colours); BL select screen stage one (ship → type → confirm, 60-s timer, BL layout and art) | ~50 % (select animation / fly-in / girder background / player 2; graze sphere; title logo) |
| Game flow (G1–G3) | KURO enters through Arcade's menu | ~30 % (single 6-stage loop rules, opening record, side select) |

**Overall: roughly 60–65 %** toward a Black Label mode that plays like the arcade. Nearly everything the player touches
directly is done and checked against MAME. Most of what's left is enemy and stage behaviour, plus presentation.

Tests: 65 entries in `TEST_MATRIX.csv`, 39 PASS. Every KURO row from K02 to K30 passes; K01 (the early attract-demo
check) is superseded by K03. The rest are older optional or hardware rows. Unit tests: 48 pass.

## Done since the last report

* **KURO select screen** (K29), stage one, art from the user's ROM. The freezes on the way came from a stack-alignment
  bug in all hook code (8-byte o32 frames; a thread switch corrupted `gp`). Hooks are now built as n32 with
  16-byte frames, and a test checks every frame.
* **Hit sparks as BL** (K30). This was the "MG pod margin" item. MG pod shots per 1,000 frames: 317 → 209 (BL 208).
* Carry-over notes for the next project (`docs/NEXT_MUSHIHIMESAMA.md`).

## Next, in order

1. Graze sphere (F4, last XTC item).
2. Pod shot counts still apart from BL: 5-way, homing, napalm (targeting / fire rules).
3. Rank on bomb and Hadou cancels (F8).
4. Enemy and stage delta, stage by stage, starting with player-shot damage and reach (G6). This is the biggest block.
5. Select screen stage two (animation, fly-in, girder background, player 2); BL title logo.
6. Game flow G1–G3; then a test on real hardware.

## Known gaps

* KURO has been tested in PCSX2 (and MAME for BL behaviour); not yet on a real PS2.
* While the select screen is up, the stage isn't drawn (black background). The HUD's "♪Show Time" track
  line still shows (BL has no Show Time).
