# Phase 18 — Load screens: where the time goes (2026-11-21)

Question: can the PS2 port's NOW LOADING screens be made faster? Measured in PCSX2 (full speed, ~60 frames/s,
disc timing emulated, Fast CDVD off), Arcade NORMAL from the difficulty menu to stage 1:

| after Start | screen |
|---|---|
| 0–2 s | NOW LOADING |
| 2.5–7.5 s | opening scene |
| 7.5–12.5 s | NOW LOADING (stage 1) |
| 13 s | gameplay |

## Findings

* **Data**: stage data is read from IBARAR.PDM (241 MB archive, index IBARAR.TBL) in 64-sector (128 KB) requests;
  the content is uncompressed TIM2 textures, so there is no decompression cost. Reads hop between several areas of
  the archive (3–4 interleaved files) plus the BGM stream (40-sector reads every ~1.6 s near LBA 1869000).
  Stage-1 load: ~11 MB.
* **The disc is not the main cost**: one 128 KB request every ~134 ms (8 frames). With PCSX2's Fast CDVD (it only
  halves timings) the stage-1 load went 5.0 → 4.5 s. With a research build that makes disc reads near-instant
  (`CDVD_INSTANT`), requests still came only every ~83 ms (5 frames): the pipeline handles one chunk per ~5 frames
  however fast the drive is (≈1.5 MB/s ceiling, ≈1 MB/s with real disc timing).
* **Both CPUs are mostly idle while loading** (sampling profiler added to the local PCSX2 build, `EE_PC_SAMPLE`,
  one sample per scanline): EE ~90 % in the kernel idle loop (0x81FC0), IOP ~80 % in its kernel idle area. The
  remaining EE time is the normal per-frame work (loading-screen drawing). So the time is spent waiting in a serial
  request → read → hand-over → next-request chain, not computing.
* **Not the cause**: MTSFILE.IRX (the game's IOP file-streaming module, Taito "MTS" middleware) polls with
  DelayThread(10 ms) in five places of its read state machine (.text 0x454, 0x4D4, 0x4F8, 0x5FC, 0x610). Patching
  them to 1 ms changed nothing (stage-1 load still ~5 s, read spacing still 134 ms).
* EE side: sceSifCallRpc is at 0x0014BFF8 (sceSifInitRpc 0x0014B6E8); the MTS file client wrappers are
  0x001AAC00–0x001AC61C; an EE-side RPC server (id 0x109904, handler 0x001AB440) receives IOP notifications. Hooking
  sceSifCallRpc's entry to log calls crashed PCSX2 itself (segfault in the emulator process), so the per-chunk call
  timeline is still unknown.

## Where a speed-up would have to come from

The chunk hand-over between the IOP streaming module and the game (one 128 KB chunk per ~5 frames, no overlap with
the next disc read). Options, in order of expected gain / effort:
1. Find the chunk/bank size the EE passes to MTSFILE / CDVDACCS (stream buffer setup) and raise it (e.g. 4×), so the
   fixed per-chunk overhead is paid 4× less often — needs the EE→IOP call that opens the stream.
2. Overlap: let the IOP read the next chunk while the EE consumes the current one (double buffering).
3. Bound: removing the per-chunk overhead entirely leaves the disc time (~50 ms per 128 KB with seeks), i.e. the
   5 s stage-1 load could drop to ~2 s at best on PCSX2 timing; real drives differ.

Research builds used here (local only): PCSX2 `rcntUpdate_hScanline` sampler (EE pc, ra, IOP pc per hblank, env
`EE_PC_SAMPLE`), `CDVD_INSTANT` env to cap CDVD read/seek events at 64 cycles; PCSX2 `CdvdVerboseReads` for the read
log.

## Ship kind (F1) and bombs (F7) in KURO (2026-11-21)

**PS2 has no ship select.** NORMAL goes straight to loading; CONFIG > FIGHTER TYPE (frontend state 7, Arrange 11)
sets the type per player (Arcade config `0x004E5050` / `0x004E5054`, labels `0x002A9370`), and the player-start code
writes the ship word (player `+4`) as side × 4 + type at `0x001CE728` / `0x001CE730`, so P1 is always Bond
(= BL straight) and P2 Dyne (= BL spread), as in arcade Ibara. BL lets either player pick straight or spread
(Phase 13: BL indexes the same mechanics by kind × 4 + type). A PCSX2 run with P1's ship word forced to 4 played
normally with Dyne's ship, spread shot and bomb.

KURO (`ps2/hooks/bl_ship.c`, `BL_SHIP_PATCHES`, all runtime-switched with the KURO table):

* FIGHTER TYPE rows take 8 values with our labels: PLAYER 1 STRAIGHT A–D / SPREAD A–D, PLAYER 2 SPREAD A–D /
  STRAIGHT A–D (popup length 4 → 8 at `0x001C9710`; popup list `0x001C970C` → `ship_popup_tab` for the edited row;
  value columns `0x001C995C/60`, `0x001C9980/84`; help lines `0x001C9808/0C`, `0x001C9838/40` from a 24-entry copy
  of the retail table so every value shows its pilot's description). The game's popup shows 4 rows at a time.
* Ship word = side × 4 **XOR** value (`0x001CE728` `addu` → `xor`): values 0–3 give the retail ship, 4–7 the other
  pilot's set.
* `kuro_set` keeps the choice while KURO is off and clamps the config to 0–3 for the retail modes (restored on
  entering KURO when the retail value was not changed meanwhile).

**Bombs.** BL's trigger `0C073600` (arcade `0C062550`) waits 7 frames after the press (+0x268), spends a bomb
(power +0x266 = 40) or, with none, the fragments as a partial bomb, spawns the bomb record (`0C07B620`, pool
`0C229004`, type side + 9) and jumps through an 8-entry per-ship table: straight A–D `0C07A7B0`, `0C07A920`,
`0C07AA90`, `0C079600`; spread A–D `0C07A280`, `0C07A410`, `0C07A100`, `0C079600`. Against the arcade (Phase 11):

* five routines differ only in relocated operands (record stride 0x280 → 0x2A0, power +0x25F → +0x266);
* spread B (`0C07A410`) reads the stick as a word (`mov.w`) instead of a byte: on the big-endian SH-3 the arcade
  read the wrong byte; PS2's port (`0x00119BC0`) already reads it with `lhu` — no change;
* type D (`0C079600`, both kinds) picks its pattern table and repeat count by ship kind where the arcade
  (`0C068570`) and PS2 (`0x0011B460`: `$gp-32640 + side*4`, `side + 1`) use the player side. KURO: `bomb_d_kind`
  at `0x0011B480` / `0x0011B4F4` (identical to retail while kind = side);
* the arcade trigger calls harder(0x1000) (`0C060350`) per bomb; BL's has no rank call. PS2 Arcade does
  harder(0x1000) twice per full bomb, 0x4000 on a fragment bomb and 0x10000 on the held path, and skips them all in
  Arrange; KURO takes the Arrange branches (`0x0013B0C4`, `0x0013B11C`, `0x0013B258`, `0x0013B274`).
* MAME probe (`bomb.lua` variants): straight A's bomb is type-5 records for 38 frames then type-0 debris to ~110;
  spread A's is type-3 records for 96+ frames — different weapons per kind, as on PS2 per pilot.

PCSX2 (K25): KURO FIGHTER TYPE shows the 8 labels and per-value help; P1 SPREAD A → ship word 4, Dyne's ship and
spread shot, spread bomb; SPREAD D → ship word 7; the choice survives EXIT and re-entering KURO; bomb-rank and
D-bomb words are on in KURO and retail outside it.

**KURO practice Game Over (fixed).** Returning to the practice menu after a practice Game Over passes through
frontend state 0, which the safety net (`kuro_frame`: state ≤ 1) took for the title and switched KURO off — the
practice menu then ran retail rules (diagnostic word `kuro_off_why` = state 0). The net now acts on Mode Select
(state 1) and the attract edge only. PCSX2: KURO practice to Game Over → back at the practice menu with KURO on;
KURO Arcade to Game Over → KURO off at the attract edge (`kuro_off_why` 0x303).
