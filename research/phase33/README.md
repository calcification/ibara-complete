# Phase 33 — Stage-6 rose form: repeat trials (Claude, 26 November 2026)

Follows Codex's phases 30–31. Question: why did the PS2 with BL's rose barrage and burst size (mode 3) take
longer than the BL reference (3,712 vs 3,272 frames), and should it ship?

## The rose core's logic is the same in both games

* Rose core (type 74, slot 85) phase machine: phase `+0x9F`, sub-state `+0xA0`, timer `+0x50`, rose kind `+0x98`.
  Both games stay in **phase 1** for the whole rose form and cycle sub-states 0 → 1 → 2 → 3 → 4 → 5 (~303 frames a
  cycle; roses in sub-states 1 and 3, through path 1). The phase-2/3 limits are 10,800 / 7,200 in both
  (BL 0C0A2A50 / 0C0A2F00, PS2 0x00178A30 / 0x00178CA4); the core dies at timer ~3,150–3,600, long before.
* Sub-state 0 sets the kind with `rand(4)` in both (BL 0C0A2AD8, PS2 0x00178ECC). The linked part's subtype is
  kind + 1 in both constructors (BL 0C0A8190, PS2 0x00163278); the rose's speed word is 0x1C000 in both.
  One difference: BL's linked part flags are 0xD300C100, the PS2's 0xD3004100 (bit 15). Linked parts never take
  damage in either game, so it has no visible effect here.
* Both random generators are the same LCG (`seed × 0x41C64E6D + 0x3039`, 15 bits; BL 0C0C2360 at 0C207578,
  PS2 0x00110FE0 at `$gp-32744`).
* `bl_rose_kind.lua` (MAME tap): all 2,137 BL roses of the reference run came from path 1 (return 0C0A2C34) with
  kinds 0, 2, 3. The reference run simply never drew kind 1; the PS2 runs did. That is chance, not a rule.

## One run is not enough: BL varies a lot

Rose-core length (first positive HP to zero HP, every 4 frames), rank 0x800000, shot level 2, stationary player:

| Run | n | Rose core | Mean | First core |
|---|---:|---|---:|---|
| BL (MAME): Codex's reference + 16 replays of a stage-frame-10,500 checkpoint with seeds 1–16 (`SEED=`) | 17 | 3,272 – 4,716 | **4,053** (sd 438) | 4,964 – 6,552 (mean ≈ 5,660) |
| PS2 mode 3 (barrage + BL burst size): Codex's run + seeds 1–4 (`BL_ROSE_SEED`) | 5 | 3,368 – 4,032 | **3,663** | 3,004 – 3,936 (mean ≈ 3,620) |
| PS2 mode 0 (retail roses, as shipped): Codex's run + seeds 1–4 | 5 | 2,988 – 3,296 | **3,103** | same as mode 3 |

Codex's BL reference (3,272) is the shortest of the 17 BL runs. Against BL's spread, the shipped PS2 rose form is
about 23 % short and below every BL run but one; mode 3 is about 10 % short and inside BL's range. Every same-seed
pair puts mode 3 400–840 frames above mode 0.

Rose lifetimes (`ROSES=1` / `BL_ROSE_LIFE`): main parts live ~71 frames median in both games, with the same
bimodal shape (shot within ~20–30 frames, or ~80–100 frames on screen).

## Conclusion

* The barrage + burst-size combination (Codex's mode 3) moves the rose form from clearly short to inside BL's range,
  and adds BL's type-14 barrage. It did not overshoot: the earlier "too long" reading came from comparing with one
  unusually short BL run.
* Remaining: mode 3 still averages ~10 % shorter than BL (5 vs 17 runs; more PS2 runs would tighten this).
* New, larger gap: the **first core** (same 359 HP) lasts ~5,660 frames in BL against ~3,620 on the PS2 (≈ 55 %
  longer in BL). Not investigated yet.

## Tools

* `tools/stage_compare/bl_stage_log.lua`: `ROSES=1` (roses.txt, one line per rose), `CORESTATE=1` (phase machine
  lines in core.txt), `SEED=` (seed after `RESUME_STATE`).
* `bl_rose_kind.lua`: `CONTACT_TAP` module (with `-nodrc`): caller and kind of every rose constructor call.
* `ps2/hooks/spawnlog.c` `BL_ROSE_LIFE`: PS2 rose records at 0x01FD0000, core phase changes at 0x01FEE000.
* `ps2/hooks/rose_probe.c`: `BL_ROSE_MODE` (trial mode built in), `BL_ROSE_SEED` (seed at stage-6 tick 10,000).
* Build and run as phase 30; summarise saves with `research/phase30/report_roses.py`.
