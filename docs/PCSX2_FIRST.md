# PCSX2-first test plan — use one small PNACH, not a new ISO

**Start here.** This supersedes the priority/order of the Phase 3/4 multi-gigabyte ISO tests. The aim is **one clean Ibara image in PCSX2, a tiny patch, and small text reports**. PCSX2 gameplay results are still **PENDING**. The project does **not** contain a working Black Label mode.

## 0. Minimal portable setup (laptop and desktop)

1. Have a legally obtained copy of the original Japanese Ibara PS2 disc image, on each machine if running locally. **The ISO is not included** in this repository. For less space, PCSX2 supports lossless **CHD** and **CSO** images, so you can convert your own original disc image once and use the compressed image directly. For `chdman`, a common conversion is `chdman createdvd -i "Ibara (Japan).iso" -o "Ibara (Japan).chd"`; verify the resulting game boots and retains CRC `420C7FAB` before deleting your local ISO. Keep the raw original if running the legacy ISO-only auditor/ISO-builder scripts.
2. Download the tiny `pnach/SLPM-66301_420C7FAB.pnach` from the repository on either device (or pull the small repo). In PCSX2 choose **Tools → Open Data Directory** and put the file in its `cheats` directory. If already present, back up your existing file first; you cannot use two different files with the same name simultaneously.
3. Boot the **unmodified** game image. Confirm game serial `SLPM-66301` and **PCSX2 game CRC `420C7FAB`** in PCSX2's Game Properties / startup log. This is PCSX2's XOR-of-ELF-words checksum, not the normal CRC32 `F9085060`.
4. In **Game Properties → Cheats**, enable cheats, then **enable only ONE `Ibara Complete` experiment at a time**. All six experimental groups are in one `.pnach` and are independently selectable in a current PCSX2. Ensure the other groups are OFF, and cold boot after changing code/video experiments. If game settings use a different config name/UI layout, use PCSX2's official [Writing Patches guide](https://pcsx2.net/docs/advanced/writing-patches/).
5. Capture a screenshot or a few lines of debug output and fill `tests/manual/RESULT_TEMPLATE.md`. On the second computer, pull the repo / fetch the same `.pnach` and continue. Do not sync BIOS files, retail ROMs, large PCSX2 savestates, or multi-gigabyte output images to GitHub.

**Alternative: guaranteed one experiment per file.** Copy `pnach/profiles/<experiment>/SLPM-66301_420C7FAB.pnach` into PCSX2's `cheats` directory, replacing the previous test file. This cannot accidentally activate a different test group. `pnach/profiles/baseline` contains no writes.

### What the PNACH can and cannot do

- **CAN:** edit EE code, EE globals, and EE data tables at runtime; exercise the 14/18-edit 240p experiments and measured rank/score/medal memory. Requires only the existing disc image.
- **CANNOT by itself:** add `/KURO.ELF;1` to ISO9660; replace the disc's `SYSTEM.CNF`; insert new `IBARAR.PDM` texture bytes before the engine loads them without identifying a safe runtime address; supply a 132 MiB arcade NAND or emulate Kuro. Keep B01–B03 ISO procedures as **optional escalation**, not the default workflow.
- **Standalone boot probe:** the self-authored 160-byte ELF at `tests/fixtures/KURO_PROBE.ELF` may be launched using PCSX2's ELF launch/override path to prove MIPS execution without rebuilding an ISO. This **isn't** a test of the game's ability to load a new file from its disc; B01 is still needed to prove that.

## Experiments

The [P00 baseline and B04 menu trace](../tests/manual/RESULTS_P00_B04.md) passed in PCSX2 2.8.2. Patch experiments P01–P06 are pending.

Use a temporary or disconnected memory card for all tests that affect score/rank. Do **not** enable the score and rank tests together with video experiments during initial isolation. Distinguish an opcode/value present in memory from evidence that gameplay responds as intended.

| Test ID | PNACH group/profile | PCSX2 action | Expected observation | Diagnostic address |
|---|---|---|---|---|
| **P00** | `profiles/baseline` (no active writes) | Start original and navigate Arcade/Arrange, Gallery/Option/Exit | Retail behavior unchanged | N/A |
| **P01** | `240p_core` | Cold boot, compare display mode and sharpness with P00 | 14-edit progressive/nearest/crop candidate; may have residual shimmer | `0x001AD250`, `0x001AF11C` |
| **P02** | `240p_halfpixel` | Cold boot, compare shimmering/centering with P01 | Same 14 edits plus four -0.5px adjustments; parity unverified | `0x001AECD4`, `0x001AED3C`, `0x001AED88`, `0x001AEDD4` |
| **P03** | `score_marker` | Start Arcade/Arrange on spare card and inspect P1 score / memory | P1 score word set to **1,000,000** on each vsync | `0x0044C600` |
| **P04** | `rank_easy` | Start a level, inspect current inverted rank word / gauge | `0x00338EB4` held at `0x00FFFFFF` (easiest) | `0x00338EB4` |
| **P05** | `rank_hard` | Separate cold boot, inspect same address / gauge | `0x00338EB4` held at `0x00000000` (hardest) | `0x00338EB4` |
| **P06** | `medal_first_10000` | Watch first level-0 medal; inspect 32-bit value at metadata reward address | First medal reward is **10,000** rather than **100**; other level rewards untouched | `0x0020B104` |

**Nuances:** P01 and P02 apply `patch=2` (boot plus every vsync), which current PCSX2 supports. P03–P05 use `patch=1` (every vsync). P06 uses `patch=2` for a static reward table. Startup timing and game writes might affect behavior. P03's displayed score may not read literally 1,000,000 at every instant; watch the memory word. P06 can be confounded by other score events; validate the table address directly before attributing a total score delta to one medal. **No game-run claim is made here.**

## Which patches are independently checked?

`python3 scripts/build_pnach.py --verify 'Ibara (Japan).iso'` recreates all PNACH profiles and checks:
- exact 2,329,648-byte retail boot ELF SHA-256;
- PCSX2 XOR CRC `420C7FAB`;
- 19 original expected words for both video variations and the first medal-reward descriptor;
- target addresses, alignment, syntax, group headers, no duplicate writes within a group.

Without an ISO or ELF (both machines need only the small repository to **generate** patches):

```
python3 scripts/build_pnach.py
python3 tests/test_pnach.py
```

Those are **offline format/source preimage checks**, not proof PCSX2 executes every group correctly. `python3 scripts/run_audits.py --selftest` still runs the Phase 5 synthetic suite. The ten-phase research audit continues to work with the clean raw ISO or ELF but is no longer the everyday patch workflow.

## PCSX2 debugging and result reporting

1. Enable advanced options via **Tools → Show Advanced Settings** if needed, then **Debug → Open Debugger**. Check EE memory at the address from the test table while a stage is running. The official [PCSX2 debugger docs](https://pcsx2.net/docs/advanced/debugger/) describe those controls.
2. Record PCSX2 version, OS (laptop/desktop), backend renderer, clean image game CRC, active PNACH group, test ID, stage/mode, screenshot or memory value, observed versus expected, and whether the game saved a score. Use `tests/manual/RESULT_TEMPLATE.md`.
3. If the game CRC differs from `420C7FAB`, **stop**: the image may be patched, a different revision, or an ELF override. Do not rename the patch to a different CRC without re-verifying its expected original code/data words.
4. Disable all `Ibara Complete` groups and restart to restore unmodified behavior. Do not rely on the toggling alone to undo earlier in-memory writes; reboot clears those.

## Optional / postponed ISO-only and filesystem investigations

- **B01**: the legacy generated test ISO's direct boot of `/KURO.ELF;1` still requires modifying the ISO directory and boot configuration. No PNACH can faithfully replace that test.
- **B02**: boot Ibara from an ISO containing an unused extra ELF and verify no normal functionality is disturbed.
- **B03**: inject a *dormant* menu texture into the PDM; can't directly translate to a reliable PNACH without first locating the asset's RAM/GS upload site.
- **B04**: selector debugging can be performed with the original ISO/CHD and no PNACH at all; see `tests/manual/B04_MENU_DEBUGGER.md`.
- **H01**: do not transfer these runtime memory patches blindly to real PS2, and don't use the boot-probe ISO on hardware until the corresponding PCSX2 tests pass.

All legacy ISO tests remain available under `scripts/build_test_images.py`, but are secondary because they create separate ~3.66 GiB files.

## Syncing between machines without extra storage

The source-only ZIP is under a few hundred KB; the PNACH is only a few KB. Commit text logs, screenshots when useful, and revised patch files to GitHub. Store **one** compressed original Ibara image locally per PCSX2 installation, rather than downloading or building a new image for each test. Preserve distinct PCSX2 game settings/BIOS locally; do not place commercial game images in GitHub.

**Source of PNACH format and timing:** [PCSX2 Writing Patches](https://pcsx2.net/docs/advanced/writing-patches/), including `patch=0/1/2/3`, named groups, serial/CRC naming, and cheat-folder behavior. **Source of compressed-image support:** [PCSX2 2.0 release](https://pcsx2.net/blog/2024/pcsx2-2-release/).
