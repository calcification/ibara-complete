# Phase 23 — Black Label's ship-select theme on the PS2 disc

Goal: while the Noir select screen is up, play Black Label's ship-select theme as the arcade does, taken from the
user's own ROM, without growing the disc.

## Where the music lives in the arcade set

The CV1000 sound chip is a Yamaha YMZ770 (MAME device `:ymz770`). Its 8 MiB sound ROM is `u23` + `u24`
(CRCs `a436bb22`, `d11ab6b6`). MAME loads each with `ROM_LOAD16_WORD_SWAP`, so every 16-bit word is byte-swapped.

* Phrase table at 0: four bytes per phrase. Bits 4–6 of byte 0 hold the table select (`atbl`) and the low
  24 bits hold the byte offset.
* Sequence table at +0x400.
* MAME save items (`emu.item(dev.items["0/m_channels.phrase"])`) show the select screen starts sequence 0, which
  plays phrase 0 on a loop.
* Phrase 0 sits at offset 0xEA262. It is AMM (an MPEG-1 layer-2 variant) at 16 kHz mono, 48.0 s long, looped
  whole.

## Decoder

`patcher/amm_decode.py` is a standard-library Python port of MAME's `mpeg_audio` (BSD-3, Olivier Galibert;
notice kept in the file), limited to the AMM path. Compared against MAME's `-wavwrite` recording of the select
screen, cross-correlation is 0.987–0.994 per window. A full decode takes about 2.5 s.

## PS2 side

**BGM streams.** The retail game keeps its 16 BGM tracks in `IBARAR.PDM` as "BG00" entries:

* The header is "BG00", 0x40, 1, 0, 0x2800.
* VAGp headers for left and right follow at 0x40 and 0x70. Each gives the per-channel byte count and the rate
  (44,100 Hz), both big-endian, and the name `sdbgstrm.tmp`.
* Zeros fill up to 0x800. After that come 0x2800-byte ADPCM blocks, alternating left and right.
* Each channel starts with a zero frame and ends with an end frame (flag 1), then a terminator frame
  (`11 07`).

`patcher/bg00_stream.py` resamples the theme to 44.1 kHz (Lanczos-4) and encodes it as Sony ADPCM, choosing the
best of five filters per frame. It writes the same data to both channels. The retail tracks have an RMS of about
7,000, while the decoded theme reaches about 14,500, so the gain is 0.5.

**Game routines:**

* `0x001371A0(track)` starts a track. It writes the track number to `$gp-29040` (0x338B80) and calls
  `0x0010F760(0, &record, 12)`. Track 0 calls the stop routine `0x0010F8E0` instead.
* A track record is 12 bytes: archive index (s16), volume (s16), a zero word, and a loop flag (u16, 1).
* `0x0010F760` copies the record to the request block at 0x345570 and clears `$gp-29216` and `$gp-29220`. The
  per-frame update at `0x0010FBD0` then opens the entry (`0x001BD770`), and plays it once it is open, looping
  when the flag is 1.
* `0x0010F8E0` stops a playing stream (state 3 or 4). It also sets both words to −1, so the request is not
  reopened.

**Hook (`ps2/hooks/bl_select.c`).** The executable carries a 24-byte slot: the tag `BLSELECT-MUS-01`, then the
archive index (0xFFFFFFFF = none) and the volume (0x58).

* `sel_begin` starts the theme with its own record when the slot holds an index.
* `finish` (confirm or timeout) calls `0x001371A0` with the stage's current track (`$gp-29040`) if one is set,
  or 0 to stop.
* The stage scripts start their own music afterwards as in retail. In PCSX2, Stage 1 requested track 1, archive
  entry 1119, about 25 s after confirm.

**Adding the entry without growing the disc (`patcher/bl_music.py`):**

* The stream (2,439,168 bytes) goes into the zero gap below `IBARAR.PDM`, at the top of the largest empty
  stretch between file extents. Every directory is scanned, including `IOP/`.
* The PDM's directory record moves its start down to the stream, and its size grows by the same amount. Every
  retail entry keeps its sectors.
* `IBARAR.TBL` adds that amount to every offset and gains one entry, 1130 at offset 0. That is 16 bytes inside
  the table's last sector.
* `0x001AAA70`, the table lookup, has no bounds check. It takes the sector from `offset >> 11`, so every offset
  must stay positive, which is why the archive start moves rather than the stream being appended.
* The music slot gets the new index.

The builder (`scripts/build_black_label_iso.py --bl-rom`) and the patcher (`apply_kuro_patch.py --bl-rom`) both
do this when `u23`/`u24` are found, in the zip or next to `ibarablk_u2`. Their outputs are byte-identical at
3,932,848,128 bytes.

## Checked in PCSX2 (K42)

* While the selector is up, the request block holds index 1130 and IOP RAM holds blocks of our stream, with
  positions advancing over time.
* After confirm, the stream position in IOP RAM stays frozen across the next 25 s of savestates, and
  `$gp-29216`/`$gp-29220` read −1 (stopped).
* Stage 1 then starts its own track 1.
* With the selector held past 48 s, the stream wraps to its start (loop).
* The other resources load as before. Retail entry 1113 reads from sector 1,852,569 before and after.

Not checked: how it sounds on hardware (level against the stage music, loop seam).
