# Ibara Complete — Phase 2: Verified retail ISO and resource mapping

**Investigation date:** November 19–20, 2026  
**Input:** user-supplied `Ibara (Japan).7z` containing exactly one ISO, `Ibara (Japan).iso`  
**Method:** archive extraction, ISO9660 directory inspection, streaming file-CRC validation, binary resource-table parsing, texture-header inspection, full unused-space scan; all read-only  
**Scope:** Japanese PS2 *Ibara*, boot executable `SLPM_663.01`  
**Status:** disc structure and asset indexes verified; game-mode dispatch and a working Kuro port remain unimplemented.

## 1. Disc identity

| Field | Measured value |
| --- | --- |
| Extracted ISO size | 3,932,848,128 bytes (3.662 GiB) |
| ISO SHA-256 | `6e58b52aa5c03d45e413e8473be52a39205095e34a1bd58dae6bd852eb4fb1db` |
| Boot path | `cdrom0:\SLPM_663.01;1` (`SYSTEM.CNF`, `VER = 1.02`, `VMODE = NTSC`) |
| Boot ELF LBA | 1,919,173 |
| Boot ELF SHA-256 | `263d3079dee66af82815219351553075340a4d9f42aceaa7bb8ef2bfb812ffac` |
| Match to previously analyzed ELF | **Exact, SHA-256 match** |
| Expected original 240p patch words | **21/21 match** from `Ibara_patch_list(4).txt` |

**Independent cross-check:** `ibara360`'s published `tools/ps2extract/ps2extract.c` accepts exactly these four retail-file sizes and CRC32s. All four match this user's ISO.

| Retail file | LBA | Size (bytes) | CRC32 |
| --- | ---: | ---: | --- |
| `SLPM_663.01` | 1,919,173 | 2,329,648 | `F9085060` |
| `IBARAR.PDM` | 1,801,312 | 241,377,288 | `F0A452FE` |
| `IBARAR.TBL` | 1,920,311 | 18,100 | `A286422C` |
| `ALLIMAGE.DAT` | 1,800,552 | 1,555,136 | `C09F7BED` |

Other files: `SYSTEM.CNF`; `IOPRP271.IMG`; ten `IOP/*.IRX` modules; `DAMMY1G.DAT` (1,024,000,000 bytes). The script in this package derives all file placements from the ISO9660 directory; no fixed file LBAs are necessary for the audit.

## 2. Decoded IBARAR.TBL → IBARAR.PDM index

The retail resource table is not an opaque archive anymore. Its 18,100 bytes contain **1,130** indexed PDM records:

- Header signature `54 42 4C 04` (`TBL\x04`), 20-byte header.
- Word at offset `0x08`: `0x046A11BC`, combining `0x046A` = **1,130 entries** and `0x11BC` = beginning of record area.
- At offset `0x14`: **1,130** little-endian pointers (four bytes each) to 8-byte records.
- At offset `0x11BC`: **1,130** eight-byte records, each containing a pointer to the corresponding offset-table cell and the unpadded resource length.
- At offset `0x350C`: **1,130** little-endian PDM-relative resource byte offsets.
- Each PDM offset is aligned to 2,048 bytes; each subsequent resource begins at the preceding resource's size rounded up to 2,048 bytes. **All 1,129 transitions passed validation.**
- The final record ends 8 bytes before the PDM file's nominal end. The meaning of those final bytes is not established.

The archive contains:

| PDM signature | Record count | Meaning |
| --- | ---: | --- |
| `TIM2` | **1,113** | PS2 textures, independently recognized as TIM2 |
| `BG00` | **16** | Music streams; confirmed as soundtrack streams in the `ibara360` extraction source |
| `SE00` | **1** | Sound-effect bank; confirmed by the `ibara360` extraction source |

**Important:** the `BG00` tag is **not** evidence of sixteen background images. The available external code identifies those entries as soundtrack streams.

A full metadata-only index, `Ibara_Complete_Resource_Catalog.csv`, supplies the resource ID, PDM-relative byte offset, stored length, absolute ISO byte offset, signature, and TIM2 dimensions and encoding. No image, sound, or game executable bytes are included in this package.

## 3. Frontend graphics verified in this ISO

The menu background and title art can be reconstructed from the existing image tiles. We cross-referenced `ibara360/tools/ps2extract/mkrecipe.py` against the **actual** PDM entries:

| Page IDs | PDM relative offsets | Usage |
| --- | --- | --- |
| 950–954 | `0x2D73000`, `0x2D83800`, `0x2D94000`, `0x2DA4800`, `0x2DB5000` | Six cut regions from five 256×256 TIM2 pages combine to form a 640×448 mode-select background |
| 1016–1017 | `0x45D4000`, `0x4636800` | Two 448×448 TIM2 pages combine to form the 640×448 title background |
| 1018–1019 | `0x4699000`, `0x46FB800` | Additional 448×448 pages, used by the reference project for a taller title composite |
| 945–946 and nearby | `0x2D20800`, `0x2D31000` | UI sprite pages; the reference extraction calls out selection plates and signs |

Both 640×448 backgrounds were decoded from this user's ISO for private visual inspection. **The mode background contains character artwork, while menu labels and selection graphics are overlays**; therefore adding a new entry should not require repainting the existing character artwork. Where the control flow and overlay drawing occur is still under investigation.

## 4. Strong evidence for an in-place secondary-ELF layout

- `DAMMY1G.DAT`: starts at LBA 286 and occupies exactly 500,000 sectors.
- The next actual allocated file begins at LBA **1,800,286**.
- Therefore the gap runs from LBA **500,286** through **1,800,285**, inclusive: **1,300,000 sectors = 2,662,400,000 bytes**.
- **The entire gap was scanned, and all 2,662,400,000 bytes were zero.** This is not just a sample.
- The ISO9660 root directory begins at **LBA 261** and has a logical length of **570 bytes**; the remainder of that 2,048-byte physical sector—**1,478 bytes**—is all zero.
- A single ISO9660 Primary Volume Descriptor is present at LBA 16 (terminator at 17); no supplemental ISO9660 volume descriptor was found.

**Potential approach (not yet tested):** allocate `KURO.ELF;1` and any needed new data in a small reserved subset of the zero gap, add a properly encoded root-directory entry and adjust the root-directory length metadata, then modify the retail frontend to load `KURO.ELF;1` when Black Label is selected. This could preserve original file extents and the existing 240p patcher's ELF mapping.

**Why this still needs care:** changes to the logical root-directory length require consistent little- and big-endian ISO9660 metadata updates in the PVD and self-referential root records. Correct file permissions/system-use fields, disc loading behavior, and PCSX2/real-console compatibility must be verified. Empty space on disc does **not** solve the PS2's 32 MB RAM, 4 MB GS VRAM, performance, or copyright/ROM-data constraints.

The root-directory metadata has **not** been modified. No new executable has been inserted. The original ISO remains unchanged.

## 5. Recommended implementation sequence

1. **Freeze original baseline.** Validate the ISO SHA-256 and four file CRC32s. Rebuild the first game's verified native 240p modifications on a copy only, never patch the source ISO in place.
2. **Prove harmless secondary-file injection.** In a disposable ISO copy, add a tiny, clearly identifiable homebrew test file to the zero gap and a matching ISO9660 directory record. Verify the old file LBAs/CRC32s did not move, `SYSTEM.CNF` still boots the retail executable, and PCSX2 can see the new file via normal disc file I/O. This is a filesystem smoke test, not yet Kuro.
3. **Trace the top-level Arcade/Arrange launcher.** Prior work identifies Arcade internal accept dispatch at EE `0x001CAA88`, Arrange internal accept dispatch at EE `0x001CCBF4`, and a possible mode flag at `-0x6864($gp)`. These are not verified top-level hooks. Capture **actual runtime traces** in PCSX2, including `$gp`, and discriminate top-level selection from internal menu states.
4. **Add a third menu entry non-destructively.** Prefer reusing original UI sprite artwork, expanding the menu selection loop, and dispatching Black Label to a new test ELF. Restore Original/Arrange behavior and saves unchanged. This phase can be developed using a tiny homebrew ELF; do not begin by copying a full arcade port.
5. **Benchmark Kuro logic separately.** The public `ibara360` code demonstrates an external recompilation/runtime architecture, but its PowerPC-to-EE port, resource needs, original game ROM dependencies, and compatibility are unresolved. Investigate license/permissions before reuse. Headless PS2 measurements must precede full rendering/audio work.
6. **Integrate accurate Kuro output.** Only after the runtime is feasible: CV1000 display behavior → GS graphics → 240p timing → SPU2 audio → mode exit/reentry, save isolation, stage loading, real hardware testing.

## 6. What the ISO does and doesn't establish

**Established by direct inspection:** exact executable match, exact retail resource CRCs, complete PDM entry index, existing UI background pages, root directory sizing, and the completely zero 2.66 GB gap.

**Not yet established:** the actual high-level Arcade/Arrange menu function, any safe patch hook, allocation and rendering of a third menu item, a working new ELF handoff, original Kuro data being on the PS2 disc, Kuro performance on PS2, or that the retail PS2 Arrange engine can fully substitute for arcade Black Label behavior.

## 7. Sources and reproducibility

- Original ISO and extracted ELF supplied by the user.
- Previously verified 240p patch list and Phase 1 technical report supplied in the earlier project context.
- `ibara360` source: <https://github.com/PaulAtreides67/ibara360/blob/main/tools/ps2extract/ps2extract.c>
- `ibara360` mode/title art recipe: <https://github.com/PaulAtreides67/ibara360/blob/main/tools/ps2extract/mkrecipe.py>

Run the included standard-library-only tool on Windows, macOS, or Linux after extracting your ISO:

```bash
python ibara_complete_phase2_audit.py "Ibara (Japan).iso" --json my_audit.json --csv my_catalog.csv --scan-gap
```

The entire archive input was read-only throughout the investigation. Game binaries, soundtrack, textures, and the full original ISO are deliberately excluded from the distributable research ZIP.
