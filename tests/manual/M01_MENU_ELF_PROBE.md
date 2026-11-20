# M01 · Launch and return from the Mode Select ELF probe

For a controller-driven return and a memory-card check, see [M02](M02_INTERACTIVE_ELF_PROBE.md).

**Result:** PASS in PCSX2 2.8.2 on Linux with Japanese BIOS v01.00 and OpenGL (Mesa llvmpipe). The input was the exact Japanese `SLPM-66301` retail ISO, CRC `420C7FAB`. The probe image used CRC `F6BD9C51` for the modified retail executable and `04D616D3` for the homebrew executable. Cheats and patches were disabled.

1. From the repository root, install the optional asset dependencies with `python3 -m pip install -r requirements-assets.txt`.
2. Run `python3 research/phase04/build_menu_probe.py 'Ibara (Japan).iso' --output 'Ibara ELF Probe.iso'`. The builder verifies the original disc and expected instructions, skips all-zero chunks when copying, and refuses to overwrite an existing output.
3. Boot the new image in PCSX2. Press Start at the title screen, then press Up from Arcade to highlight the sixth row, **ELF PROBE**. The five retail choices retain their indices and order.
4. Press Circle. The probe sets the GS background color, waits briefly, and loads the retail executable again. Video can be blank during the handoff. The PCSX2 log should report `KURO.ELF;1` executing at `0x00100000`, followed by `SLPM_663.01;1` executing at `0x00100008`.
5. Enter Mode Select again. Check Arcade, Arrange, Gallery, Option, and Exit. Arcade and Arrange open their original submenus, Gallery and Option open their respective screens, and Exit returns to the title.

The verified run produced both execution events after selecting the sixth row and reached Mode Select again through the retail title screen. All five original frontend checks passed in the same modified image. The return is a cold reload of the retail executable. This test covers frontend navigation and the two disc boot transitions. Gameplay, save persistence, physical PS2, and the 240p patch are outside the test coverage.

Build verification compared the regenerated ISO to the runtime-tested image byte for byte. A source comparison confined edits to the original boot ELF ranges, the label rectangle in resource 945, and the ISO9660 metadata and sector used for the added ELF. The test uses a locally generated homebrew payload. The arcade archive is unnecessary for the build and the run.
