# Stage compare: Black Label (MAME) vs the PS2 BLACK LABEL build (PCSX2)

One command logs one stage in both games under the same controlled conditions and writes a per-enemy-type and
per-bullet comparison. This is how stage 1 was ported (research/phase14); use it for stages 2–6.

```
python3 tools/stage_compare/run_stage.py --stage 2 --out runs/stage2 \
    --retail-iso 'Ibara (Japan).iso' --pcsx2-dir ~/pcsx2/build/bin --mame mame --bl-roms ~/roms
```

Conditions in both games: player 1 Bond / straight A, invincible, shot held from the start, rank locked at
0x800000 (`--rank -1` for free rank), optional `--shot-level N`. Logging starts with the first enemy of the
chosen stage (BL stage byte = stage + 1; PS2 scene counter `$gp-28244`) and stops when it ends.

Outputs in `--out`: `bl_spawns.txt`, `bl_bullets.txt`, `bl_core.txt`, `ps2_spawns.txt`, `ps2_bullets.txt`,
`ps2_core.txt`, `ps2.p2s` (savestate; contains game data, keep local), `compare_spawns.txt`,
`compare_bullets.txt`. Formats are documented in `bl_stage_log.lua` and `ps2/hooks/spawnlog.c`.

Reading the results (lessons from stage 1):
* Spawn **subtypes** are also enemy state counters; differences there are usually logging-time artefacts.
* Compare HP and spawn counts per type first, then bullet counts, speeds and types per 500-frame bin.
* Bosses choose some attacks at random (stage 1: spiral turrets, sweep direction): compare attack *structure*,
  not exact counts. `--noshot` (BL side only for now) shows the untouched boss timeline.
* Fewer BL bullets in shooting runs can simply mean enemies died sooner; check with untouched enemies.

Pieces: `bl_stage_log.lua` (MAME autoboot script, usable alone with `OUTDIR=`), `run_stage.py` (builds a logger
ISO from the BLACK LABEL hook build with `--define BL_SPAWN_LOG BL_LOG_STAGE=… BL_SPAWN_RANK=…`, drives PCSX2 on
Xvfb with xdotool, saves state with F1 and decodes the logs from EE RAM 0x01F20000 / 0x01F35000 / 0x01F60000).
PCSX2 must already be configured (BIOS, keyboard pad: Return Start, Up, x Circle, z Cross; F1 save state).

## Long captures and repeat boss measurements

The PS2 rolling logs retain the latest 2,600 enemy spawns, 7,000 bullet spawns, and 8,000 boss samples
(16,000 for the alternate core-flags logger). Their EE bases are 0x01F20000, 0x01F35000, and 0x01F60000.
Each exported PS2 row appends the native stage byte (2 = stage 1) and stage tick. The leading columns
are unchanged. The extractor still accepts the older fixed logs, including bullets at 0x01F40000.
Use the separate logger build without the Noir ship-select artwork, which uses this area in the production ISO.

See ps2_log_coverage.json for the retained frame bounds and overwritten record count. A wrapped spawn log
requires a unique event that survives on both sides, supplied with --anchor-type. Wrapped spawn/bullet
reports compare shared coverage and drop the potentially incomplete oldest frame or bullet bin. If a
capture misses the intended anchor or phase, shorten the capture or take intermediate saves. For full-stage
enemy and bullet totals, the BL_COUNTS test build records separate totals. Only save local copies of captures.

Repeat boss trials in separate output directories. Use shot level 2 and rank 0x800000 for the damage audit.

    python3 tools/stage_compare/boss_samples.py --subtype 0 runs/s2-run1 runs/s2-run2 runs/s2-run3

The report gives observed HP and frame spans for one core subtype. Use subtype 2 for the stage-6 rose core.
Zero HP may go unsampled if a core is removed immediately. Confirm that case against phase transitions,
or with a hit trace. An escape, an incomplete capture, or a core whose real HP lives elsewhere need
separate inspection before counting the run as a kill.
