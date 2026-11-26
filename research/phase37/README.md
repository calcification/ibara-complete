# Phase 37 — Stage-6 first core (Claude, 26 November 2026)

Same 359 HP in both games, but the first core lasts ~5,660 frames in BL (17 seeded runs, 4,964–6,552) against
~3,620 ticks on the PS2 (6 runs, 3,004–3,936). Rank 0x800000, shot level 2, stationary player, as phase 33.

## HP over time (BL checkpoint replay vs PS2 mode-3 seed 7)

| Frames after the core appears | BL HP | PS2 HP |
|---|---:|---:|
| 400 | 358 | 354 |
| 1,000 | 358 | 284 |
| 1,400 | 358 | 237 |
| 2,000 | 338 | 166 |
| 3,000 | 307 | 81 |
| 3,800 | 250 | 0 |

The core sits at the same place (x 240, y 512 from frame 400) and moves alike in both. BL's core flag word is
D3008100 throughout (no invulnerable window).

## Parts (type 74) during the first core

`bl_stage_log.lua PARTS=1` (BL) and `BL_PART_STATS` (PS2): spawns and HP lost per subtype.

| Subtype | BL spawns / HP lost / start HP | PS2 spawns / HP lost / start HP |
|---|---|---|
| 0x10 | 5 / 215 / 71 | 5 / 195 / 71 |
| 0x11 | 9 / 291 / 71 | 8 / 363 / 71 |
| 0x12–0x18 | start HP 40 / 37 | start HP 27 |
| 0x18 | 9 / 97 | 6 / 48 |
| 0x1A–0x1F | start HP ~71, appear ~2,020 after the core | start HP 71, appear ~2,044 after |
| 0x20 | 16 / **359** / 66 | 15 / **254** / 71 |
| 0x28 | 10 / 179 / 43 | 13 / 174 / 43 |
| 0x29 | start HP 23 | start HP 13 |

The shields (0x10, 0x11, 0x28) exist and absorb about the same in both. In BL the 0x20 parts lose exactly the core's
359 HP, and the core only starts dropping once they appear: BL's core seems to take its damage through the linked
0x20 parts, hardly directly. The PS2's core is hit directly from the start.

## BL damage function (0C0A8E90) vs PS2 (0x001278B0)

* Parent links: both follow +0x7C while flag 0x4000 is set.
* Both refuse damage with flag 0x20000000, and for parts past x 0x120 unless a global is set.
* BL only: no damage when the part's HP ≤ 14 and bit 15 of (caller's mask & part flags) is set (0C0A8F5A). The PS2
  creates parts without bit 0x8000 (e.g. rose linked part BL 0xD300C100 vs PS2 0xD3004100). Not the core's cause
  (HP 359), but a real difference.

## Where the shots go (contact traces, first 1,400 frames of the core)

BL (`bl_contacts.lua`, checkpoint replay): the core is touched 9 times (1 HP); the shields take the rest (0x10
1,305, 0x28 883, 0x11 665 contacts). PS2 (`BL_CONTACT_ALL74`): the core 837 contacts (98 HP), the shields about
as often as in BL. The core's own hitbox is empty in both (it takes damage only through linked parts: slot 1
sub 0xE, the six-part ring 0x19, sub 3 / 5–7); hitbox sizes of every linked part and shield are identical; and the
first hittable part in the player's lane is the same shield in both games (0x28 / 0xF / 0x10, same shares).

By shot type: every BL contact is shot type 0; on the PS2, type-3 shots make 828 of the core's 837 contacts and 97 of
its 98 HP. BL's collision pool (0C2A6D9C) holds only type-0 shots in this window (4,396 new shots).

### The cause: different pods, and one real rule

* **Set-up mismatch.** The BL reference run (natural route) reaches stage 6 with weapon 6 and three pods of shot kind
  12; the PS2 Practice run has weapon 0xFF and pods of kind 10, which fire the type-3 shots. Phases 30–33 matched ship
  and shot level, not pods, so their first-core and rose numbers compare different weapons.
* **Piercing shots (real rule).** BL's shot-vs-enemy loop takes the next shot after any damage call (0C06E404 →
  0C06E308, also for shots with flag 0x00800000). The PS2's main-shot loop sends a 0x00800000 shot on to the next
  enemy after scoring (0x0012B588 → 0x0012B5B8), so it can hit a shield and the ring behind it in one frame. Noir
  now patches 0x0012B5B4 `nop` → `b 0x0012B370` (candidate, committed). Alone, with the mismatched pods, it moved the
  first core from 3,566 to 4,054 ticks on average (seeds 1–4) and the rose core from 3,651 to 3,558.

## Matched pods (BL_FORCE_POD_WEAPON=6: weapon 6, three pods of kind 12, as the BL run)

PS2 mode 3 (K58 roses) + the piercing patch, seeds 1–4:

| | First core | Rose core |
|---|---|---|
| BL, 17 runs | 4,964–6,552, mean ≈ 5,660 | 3,272–4,716, mean 4,053 |
| PS2, BL's pods | 4,864 / 5,884 / 6,044 / 6,032, mean **5,706** | 3,932 / 4,464 / 4,068 / 4,220, mean **4,171** |

With the same pods, both phases are inside BL's range: most of the earlier first-core gap was the set-up.

PS2 mode 0 (retail roses) with BL's pods, seeds 1–4: rose core 3,696 / 3,304 / 3,104 / 3,508, mean **3,403**; first core
6,444 / 5,476 / 5,924 / 5,520 (mean 5,841). So the K58 rose changes are still needed with matched pods (3,403 → 4,171
against BL's 4,053); the first core needs no change.

## Conclusion

* No first-core gameplay difference beyond the piercing rule: with the same pods the PS2 first core matches BL.
* The piercing rule ships as **K60** (BL's shot loop; affects weapons whose shots carry 0x00800000, e.g. the kind-10
  pods' type-3 shots).
* Lesson for all comparisons (handoff): match the pods (weapon and pod kinds), not only ship and shot level.

Compare the core's own hit area / collision settings, then trace which part each player hit lands on (Codex's
`research/phase31/bl_contacts.lua`).
