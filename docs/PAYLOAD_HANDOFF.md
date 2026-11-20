# PS2 launcher payload handoff

The sixth entry in Ibara's Mode Select launches a standalone PS2 Emotion Engine executable from the disc. The [interactive probe](../tests/manual/M02_INTERACTIVE_ELF_PROBE.md) is a working example of startup, controller setup, and return.

## Executable and return path

- Supply a little-endian MIPS ELF32 `ET_EXEC` for PS2 EE. Its entry point must be in a file-backed executable load segment and its load segments must fit in EE RAM. The builder checks these structural requirements before generating a disc image.
- The launcher installs the ELF at `cdrom0:\KURO.ELF;1` and calls `LoadExecPS2` with zero arguments. The program starts as a separate executable and initializes its own video, controller, and other I/O as needed.
- To return, close resources such as controller ports and reload `cdrom0:\SLPM_663.01;1` with `LoadExecPS2`. This starts Ibara again through its title screen. A payload that saves data needs its own save handling.
- Add companion files with one `--disc-file NAME.EXT=PATH` per file. Use up to eight ASCII letters, digits, or underscores for the name and up to three for an optional extension. The builder uppercases names and rejects duplicate names, including existing disc entries and `KURO.ELF`. Open a packaged file from the payload using a path such as `cdrom0:\PAYLOAD.DAT;1`.

## Build and verify a test image

Use the original Japanese `SLPM-66301` ISO and install the Python dependencies in `requirements-assets.txt`.

```sh
mkdir -p outputs
python3 research/phase04/build_menu_probe.py 'Ibara (Japan).iso' \
  --payload-elf path/to/payload.elf \
  --disc-file PAYLOAD.DAT=path/to/payload.dat \
  --label 'EXTRA MODE' \
  --video-profile 240p_core \
  --output 'outputs/Ibara launcher test.iso'
```

Omit `--disc-file` for a self-contained executable such as the interactive probe. Companion contents are copied as supplied. The ELF and companion files share the free sectors and root directory space reserved by the builder. The [companion file test](../tests/manual/M04_COMPANION_FILES.md) verified a multi-sector binary and an empty file from inside a standalone PS2 ELF.

The `retail` profile is the default. `240p_core` and `240p_halfpixel` apply the P01 and P02 edits to the retail executable at build time. `240p_cave_beta` adds the three field-state writes from the [published Cave 240p beta](https://github.com/calcification/cave-ps2-240p/blob/v0.1.0-beta.1/docs/PATCH_SPEC.md#ibara) for hardware comparison. Each payload controls its own output mode. Boot the image with PCSX2 cheats disabled and use a separate test memory card. The builder prints the executable CRC and SHA-256. Use the SHA-256 or build option to distinguish `240p_core` and `240p_halfpixel` since their retail executables share an XOR CRC.

In PCSX2, check that the sixth entry displays the supplied label, the payload starts, and its return action reloads the retail title. Check Arcade, Arrange, Gallery, Option, and Exit after returning. For a progressive profile, confirm the mode after both the initial boot and the retail reload. Use the [P01/P02 register checks](../tests/manual/RESULTS_P01_P02.md) to identify scan mode and active height.

Both progressive profiles passed the [launcher round-trip test](../tests/manual/M03_LAUNCHER_VIDEO.md) with the interactive controller probe.
