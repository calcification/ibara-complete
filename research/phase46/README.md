# Phase 46: memory card files for replays and settings (Claude, 28 November 2026)

Goal: write our own files (replays, later Noir / Arrange settings and Noir scores) to the memory card safely,
without ever touching the game's save. Code: `ps2/hooks/mcfile.c`. A test-only driver is `ps2/hooks/mctest.c`
(`MC_TEST`), and the card-image reader is `tools/mc_read.py`. Not in the release build yet.

## The game's memory card code

* Save folder `BISLPM-66301` with `BISLPM-66301` (7,300 bytes), `icon.sys` (964) and `ibara.ico` (33,704). The
  descriptor is at 0x001D48B0, the icon.sys template at 0x001D49B0 (title "イバラ" at +0xC0), and the icon itself is
  embedded in the executable at 0x001D4DB0.
* A save manager (state block 0x00339D30; job state 0x00339D50, 3 while a job runs) drives a C++ card class
  (0x001C0xxx–0x001C2xxx) that polls from its own thread.
* Underneath is Sony's libmc (XMCSERV client), statically linked. Each function sends one RPC through
  `sceSifCallRpc` (0x0014BFF8); the command number identifies it:

| Function | Address | RPC |
|---|---|---|
| sceMcGetInfo(port, slot, &type, &free, &format) | 0x00155558 | 1 |
| sceMcOpen(port, slot, name, mode) | 0x00154DD0 | 2 |
| sceMcMkdir(port, slot, name) (open with 0x40) | 0x00154EF8 | 2 |
| sceMcClose(fd) | 0x00154F30 | 3 |
| sceMcSeek(fd, offset, origin) | 0x00154FE8 | 4 |
| sceMcRead(fd, buf, size) | 0x00155150 | 5 |
| sceMcWrite(fd, buf, size) | 0x00155268 | 6 |
| sceMcFlush(fd) | 0x00155C40 | 10 |
| sceMcChdir | 0x00155918 | 12 |
| sceMcGetDir(port, slot, name, mode, max, table) | 0x00155748 | 13 |
| sceMcSetFileInfo(port, slot, name, info, flags) | 0x00155CF8 | 14 |
| sceMcRename(port, slot, path, new_name) (set file info, flag 0x10) | 0x00155EC0 | 14 |
| sceMcDelete(port, slot, path) | 0x00155B28 | 15 |
| sceMcFormat / sceMcUnformat | 0x00155A58 / 0x00156018 | 16 / 17 |
| sceMcGetEntSpace | 0x001560E8 | 18 |
| sceMcSync(mode, &cmd, &result) (mode 1 polls: 1 finished, 0 running, -1 idle) | 0x00155420 | — |

## mcfile.c

* A non-blocking job, advanced one card command per frame (`mc_tick`), so the game keeps drawing while it saves.
* It starts only while the game's save manager is not running a job (0x00339D50 != 3). Only one libmc command may
  be outstanding and the game's card thread polls `sceMcSync` too. Callers must run jobs only where the game does
  not start card work (our own screens).
* Folder `BISLPM-66301KURO` (memory card slot 1). On first creation it gets `icon.sys` (the game's template,
  titled "イバラ / ＫＵＲＯ　ＲＥＰＬＡＹ") and the game's `ibara.ico`, so the PS2 browser shows it properly.
* **Saving NAME:** check the card (PS2 card, formatted, enough free space for a second copy plus icons) → make the
  folder → delete a stale `NAME.TMP` → write `NAME.TMP` in 16 KB commands → close → read it back and compare
  every byte → delete the old `NAME` → rename `NAME.TMP` to `NAME`.
* **Loading NAME:** read `NAME`. If it is missing, read `NAME.TMP`, which is what a save cut between the delete and
  the rename leaves.
* The game's own files are never opened.

## Tests (PCSX2 2.8.2, card image with the game's save)

Test build: `mcfile.c` + `mctest.c` with `MC_TEST`, started from the frontend. It saves a 300,000-byte pattern as
`REPLAY1.DAT`, loads it and compares, overwrites it with a second pattern, loads and compares again, then saves a
4 KB `SETTINGS.DAT`.

* All five jobs succeeded, and both loads matched byte for byte. The whole sequence takes a few seconds in PCSX2.
* Checked from outside with `tools/mc_read.py`: the file system is consistent (FAT chains match sizes, no shared or
  lost clusters). The game's three files are byte-identical to before, `REPLAY1.DAT` holds the second pattern, and
  the folder title reads イバラ / ＫＵＲＯ　ＲＥＰＬＡＹ.
* The release ISO still boots and auto-loads its own save from a card that has our folder (the game's "auto-loaded"
  message at boot).

### Power cuts (`MC_TEST_CUT=n`: the module stops after n card commands, then PCSX2 is killed)

Commands 1–53 are the first save (folder and icons, then the file), 54–74 the load, and 75–121 the overwrite.

| Cut after | Where | Card afterwards |
|---:|---|---|
| 5 | icon.sys written, icon not | consistent; folder with icon.sys only |
| 20 | first-ever save, mid-write, file still open | `REPLAY1.DAT.TMP`'s directory size (32 KB) is ahead of its cluster chain (1 cluster): the card's write cache was never flushed. Only our temp file is affected |
| 77 | stale temp deleted | consistent; old `REPLAY1.DAT` intact (pattern 1) |
| 85 | temp part-written | consistent; old file intact, temp 0 bytes |
| 98 / 110 / 119 | temp complete / mid-verify / verified | consistent; old file intact, complete temp beside it |
| 120 | old file deleted, rename not done | consistent; only the complete temp (pattern 2) |
| 121 | done | consistent; new file |

In every case the game's three files are byte-identical. Follow-ups:
* Load after cut 120 falls back to `REPLAY1.DAT.TMP` and returns all 300,000 bytes of the new version.
* Load after cut 20 fails cleanly (opening the partial temp is refused, −3); nothing partial is returned.
* A full save sequence on the cut-20 and cut-120 cards succeeds and leaves a consistent card (the stale temp is
  deleted first).

A first-ever save cut mid-write can leave our own temp file inconsistent, as with any PS2 save cut while a file is
open. The replay format carries a length and checksum, so a damaged file is rejected rather than played.

### Card problems

| Case | Result |
|---|---|
| No memory card (slot disabled; the game's own "no card, start anyway?" → Yes) | save refused at the card check (−11), load fails (−12), the game carries on |
| Unformatted card (all 0xFF) | save refused at the card check (not formatted), load fails (−2); nothing written |
| Not enough space (a 9 MB file claimed) | refused by the space check (−1000) before anything is written; card unchanged |

## Next

* Replay file format: header (magic, version, mode, ship / bomb, stage, start state), compressed per-update
  data, length and checksum.
* Save / load screens (only where the game does no card work), then the REPLAY menu entry and playback.
* Hardware: one real card on an original PS2 before any release use.
