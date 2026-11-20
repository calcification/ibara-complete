# M03 · Launcher and progressive video round trip

The launcher video profiles passed in PCSX2 2.8.2 on Linux using Japanese BIOS v01.00 and Mesa OpenGL. Each test used a separate image built from the verified retail ISO, the original M02 controller test ELF, the label `PAD TEST`, and a blank disposable memory card. PCSX2 cheats and built-in patches were disabled.

| Build option | Retail EE words checked before launch and after return | GS scan before launch and after return |
|---|---|---|
| `240p_core` | 14 patched words and 4 original coordinate words matched | Progressive with 224 active lines |
| `240p_halfpixel` | All 18 patched words matched | Progressive with 224 active lines |
| `240p_cave_beta` | All 21 patched words matched | Progressive with 224 active lines |

All three images displayed `PAD TEST`, ran the controller program at `0x00100F78`, and reloaded the retail ELF at `0x00100008` after **Return to Ibara**. The probe used its own video settings during the handoff. The GS dumps taken during retail execution before launch and after reloading had `SMODE2.INT = 0` and 224 active lines on read circuit 2. All disposable cards matched their original bytes.

`240p_core` and `240p_halfpixel` share the XOR CRC `F6BD9C30`. `240p_cave_beta` has CRC `F6BE9C30`. The builder reports a SHA-256 for each variant.

| Build option | Retail ELF SHA-256 |
|---|---|
| `240p_core` | `a9e29661ce59472a16f00711dd3d4b7ec352c6952876495238d5c0fbc9006e11` |
| `240p_halfpixel` | `f23b4c3efb44dd49c056a6b2e31701fb24bdc187916e1e1d708af0226250937d` |
| `240p_cave_beta` | `8fff23ec6537018a393ec5e6608804efdbb75ff741648f79e4c56848bbfaf50c` |

Follow the [payload handoff](../../docs/PAYLOAD_HANDOFF.md) to build the image. Use the M02 ELF as the payload and choose `PAD TEST` for the label to reproduce this test. Capture a GS dump and save state before launch and after return.

## Physical PS2 report

On November 20, 2026, the tester reported a working `240p_core` round trip with diagonal scrolling shimmer. In a follow-up on the same PS2 setup, `240p_cave_beta` reduced the shimmer to the level of the previously published Cave 240p patch. This establishes visual parity with that patch on the tested setup. Console model, ISO loader, display, and measured scan mode were unspecified.

Use `--video-profile 240p_cave_beta` when you want the launcher image to use the published patch's video settings. The 21 video writes reproduce the Ibara video-only ELF byte for byte before the launcher edits are applied. The published beta records some residual shimmer. [Cave 240p beta patch specification](https://github.com/calcification/cave-ps2-240p/blob/v0.1.0-beta.1/docs/PATCH_SPEC.md#ibara)
