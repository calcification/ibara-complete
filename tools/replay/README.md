# Frame-indexed emulator tests

Use this harness to check recording playback within each emulator, then compare aligned gameplay traces. The native formats are separate: MAME writes its own INP via `-record`, while the Python tool writes PCSX2 v2.8.2's v1 P2M2 layout with its matching savestate sidecar. Keep ROMs, ISOs, BIOS files, NVRAM, recordings and savestates local.

## Input scenarios

The JSON format uses zero-based frames. Each `[count, controls]` segment holds exactly those controls for that many frames. The next segment replaces the entire held set. Frame 0 is the first update from the declared `anchor`. The order of mask bits, from least to most significant, is `up down left right shot bomb aux aux2 start coin select`. The PS2 build's default in-game map is Cross for shot, Circle for bomb, Square for weapon change, Triangle for aux2, and the D-pad for directions. To override a binding, pass `--map path.json` with logical keys and DualShock button names, or `null` for an unmapped control. MAME binds bits to `:PORT_C` and `:PORT_D` on the `ibarablk` set.

| Scenario | Anchor | Frame sequence |
|---|---|---|
| `movement.json` | Stage 1, player controllable | Neutral, then four moves while holding shot |
| `bomb.json` | Same start, at least one bomb | Shot, then press bomb for one frame at frame 60 |
| `cancellation.json` | Stage 1 with hostile bullets and a bomb in stock | Wait, press bomb on frame 30, observe bullet and enemy counts |

Use these scenarios with the same ship, difficulty, starting stock, and stage on both systems. Track any test-only modifications, config hash, controller mapping, video mode and storage state with the run. Start repeated runs with the same build, emulator version, checkpoint and RNG policy. A checkpoint should include the game, not just a menu screenshot. Record how and where RNG was preserved or observed. When seeds are unavailable, record `initial: null` and use the repeat traces to check stability. Preserve native frame numbers and establish the offset from each emulator's verified anchor before reporting cross-emulator frame differences.

## MAME 0.276

With your own `ibarablk.zip` in a ROM directory, use Python 3.11 or later:

```sh
python3 tools/replay/run_mame.py tools/replay/scenarios/movement.json outputs/replay-mame-move --rompath /path/to/roms
python3 tools/replay/run_mame.py tools/replay/scenarios/bomb.json outputs/replay-mame-bomb --rompath /path/to/roms
python3 tools/replay/run_mame.py tools/replay/scenarios/cancellation.json outputs/replay-mame-cancel --rompath /path/to/roms --start 3425 --require-bullets
```

Each command creates its own work directory, boots with fresh factory settings and no persisted NVRAM, and records a fixed coin/start/default-selection prelude plus the scenario in a native INP. The two playback passes omit Lua input overrides and sample the emulated input ports. The runner compares both playback CSVs to the recorded trace. It uses callback 3101 for the default stage-entry checkpoint. For cancellation, callback 3425 starts with hostile bullets already on screen. A stage check and the optional bullet and bomb-stock checks guard that checkpoint.

The sampler exports integer player coordinates in the game's native axes, score, stored inverted rank, hostile bullet count, live enemy count, the first live slot's type/state/HP, raw stage byte (2 for stage 1), lives, and bomb stock. An empty enemy slot is recorded with empty enemy fields. Compare slot tuples across platforms only after matching the logical enemies. Supply `--xtc-address` and `--rng-address` only when you have verified 32-bit addresses for this ROM revision. For a verified counter stored in quarter steps, use `--xtc-divisor 4`. The recorded runs leave these fields unobserved.

## PCSX2 2.8.2

Enable **Input Recording Tools** under Advanced settings. Use a pinned emulator build and isolated settings and memory cards. For gameplay runs, disable cheats and MTVU and use a Stage 1 checkpoint with a stable controller and settings matched to MAME. For the standalone homebrew test, build the ELF with PS2DEV v2.0.0, boot it with PCSX2's ELF loader, and save a state after the probe says **waiting for first button**.

```sh
mkdir -p outputs/replay-ps2
make -C outputs/replay-ps2 -f "$PWD/tools/replay/ps2_probe/Makefile"
python3 tools/replay/replay.py pcsx2-movie tools/replay/scenarios/movement.json outputs/replay-ps2/movement.p2m2 \
  --state /path/to/ready.p2s --title 'replay-probe [?]' --lead 45 --tail 8 --probe-sync
```

Use **Tools → Input Recording → Play** to open `movement.p2m2`. If PCSX2 stays paused after loading, resume once and wait until playback finishes and PCSX2 pauses again. Save an end state. Play the same movie again from its automatically loaded sidecar and save a second end state. Extract and compare the traces:

```sh
python3 tools/replay/replay.py ps2-probe-csv tools/replay/scenarios/movement.json /path/to/end-1.p2s outputs/replay-ps2/first.csv --skip 4
python3 tools/replay/replay.py ps2-probe-csv tools/replay/scenarios/movement.json /path/to/end-2.p2s outputs/replay-ps2/second.csv --skip 4
cmp outputs/replay-ps2/first.csv outputs/replay-ps2/second.csv
```

The homebrew probe listens for the four-frame Select marker added by `--probe-sync`. The 45 neutral lead frames precede that marker and are outside both the scenario and the probe log. The eight neutral tail frames allow the final polls to settle. The saved probe observes the actual DualShock inputs and logs synthetic position and shot counts. On Python older than 3.14, install `zstandard` if the savestate uses ZIP compression method 93. `pcsx2-input` decodes encoded movie masks for diagnosis. Use the comparison command below to check the observed masks against the plan as well as checking the replays against each other. [PCSX2 2.8.2 recording format source](https://github.com/PCSX2/pcsx2/blob/v2.8.2/pcsx2/Recording/InputRecordingFile.cpp)

### Project telemetry adapter

`ibara_ee_trace.c` is an opt-in observer for the current PS2 memory layout. Link it into a diagnostic build and reserve a `struct bloom_trace` in that build's writable EE RAM. Call `bloom_trace_reset` at the verified stage anchor before the first sampled update, then `bloom_trace_sample` once after each update using the actual held controls converted to the scenario bit order and the displayed XTC value. Do not use the homebrew probe's address by default in the project build. An existing hook or buffer may occupy that address. Use a controller checkpoint that already precedes the first input poll and omit `--probe-sync` in gameplay.

Extract the end state with `ps2-probe-csv ... --address ADDRESS --fields observed_input player_x player_y score rank hostile_bullets enemies enemy_type enemy_state enemy_hp stage bomb_stock lives xtc`. The capture ABI is an eight-byte little-endian header (magic `0x46524231` and row count) followed by 32-bit words in the stated field order. Use `0xffffffff` for absent enemy fields. The coordinate fields use signed integer pixels in native game axes. Verify the sample boundary and field meanings before using them for parity decisions.

The tested diagnostic build was an isolated checkout of `b9c0a00`. In that checkout, copy the observer sources into `ps2/hooks`, add `ibara_ee_trace.c` to the `bl_mode` source list in `scripts/build_ee_hooks.py`, and include the header in `xtc.c`. The test called the observer after `xtc_add` in `xtc_frame`, gated on the stage byte being 2 and P1's `PLAYER_CAN_BE_HIT` flag. It sampled the low six bits of `PS2_PLAYER_HELD` and P1's displayed XTC. Higher buttons need a separate verified mapping. The scratch build used a buffer at `0x01F70000`, reset on first activation, with cheats and MTVU disabled. Reconfirm that this buffer fits in free RAM before using it on another build. With PS2DEV in place of the GNU cross toolchain expected by the hook builder, link with the `elf32lr5900` emulation for its o32 objects.

Boot the diagnostic ELF with the clean disc mounted using `pcsx2-qt -fastboot -elf trace-port.elf -- 'Ibara (Japan).iso'`. Save a ready-to-play Stage 1 state and record the buffer count at that checkpoint. Build a movie without the probe marker, replay twice from the same state, and account for the native input poll boundary when selecting the first row. Our checkpoint already held 73 rows. Extraction at offset 73 exposed a one-frame input delay. Offset 74 aligned all 300 masks, with independently matching press and release transitions. This offset is specific to the checkpoint and hook.

## Comparison

The CSV has a sequential `frame` column, `observed_input` masks from the actual runtime, and a subset of the telemetry fields above. For each run, use a JSON sidecar such as:

```json
{
  "emulator": "PCSX2",
  "version": "2.8.2",
  "build": "record the exact title/build fingerprint",
  "checkpoint": "record the checkpoint hash and native frame",
  "anchor": "stage1_player_control",
  "scenario_sha256": "use the hash printed by the generator",
  "sampling": "post_update",
  "settings": {"stage": 1, "difficulty": "factory default", "ship": "default selection", "bomb_stock": 1, "lives": 2},
  "rng": {"policy": "restored checkpoint", "initial": null}
}
```

```sh
python3 tools/replay/replay.py compare tools/replay/scenarios/movement.json \
  run-a.csv run-b.csv run-a.json run-b.json --repeat --fields player_x player_y score
```

Run a same-emulator comparison with `--repeat` first. It requires identical context and reports the earliest input and selected telemetry differences independently. For a cross-emulator run, remove `--repeat` after both same-emulator checks pass. Compare fields only after verifying their units and matching sample boundaries. A state mismatch with verified inputs is a gameplay difference in the trace, with possible causes including the checkpoint, RNG, timing, or port behavior. Missing input observations keep state differences unclassified. Return statuses are 0 for match, 1 for divergent or unverified, and 2 for invalid input. Screenshots and physical PS2 runs are deferred. A future screenshot comparator should match gameplay frame, orientation, crop and scale before comparing pixels.

## Verified locally

- MAME 0.276 on Linux: Stage 1 native INP record plus two playbacks each for movement, bomb, and cancellation. Every trace matched its recording and the proposed controls across all 300 frames. The cancellation trace started with two counted hostile bullets. Bomb stock fell from 1 to 0 on frame 31 and the hostile bullet count reached 0 on frame 34.
- PCSX2 2.8.2 on Linux: the original homebrew probe replayed the same generated native P2M2 twice per scenario with the same sidecar and emulator settings (MTVU was enabled for these probe runs). Every exported 300-frame trace matched its sibling and the proposed controls, including the one-frame bomb presses.
- The instrumented PS2 port replayed movement twice from the same Stage 1 sidecar. Without correcting the poll offset, the comparator reported `input_desync` at frame 30. The aligned 300-frame traces matched across all captured fields. The PS2 checkpoint had zero bombs and no live enemies at frame zero, while the MAME movement checkpoint had one bomb and three live enemies. Cross-emulator gameplay comparison and the PS2 port's bomb and cancellation runs await matched checkpoints.
