# M04 · Companion files on the launcher disc

PCSX2 2.8.2 on Linux with Japanese BIOS v01.00 booted the original frontend with `240p_core` and cheats disabled. The sixth option, **FILE TEST**, launched the homebrew probe. The probe read all 5,000 bytes from `cdrom0:\PROBE.DAT;1`, opened the zero-byte `cdrom0:\EMPTY;1`, and reloaded the retail title after displaying **BOTH COMPANIONS VERIFIED** for about six seconds.

The combined run used integration baseline `9bf94de` with the launcher changes applied locally. Before launch and after return, both captures matched all 18 expected retail EE words for `240p_core` and showed `SMODE2.INT = 0` with 224 active lines on read circuit 2.

Use PS2DEV and PS2SDK v2.0.0, the original Japanese `SLPM-66301` ISO, and the Python packages from `requirements-assets.txt`. From the repository root, with the PS2DEV environment set up, run the following commands.

```sh
mkdir -p outputs/companion-test
make -C outputs/companion-test -f "$PWD/research/phase04/companion_probe/Makefile"
python3 - <<'PY'
from pathlib import Path

folder = Path("outputs/companion-test")
(folder / "pattern=bytes.dat").write_bytes(bytes((17 * i + 3) % 256 for i in range(5000)))
(folder / "empty.dat").write_bytes(b"")
PY
python3 research/phase04/build_menu_probe.py 'Ibara (Japan).iso' \
  --payload-elf outputs/companion-test/companion-probe.elf \
  --disc-file 'probe.dat=outputs/companion-test/pattern=bytes.dat' \
  --disc-file empty=outputs/companion-test/empty.dat \
  --label 'FILE TEST' --video-profile 240p_core \
  --output outputs/companion-test/companion.iso
```

Boot the resulting image in PCSX2, open Mode Select, and choose **FILE TEST**. Check for `PROBE.DAT: PASS (5000 bytes)` and `EMPTY: PASS (0 bytes)`. On success, wait for the title to reload and check the scan mode again. The probe stays on its results screen if a file check fails.
