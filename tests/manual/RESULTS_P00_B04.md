# P00 and B04 retail PCSX2 results

**November 20, 2026 · PCSX2 2.8.2 on Linux · Japanese BIOS v01.00 · OpenGL (Mesa llvmpipe).** The original `SLPM-66301` ISO matched SHA-256 `6e58b52aa5c03d45e413e8473be52a39205095e34a1bd58dae6bd852eb4fb1db` and PCSX2 CRC `420C7FAB`. No PNACH profile was active. Cheats and patches were disabled for the debugger run.

**P00 passed.** The title reached Mode Select. Arcade, Arrange, Gallery, and Option opened their respective screens, and Exit returned to the title. This run verified frontend navigation. No full gameplay or hardware test was performed.

**B04 passed for the retail frontend paths.** The live EE debugger hit `0x001CA42C` (selector), `0x001CA798` (accept dispatcher), and each of the five choice branches.

| Menu choice | EE PC at breakpoint | Result from the branch and observed screen | Workspace capture |
|---|---|---|---|
| Arcade | `0x001CA800` | State 2, Arcade submenu | `b04-arcade.png` |
| Arrange | `0x001CA824` | State 9, Arrange submenu | `b04-arrange.png` |
| Gallery | `0x001CA848` | Request 2, Gallery screen | `b04-gallery.png` |
| Option | `0x001CA860` | State 13, Option screen | `b04-option.png` |
| Exit | `0x001CA7E4` | Request 1, title screen | `b04-exit.png` |

The debugger showed `$gp = 0x0033FCF0` at the Arcade dispatcher and Exit breakpoint. At Exit, the selected-index word was `4` at `0x00339484` (`$gp - 0x686C`), and the frontend state was `1` at `0x00338F58` (`$gp - 0x6D98`), before the Exit handler ran. Both candidate descriptor words at `0x002A90D8` and `0x002A90DC` matched the zero values from the static audit. The candidate animation and fade words at `0x00500634`, `0x00500654`, and `0x00500674` were also zero in that snapshot. These observations establish their values at this breakpoint. A menu hook still needs to establish their lifetime and check neighboring accesses.

The local workspace contains `retail-pcsx2.log`, `retail-debug.log`, the debugger screenshots, and the `b04-ram-*.png` memory captures under `/workspace/work/pcsx2`. The source audit suite reported 20 passes and zero failures.
