**Current recommended method:** small PCSX2 `.pnach` experiments on the original ISO/CHD. The [P00 baseline and B04 menu trace](../tests/manual/RESULTS_P00_B04.md) passed in PCSX2 2.8.2. [P01 and P02](../tests/manual/RESULTS_P01_P02.md) both produced 224 active progressive lines. P03–P06 await emulator runs. See [PCSX2_FIRST](PCSX2_FIRST.md) for the procedures.

# Verified status and roadblocks (November 2026)

| Area | Present evidence | Unverified / missing |
|---|---|---|
| Original ISO | ISO9660 structure, 1,130 resource entries, original checksums | None for this exact reference image |
| Boot test | Separate ISO file injection verified offline; menu-triggered ELF runs in PCSX2 | Direct-boot B01 procedure and console safety |
| Retail-boot test | Original `SLPM_663.01` location/bytes preserved in injected ISO | Actual retail boot/navigation in modified ISO |
| Menu | Five retail branches traced and [a sixth test row launches an interactive homebrew ELF and returns to the retail title in PCSX2](../tests/manual/M02_INTERACTIVE_ELF_PROBE.md) | Hardware validation and integration with a compatible gameplay executable |
| New art | Phase 4 button indexes altered only within 112x48 alpha-clear slot | Correct hardware texture behavior; new button draw call |
| Kuro | Public Xbox 360/PC SH-3 recompilation source used as reference; 64 MiB VRAM model demands redesign for PS2 | Ported Kuro game code, data streaming, native graphics, timing, authentic sound and gameplay |
| Gameplay analysis | Native EE score/rank/pickup/cancellation/rose-merge instruction anchors | Dynamic branch conditions, complete bomb/Hadou IDs, parity against Kuro |
| 240p | Separate `cave-ps2-240p` release; progressive output confirmed for both PNACH profiles in PCSX2 | Physical CRT signal and shimmer comparison, integrated gameplay build |

**Pending:** a playable Black Label port, arcade-accurate mechanics and timing, and hardware validation.

**Evidence caveat:** previous phase scripts independently fingerprint 60–82 sampled opcode words and/or specific call edges. This prevents unintentional revision drift; it does NOT prove all function semantics, timing, graphical correctness, or untouched business logic. In particular, earlier Phase 6/7 player base addresses were corrected in Phase 8 and a Phase 9 Python scorer restriction was corrected by Phase 10.

**Why the native-engine approach remains exploratory:** Kuro's SH-3 and PS2's EE MIPS are different CPUs, their player-record strides differ, and real Kuro has gameplay logic and assets not established to be on the retail PS2 disc. The Phase 5 tile cache is a capacity prototype, not a port.
