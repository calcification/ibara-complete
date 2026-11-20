# Verified status and roadblocks (November 2026)

| Area | Present evidence | Unverified / missing |
|---|---|---|
| Original ISO | ISO9660 structure, 1,130 resource entries, original checksums | None for this exact reference image |
| Boot test | Separate ISO file injection structurally verified; SHA/CRC/byte-diff compared | PCSX2 secondary ELF execution; on-console safety |
| Retail-boot test | Original `SLPM_663.01` location/bytes preserved in injected ISO | Actual retail boot/navigation in modified ISO |
| Menu | 5-option selector, MIPS branching and texture index/space mapped | A 6th rendered/working option and PS2 ELF handoff |
| New art | Phase 4 button indexes altered only within 112x48 alpha-clear slot | Correct hardware texture behavior; new button draw call |
| Kuro | Public Xbox 360/PC SH-3 recompilation source used as reference; 64 MiB VRAM model demands redesign for PS2 | Ported Kuro game code, data streaming, native graphics, timing, authentic sound and gameplay |
| Gameplay analysis | Native EE score/rank/pickup/cancellation/rose-merge instruction anchors | Dynamic branch conditions, complete bomb/Hadou IDs, parity against Kuro |
| 240p | Separate `cave-ps2-240p` release | Any integrated, tested 240p + extra-ELF + Kuro build |

**Do not claim:** a playable Black Label port, an inserted third menu entry, tested extra ELF boot, arcade-accurate mechanics, authentic Kuro assets on the disc, or the PS2 reaching full Kuro framerate.

**Evidence caveat:** previous phase scripts independently fingerprint 60–82 sampled opcode words and/or specific call edges. This prevents unintentional revision drift; it does NOT prove all function semantics, timing, graphical correctness, or untouched business logic. In particular, earlier Phase 6/7 player base addresses were corrected in Phase 8 and a Phase 9 Python scorer restriction was corrected by Phase 10.

**Why the native-engine approach remains exploratory:** Kuro's SH-3 and PS2's EE MIPS are different CPUs, their player-record strides differ, and real Kuro has gameplay logic and assets not established to be on the retail PS2 disc. The Phase 5 tile cache is a capacity prototype, not a port.
