# Phase 20 — Black Label's ship select screen: inventory (2026-11-22)

**Only in Black Label.** The select screen is BL-only code (`0C0B8210`, 1,618 instructions, with `0C070DC0`,
`0C0703C0`, `0C0734D0`; Phase 11 found no arcade Ibara counterpart). Arcade Ibara and the PS2 port have no select
screen: the pilot is the side (P1 Bond, P2 Dyne) and PS2 sets the type in CONFIG > FIGHTER TYPE. The PS2 disc's
textures (`IBARAR.PDM`, 1,113 TIM2) hold the GALLERY sketches and one colour ship illustration, none of this screen.

**What it shows** (MAME snapshots): 武機選択 header with a 60-s timer; per player a metal panel with the pilot (P1 Bond,
P2 a second pilot with blue ships), the ship's name (シスター・シミリス straight, ディオ・スピロッソ spread),
直進型 / 拡散型 labels, a large ship render; a 参戦可能 "join" panel for the free side; 左右で機体を選択 prompt; a girder
background that fades in; a dissolve / fly-in transition when the ship changes.

**How it is drawn.** Blitter job lists in RAM (`0C3CC400` / `0C46C500`, double-buffered); draw op = 10 BE words
(attr 0x1xxx: d_mode, s_mode, trans, blend, flipy, flipx; alpha; src x, y; dst x, y; w-1; h-1; tint R; tint GB),
upload op = 0x2xxx with dx, dy, w-1, h-1 and the pixels inline. `bl_blitter_log.lua` logs both from power-on;
`map_uploads.py` maps the 19,834 uploads (256 × 5-row strips of 256-wide images, 512-byte stride) to 3,572 rectangles
in the ROM (all found). The select screen runs ~830-890 draw ops a frame (most are 32 × 32 background tiles); 940
distinct source rectangles over 267 logged frames; 333,120 ROM-backed blitter pixels sampled (~650 KB as 16-bit,
~10 of our 256 × 128 pages) plus 113,920 frame-buffer pixels (x 960-1315, y 136-455: copy effects, not ROM art).

## Findings for the PS2 port (2026-11-22)

**Coordinates.** The blitter double-buffers at scroll x 32 / 416 (register `0x18000014`), y origin 136: game
coordinates = dst − (buffer x, 136); landscape, game x up the portrait screen. PS2 keeps the same system: its HUD
offsets are x 416 / y 136 (`$gp-28648` / `$gp-28640`), so a BL draw op maps onto `0x00110B70` directly:
x = dst_x − origin + 416, y = dst_y − 136 + 136; w (along x) = op w, h (along y) = op h; texture = the source rect
in a page of ours (screen orientation: pixel (row i, col j) = blitter (sx + w − 1 − i, sy + j)); tint = R << 16 |
GB (0x80 = 1.0, same as PS2); a0 = 0x10000000 | (attr & 0x277) << 16 (blend bit, s_mode, d_mode — PS2 tests the
same d_mode 7 / s_mode 1 values at `0x00110DCC`; Arrange's gauge uses blend + d_mode 4 = 0x2040000) | flipx →
0x08000000, flipy → 0x04000000 | alpha word (s_alpha << 8 | d_alpha, as PS2).

**Screen contents per frame** (≈ 830-890 ops): 414 32 × 32 tiles compose the girder background off-screen
(blitter x 960-1315, y 136-455), copied to the screen one 1-px row at a time with a per-row x offset (a heat-shimmer
wave) and tint 0x58 (dark); ~80-100 element ops (header 武機選択 at game x 272-311, timer, the two side panels at
y < 120 / ≥ 120, portraits, ship renders, name plates, the join panel, prompt, 8 × 8 font text for CREDIT / PRESS
START). Steady state: ~10 ops animate (pulsing / blinking); a ship change plays ~30 frames of moving ops (fly-in);
P2 joining switches that panel.

**Sizes.** Element art (everything but the background tiles and the frame-buffer copies): 150 distinct source
rects, 179,520 pixels = 5.5 pages of 256 × 128 PSMCT16 (fits the 6-page area at `0x01F20000`); the background adds
the tile set (stage 2 of option 3).

**Holding the game while the screen is up.** The main loop (`0x0012E1E4`) skips the game update while the pause
byte `$gp-28128` is set and then calls the pause menu `0x00128E10` (`jal` at `0x0012E778`; returns 0 = stay, 3 =
restart / title); the HUD pass (and our sprites) still render. KURO plan: set the byte at the start of a KURO game,
replace that call with the select screen's own (draws, reads the pad, returns 0), then write the ship word / FIGHTER
TYPE config and clear the byte.

**Art delivery plan.** Pages pre-laid-out by the patcher from the user's ROM (vram_map offsets + an atlas layout,
both coordinates only) into an extra loadable segment of the frontend executable at `0x01F20000` (zeros on the
disc without `--bl-rom`; the executable's disc extent has ample free space, the ISO size is unchanged).

## The select flow (captures, 2026-11-22)

`bl_select_capture.lua` (one player; Right / Left, button, Down ×4, Up, button):

1. **Ship:** left / right picks straight (シスター・シミリス, 直進型) or spread (ディオ・スピロッソ, 拡散型); a fly-in
   transition (~30 frames) on each change; prompt 左右で機体を選択.
2. **Type:** the button opens TYPE A / B / C / D (up / down; prompt 上下でカスタムタイプ選択) with SPEED / POWER bars and
   the bomb kind (拡散 / 爆発 / 直進 / 全方位 ...) — BL chooses the type here, not in a settings menu.
3. **Confirm:** the button flashes the ship; the panels dissolve into the girder background, the ship launches, a
   pilot illustration plays, then stage 1.

The free side shows the 参戦可能 / PRESS START join panel; with two players each side runs the same two steps.
Per frame the P1 panel is ~40-50 ops; steady states have no single loop period (several independent animations:
pulsing highlights, blinking text, bobbing arrows), so the PS2 version will animate elements individually rather than
replay frame lists.

## Stage two: what is behind BL's select screen (2026-11-25)

The "girder background" is **not select-screen art**. MAME, select screen open from Start (`draws.txt` of the K29 capture,
blitter VRAM read through the `*m_bitmaps` item):

* BL composes 117 cells (13 × 9) of 16 32 × 32 tiles off screen (blitter x 987–1403, y 128–447). The tiles at VRAM
  (0x0–0x5F, 0x800–0x8FF) are **stage 1's water layer** (the VRAM dump shows the water texture; the upload map's later
  upload there is the same stage art). The composite is copied to the screen one 1-px row per op (320 ops a frame) with a
  heat-shimmer x offset: a 64-row profile of 0–6 px (3,4,4,4,5,5,5,5,6×17,5,5,5,5,4,4,4,3,3,3,3,2,2,2,2,1×8,0,1×8,2,2,2,2,
  3,3,3), moving one row every 4 frames; rows shifted 4 or more copy from 32 px further left to keep the edge covered.
* The tint of that copy is 0 for the first ~44 frames after the screen opens, then rises 2 a frame to 0x80 (the stage's
  own fade-in). The launch tower (the "girders") is drawn by the stage as usual, on top of the water.
* So BL keeps **the live stage 1 opening** (launch pad) running behind its select screen: black, then the stage fading in.

**PS2.** Showing the stage instead of hiding it (`sel_layers_stub` only for the first 44 frames) still gives black:
the PS2 select screen opens on the first frame of scene 1, under NOW LOADING, and the game update is paused from then
on (`sel_pause`), so the launch tower has not been spawned and the stage never fades in. After confirm, the stage
appears within ~0.5 s (with the retail "Bond 01 Agent" pilot panel, the PS2 counterpart of BL's pilot illustration).
Options were: (a) let the update run until the launch pad is up, then pause and open the screen; (b) keep the update
running and hold the takeoff script; (c) leave it black. **(a) is built (K51):** `sel_begin` also waits for the NOW
LOADING fade (`$gp-28936`, 0x00338BE8) to reach 0, and the stage-hiding stub at `0x0012E234` is gone, so the launch
pad (tower girders) stays drawn under the panels. Before the screen opens the PS2's own NOW LOADING plays (BL: 44 black
frames); the takeoff and the "Bond 01 Agent" pilot panel still follow the confirm. PCSX2: the full 60-s timer with both
players (P2 joining, ship and type changes) ran without texture-cache trouble and started a two-player game. Not
reproduced: BL's water shimmer and its fade-in of the stage behind the screen.

## Animation and confirm (stage two, K52, 2026-11-25)

**Captures.** `bl_select_capture_long.lua` (player 1, KIND S / P) and `bl_select_capture_long_p2.lua` (player 2) hold
every state for 240 frames: ship, other ship, back, type A–D, Down past D, Up. Every element of a state settles within
34 frames of the state's entry (the transition: the screen's opening slide, the ship fly-in and dissolve, the type
panel sliding out) and then loops with a period of 32 or 64 frames; values change every 2 frames.

**Data** (`make_select_anim.py`, `make_select_data.py --long`): 24 states (the 22 before, plus the screen opening for
player 1 and player 2's joining). A state is a list of tracks in BL's draw order (the order matters: the type panel
sits behind the bottom plates until it slides out). A track is a sprite, its first position, an intro and a 64-frame
loop of samples (every 2 frames); a sample is a record: position delta, 0x00110B70 flags (blend, flips, alpha), tint,
or not drawn. 875 tracks (1,532 references), 764 records, 4,095 samples, 202 flag and 85 tint values: about 25 KB,
replacing the 15 KB of single-frame ops. Sprites inside another sprite are drawn from that sprite's page area (237
sprites, 230 packed).

**Runtime** (`bl_select.c`): three slots (header, player 1, player 2 / join panel) each remember their state and the
frames since they entered it; the screen's opening and player 2's joining keep their own tracks while the straight
ship stays selected.

**Confirm** (`bl_select_capture_confirm.lua`): BL lights the ship render up (tint 252, down 8 every 2 frames to 132)
and draws a white additive copy over it (alpha 0xE8, down 0x10 every 2 frames, frames 3–32); a few elements flicker
slightly. From frame 34 the panels dissolve — BL copies strips of the frame buffer — and the stage shows from frame
~64. Noir reproduces the flash per side (from that side's confirm) and replaces the dissolve with a fade of every
element's blend alpha (0xF7 down 0x10 every 2 frames; unblended elements go at half way), closing the screen at
frame 64 after the last confirm (or the timer). The PS2's own pilot panel and takeoff follow.

BL's "dissolve", snapshotted every 3 frames (`bl_select_capture_confirm.lua`), is a cross-fade of the whole composed
screen into the stage over ~30 frames (the frame-buffer copies are how the blitter fades everything at once); Noir's
per-element fade matches it, except that overlapping pieces can show through each other for a moment.

**Water shimmer.** BL composes stage 1's water from 32 × 32 tiles off screen and copies it to the screen one row at a
time with the 0–6 px wave in **normal play** too (344 row copies in a stage-1 gameplay frame), not only behind the select
screen. The PS2 port has it too (the user's observation watching stage 1; screenshot comparison here was ambiguous:
the wave is computed, no table in either program, and the texture repeats). Open nuance: behind the select screen the
PS2's update is paused, so its shimmer may stand still there while BL's keeps moving (mostly hidden by the launch pad).

Not reproduced: the slight flicker during the flash, transitions that depend on the
direction a type was reached from (each state has the transition of one entry: type B from A, C from B, D from C).

## Side select and the opening's music (G2 / G3, K53, 2026-11-25)

**Black Label** (MAME, a coin and only 2P Start): player 2 plays alone. The select screen opens with player 2's panel
and player 1's 参戦可能 join panel; stage record 7 → 0 (the opening, with the select screen over it) → 1. Either side
can start, and the free side can join with its Start while the screen is up.

**Noir before K53:** GAME START on controller 2 started a player-2 game (the retail start reads the pressing pad) but
skipped the select screen. Now `sel_begin` opens for whichever side started; the free side shows its join panel
(`join_P1`, from `bl_select_capture_join_p1.lua`, or `join_P2`); either free side joins with Start; on confirm each
side gets FIGHTER TYPE and ship word `value XOR 4 * side` (K25), with the retail player set-up `0x0012D840` for a
side that joined on the screen. PCSX2: controller 2 starts → player 2's panel and player 1's join panel; player 1
joins with Start, picks spread; both confirm; two-player takeoff (P1 ship word 4, P2 4). Player-1 starts unchanged.

**The opening's music (G2).** Both games play record 0 (the opening) before stage 1; BL's opening script fades the
music (`FF26` = sound command (0, 16)) where the PS2's runs `FF0A`. The PS2's fade is `0x0010F570(0, 16)` (used by its
scene scripts, e.g. `0x001150C0`): the update `0x0010FBD0` lowers the request volume (`0x00345572`) 16 steps a frame
while `$gp-29212` is set, then stops the stream. Noir's select theme used to stop abruptly at confirm; it now fades
out over about 1.5 s (PCSX2: volume 88 → 0, stream stopped) unless the stage already has a track.

## Running on PS2 (stage one, 2026-11-22)

`ps2/hooks/bl_select.c` with the art pages from `--bl-rom` (`bl_tex.c`: six PSMCT16 pages, each a texture object
cloned from the HUD page's). PCSX2, KURO stage 1: the screen opens once the stage runs, Right switches to the spread
ship, Circle / Cross opens TYPE A–D, Down moves to TYPE B, Circle / Cross resumes the stage with ship word 5 (spread,
type B; FIGHTER TYPE 5); with no input the 60-s timer runs out and the stage resumes with the current choice.
Arrange is unchanged (no select screen, its gauge and PRACTICE row as before). Pad: `0x00341FA0 + port * 0x50`,
+0x0C directions (bit 0 up, 1 down, 2 left, 3 right), +0x08 button edges (0x10 Circle, 0x20 Cross).

**The freeze, solved.** With more than one of our pages on screen the game froze within a few frames (TLB misses at
0x4C / 0x50 from the sprite routine's batch list). Bisecting by page pointed at the GS texture cache, but a PCSX2
trace (TLB message with registers) showed `gp = 0xFFF20000` inside `0x00110B70`; gp checks around every sprite call
showed it changing *between* two of our calls, in our own C code, which never writes gp. The main thread's
register save area on its stack (found in a savestate below its sp) held the same gp: the kernel saves a preempted
thread's registers on that thread's stack with `sq`, and our hooks were o32 code whose frames are only 8-byte
aligned; a thread switch while our draw loops ran therefore saved / restored registers on a misaligned stack (`sq` /
`lq` ignore the low address bits) and gp came back corrupted. The longer our code runs per frame, the likelier — one
page worked, the full screen did not. Fix: the hooks are built for n32 (`-mabi=n32`, `ld -m elf32ltsmipn32`), whose
frames are 16-byte aligned like the game's (tests check every `addiu sp` in the KURO image). n32 passes arguments 5-8
in `$8-$11`, as the game's own EABI code does.

**Stage hidden while the screen is up.** `jal 0x00112500` at `0x0012E234` (before the draw pass's 24-layer loop)
returns to `0x0012E424` (the HUD calls) while the screen is up: BL's screen covers the playfield, and nothing after
the loop reads its registers. The HUD still draws (score line, RANK bar).

**Patch.** The hook image now has a literal run of ~9 KB (code + `bl_select_data.c` tables);
`scripts/make_patch.py` allows 16 KiB per run (64 KiB total, unchanged). `ibara_kuro.patch` 9.8 KB; patch +
`--bl-rom` gives the same disc as `build_black_label_iso.py --bl-rom` (byte-identical).

Stage two: done (K51 stage behind the screen, K52 animation and confirm, sections above). Player 2: done
(K46, below).

## Before takeoff (2026-11-22)

KURO now opens ship select in scene 1, once the HUD texture table is ready. The retail pause check
(`0x0012C220`, called at `0x0012E1AC`) rejects pauses in that scene. `sel_pause` overrides the result while
the menu is active, so the ship stays on the launchpad. Confirming a ship and type sets the ship word and
resumes the retail takeoff. The final result of the pause check comes from the retail routine at all other times.

Arrange's stock bar (`0x001285C0`) uses the same seven slots and equipped-weapon ID as KURO. In KURO the
draw call at `0x0012E434` shows that bar outside ship select. The selector hides the RANK gauge and clears
the XTC text cells. PCSX2 held P1 on the launchpad in Yoko and Tate R, then took off with Spread B (ship word 5).
With MG and Rocket stocked via PINE, pressing Square changed the active weapon and the bright slot from MG
to Rocket. After game over, the three patched call/branch words for pause and the stock bar were restored.

## Player 2 (K46, 2026-11-25)

**Black Label (MAME).** While the select screen is up, the free side shows the 参戦可能 join panel. Player 2's Start opens
their own panel (blue pilot and ships, "Player2" plate). Both sides then choose ship and type independently on the
shared 60-s timer. A player who joins later in the game gets **no** select screen.

**Data.** `bl_select_capture_p2.lua` (VARIANT S / P) repeats the one-player captures' inputs with player 2, started
at frame 120. MAME's player-2 controls are on `:PORT_L`. `make_select_data.py --p2` adds ten states from the
`y >= 120` half: `ship_S2`, `ship_P2`, `type_S2A`–`D` and `type_P2A`–`D`. That makes 22 states, 231 sprites and
216,592 px. It needs **eight** texture pages: `KT_PAGES` 8, art segment `0x01F20000`–`0x01F9FFFF`, page-table row 6
cols 0–7, all free in the retail table. RAM `0x01F80000`–`0x01FBFFFF` was zero in every savestate checked (select
screen, gameplay, stage 6). The rank bar's object moved to index 8, and the packer now also keeps page 5 rows 96–127
(graze sphere, XTC digits) free.

**Runtime** (`ps2/hooks/bl_select.c`):
* Per-side state: on, phase (ship / type / confirmed), kind, type.
* **Joining:** player 2 joins with Start, read from their mapped input word (`+0x24E` bit `0x200`, which honours
  KEY CONFIG and is updated while paused), and starts on their CONFIG fighter type. The free side draws the join
  panel.
* **Finishing:** the screen closes when every joined player has confirmed, or when the timer runs out.
* **Bringing player 2 in:** the retail join (`0x0012C5E4`): FIGHTER TYPE, ship word = value XOR 4 for side 1 (as
  KURO's join, K38), then the player set-up `0x0012D840(1)`.

**Check (PCSX2).**
1. Player 2's side showed the join panel.
2. P2 Start opened player 2's panel.
3. Player 2 went to spread, type B, while player 1 picked spread, type B and confirmed first. Player 1's panel held
   while player 2 chose.
4. Player 2 confirmed, and both ships stood on the runway and took off together. P1 ship word 5 (FIGHTER 5); P2
   FIGHTER 5, ship word 1; both active.

The patch's longest literal run (our hook image) is now 16,720 bytes, so `make_patch.py` allows 24 KiB per run;
the total stays capped at 64 KiB.

## Type changes (K57)

Hardware report: scrolling up through the types made the cursor jump, and landing on type A replayed the panel
sliding in. The long captures step A → B → C → D with Down, so type A's transition is the panel's slide-in from the
ship screen and B–D's first samples still show the type above (cursor and info). BL itself just swaps the panel's
content on a type change (the same captures' wrap D → A and Up A → D: one sample of the old content, then the new).
`draw_slot` now starts a type state after its transition when it comes from another type, or from the ship screen
into B–D. PCSX2: bursts of screenshots on C → B, B → A, A → D, D → A each show a single clean swap.

## Two-player takeoff (26 November 2026)

BL (MAME, both players confirm on the select screen): both ships stand on the launch pad and take off together.
Noir since K51: the select screen opens after NOW LOADING, when the takeoff already runs for the starting player;
the side that joined on the screen gets the retail join (player state +0x0C = 1, entering from below) and appears
after the takeoff. Takeoff savestate: starter +0x0C = 2, y 544, speed words 0x24000; joined side +0x0C = 1, y 480,
0x2C000; same x (66). Copying the starter's takeoff fields put the joined ship behind the other one, not beside it.
Matching BL needs the PS2's own two-player takeoff positions (the K53-era runs, when both records existed before the
takeoff began, did take off together).

**Fixed (K59).** In the retail two-player takeoff both records carry their own side's position (+0x14: 480 / 544,
the screen's horizontal axis in tate) and speed words; the retail join already sets those. The joined side only
lacked the takeoff step (+0x0C) and the invincibility counter (+0x278). Copying just those two from the other
player puts both ships on the pad together (the earlier attempt also copied the position, which stacked the ships).
