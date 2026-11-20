# M02 · Interactive ELF probe

The sixth Mode Select entry launches an original PS2 program that displays a two-choice menu. **Check controller input** counts fresh Circle presses. **Return to Ibara** closes the controller port and reloads the retail executable. The probe waits for controller buttons to be released before accepting input from a new connection.

## Build and run

Install the PS2DEV toolchain and set `PS2DEV` and `PS2SDK` to its directories. Put the EE toolchain `bin` and PS2SDK `bin` on `PATH`. The tested toolchain was PS2DEV v2.0.0. [PS2DEV releases](https://github.com/ps2dev/ps2dev/releases/tag/v2.0.0)

From the repository root, with Python asset dependencies installed, run the following against the original Japanese retail ISO.

```sh
mkdir -p outputs/interactive
make -C outputs/interactive -f "$PWD/research/phase04/interactive_probe/Makefile"
python3 research/phase04/build_menu_probe.py 'Ibara (Japan).iso' \
  --probe-elf outputs/interactive/interactive-probe.elf \
  --output 'outputs/Ibara Interactive Probe.iso'
```

The builder checks the supplied ELF32 MIPS program headers and the original disc extent before creating a separate ISO. Omitting `--probe-elf` selects the timed [M01 probe](M01_MENU_ELF_PROBE.md).

1. In PCSX2, use a disposable memory card in slot 1 and turn Auto Save off in **Option → Load/Save**.
2. Save from Ibara's **Load/Save** menu, then take a copy or hash of the test card.
3. Select **ELF PROBE** in Mode Select. Hold Circle through launch and confirm that the new screen waits for release. After releasing Circle, press it once on **Check controller input** and confirm that the count increments once.
4. Select **Return to Ibara** with the D-pad, press Circle, and re-enter Mode Select from the title. Repeat the handoff with the same card.
5. Compare the card to its saved copy, then load from **Option → Load/Save** and verify normal operation.

## PCSX2 results

PCSX2 2.8.2 on Linux used Japanese BIOS v01.00 and Mesa OpenGL. The retail frontend ran with CRC `F6BD9C51`. The interactive ELF ran at `0x00100F78` with CRC `42C07179` and returned to the retail ELF entry at `0x00100008` on each of three cycles.

- Two separate Circle presses incremented **Input checks** to `2`. Both D-pad directions were used to select **Return to Ibara**. The launch button held across the last handoff displayed **Release buttons to begin** and left the input count at `0`.
- Ibara created a save on the disposable card before the final two cycles. Both cycles preserved the entire card byte for byte. Ibara reported completion of both the slot 1 auto-load at startup and the manual load in Options.
- After the final return, Arcade, Arrange, Gallery, and Option opened their original screens, and Exit returned to the title. The card still matched its saved copy after this pass.
- The default timed-probe build matched the previously tested M01 ISO byte for byte. The interactive build used the same verified retail source ISO and the generated PS2DEV ELF.
