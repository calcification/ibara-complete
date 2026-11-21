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
