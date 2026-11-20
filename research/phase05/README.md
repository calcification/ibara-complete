# Ibara Complete — Phase 5: Arcade Kuro memory substrate

Independent research prototype; **does not depend on Phase 3 (boot probe) or Phase 4 (menu integration)**. No PS2/PCSX2 hardware execution claimed.

## What this actually delivers

- `src/cv1k_memory.c/.h`: original C implementation of a zero-on-demand, 64×64-tiled memory backing store for the CV1000's **8192×4096** 16-bit VRAM address space. The tile pool is explicitly bounded; exhausted memory causes an error rather than silently overwriting data. Includes pixel reads/writes, fills, and overlapping rectangle copies.
- Same C code provides a **2,112-byte NAND-page LRU cache**. NAND backend is a caller-supplied `fetch(page)` callback so a future PS2 backend can read from disc; no ZIP or filesystem dependencies in this core.
- `src/check_kuro_roms.py`: offline validator for a user-supplied arcade Black Label archive using chip sizes and CRC32 fingerprints in `ibara360`'s `romload.c`.
- `src/analyze_vram_trace.py`: program to measure a hypothetical graphics write trace's peak tile residency (format below). Includes read/write tile footprint and per-frame statistics. This is a **tool for future real traces**, not data collected from Ibara Kuro.
- `src/memory_budget.py`: transparent, editable memory allocation assumptions, showing unallocated headroom; not a claim of performance.
- `results/cv1k_memory_mips3.o`: successfully cross-compiled **MIPS-III o32 relocatable object**, **not** a bootable PS2 ELF nor an EE executable linked against PS2SDK.
- Host-side native tests with AddressSanitizer/UndefinedBehaviorSanitizer.

## Verified source-level hardware requirements

| Source | Requirement |
|---|---|
| `ibara360/runtime/recomp.h` | 8 MiB (`RAM_SIZE = 0x800000`) CV1000 work RAM |
| `ibara360/runtime/cv1k.h` and `runtime/blitter.c` | 8192 × 4096 × 16-bit CV1000 VRAM = **64 MiB** dense allocation |
| `ibara360/host/xsdk/ibara360/source/romload.c` | Four ROM chips: U4 2 MiB, U2 132 MiB (NAND with spare bytes), U23 4 MiB, U24 4 MiB — **142 MiB combined** |
| PS2 EE main memory | 32 MiB; the intact Xbox 360 architecture cannot fit directly |

See: https://github.com/PaulAtreides67/ibara360 (particularly the linked source paths). This repository's license was not verified; no source code from it is bundled here.

## Run tests

From the package directory, on Linux/macOS:

```bash
cc -std=c11 -O2 -Wall -Wextra -Werror src/cv1k_memory.c tests/test_memory.c -o tests/test_memory
./tests/test_memory
python3 tests/test_tools.py
python3 src/analyze_vram_trace.py tests/sample_trace.csv --pool-mib 8
python3 src/memory_budget.py --vram-mib 8
```

On Windows, use a C compiler such as Visual Studio or MinGW for `tests/test_memory.c`, and `py -3` instead of `python3` for Python scripts.

To **cross-compile just the memory core** with a suitable LLVM Clang target (not PS2SDK linking):

```bash
clang --target=mipsel-none-elf -march=mips3 -mabi=o32 \
  -ffreestanding -DIC_FREESTANDING -fno-builtin -O2 \
  -c src/cv1k_memory.c -o cv1k_memory_mips3.o
```

## Trace format (NOT real gameplay data yet)

`frame,op,x,y,width,height` CSV; `op=W` for destination/write or `R` for read; all coordinates are 0-based CV1000 VRAM pixels. Rows must be ordered by frame. For accurate **tile coverage**, capture draws, fills, and uploads including clips and wrap behavior. Every written tile is assumed resident for the rest of the capture; no eviction, compression or tile reclamation is modeled. See `tests/sample_trace.csv` for **synthetic** data. Future work is to instrument `ibara360`'s CV1000 blitter (with appropriate upstream permission) and run a sustained gameplay trace from original Kuro ROMs.

## Offline Kuro ROM verification

```bash
python3 src/check_kuro_roms.py /path/to/your/ibarablk.zip --verify-payload
```

The checker compares ZIP member length and CRC, regardless of member name. It never extracts, saves, or includes ROM bytes; source data must be independently and lawfully obtained. It cannot turn the **PS2 ISO alone** into a faithful arcade-Kuro program: those ROMs are different data. This checker has only been unit-tested with missing ROMs; it has not been verified against a real arcade archive.

## Why not drop this directly into ibara360?

The source runtime directly indexes `cv1k_vram` as a flat 64 MiB pointer. Our sparse API does not support those direct accesses. All blitter draw/upload and screen reads would require a rewritten backend, and some original arcade operations use custom blending/transparent pixels that are **not** implemented here. This is an engineering feasibility component **not a complete renderer**. Also, a NAND page cache is useful only once its DVD I/O and timing have been tested; reading 132 MiB of graphics on demand may cause unacceptable stalls.

The likely production strategy remains: preserve the retail PS2 Arcade and Arrange engines, load a Kuro-specific EE executable from the game disc, and either adapt Kuro's recompiled logic to PS2-native rendering **or** reproduce Kuro's gameplay differences within the existing PS2 engine if feasible. Neither path is proven yet.

## What a later real-world test must establish

1. Game-only translated function/code size and memory use after PS2 compilation.
2. Maximum unique CV1000 tiles written over boot, menus, and full gameplay (our 8 MiB tile pool might be too small).
3. NAND access locality and worst frame I/O; disc access is much slower than RAM.
4. PS2 GS implementation of sprite layering and blending, slowdown/timing, SPU2 sound and controller input.
5. Correctness against genuine arcade Ibara Kuro behavior; never infer this from synthetic tests.

**No retail ISO or arcade ROM is included or changed by this package.**
