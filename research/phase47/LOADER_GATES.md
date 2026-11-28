# Replay format 4: loader gates and the Stage 1 start

Format 3 fixed Noir's late slip (the target search cursor) but every
Noir playback still split early, and Arcade split too once its replays
were recorded after another game. Format 4 removes the remaining causes
found in PCSX2 2.8.2. Each fix below was found with the trace build
described at the end.

## Loader gates

The disc and texture loaders run beside the game, so the number of
updates a load takes changes from run to run. A few game decisions
read the loader. Every one found goes through one of these:

| Kind | Code | Question |
| --- | --- | --- |
| 0 `G_RES` | 0x00135D70(type), called by every enemy factory (53 sites) | Are the type's textures resident? A miss queues them; the factory spawns nothing. |
| 1 `G_BG` | script FF08, 0x00114E20 | Are the background layers' textures resident? |
| 2 `G_QUEUE` | script FF27, 0x00114820 | Is the texture queue (0x00448700) empty? |
| 3 `G_QUEUES` | script FF28, 0x001147E0 | Are the disc (0x00447F00) and texture queues empty? |
| 4 `G_REQ` / 5 `G_REQ2` | script FF0C 0x00114B40, FF10 0x00114B20 | Queue a texture group; 0 when the loader has no room. |

The stage script interpreter (0x00115620, table 0x001EAC10 indexed by
the command's low byte) runs a command again at the next update when
it returns 0. The other script commands and the remaining readers of
the queues (the loader itself, the frontend at 0x001CF168) do not decide
gameplay.

FF27 and FF28 also set 0x00338F40 ($gp-28080). While it is set, the main
state machine (0x00113400) calls 0x0013BFA0 before the game loop every
frame; once the queues are empty, that routine runs the stage script
itself, between two updates. So the Stage 1 FF27 wait usually ends
outside an update (Codex's note that "the draw path can also call the
stage interpreter"). These checks count as well.

The recorder keeps every answer, in order, from the replay's start.
Answers given between updates belong to the update before them: the
stream writes an update's fields one update late, after its list. An
update with checks is preceded by `0x81`, a count byte and the checks
(u16: kind << 12 | argument << 1 | result).

Playback hands the game the recorded answer for each check. A check
that comes true early answers 0 until its recorded update. Before an
update whose recorded checks came true, `rpl_may_update` evaluates
them (kinds 0–3; the queue requests move the script cursor and are not
evaluated ahead). If one is still false, the game takes the retail
draw-only path at 0x0012E1EC for that frame: the loaders run, the input
and the stage clock wait. Checks during a hold answer 0. A hold gives
up after 600 passes (10 seconds) and plays on.

Typical Noir run: 342 failed FF27 checks, 80 residency checks, 5 queue
requests; playback held 5 frames, every check matched.

## Stage 1 start for every mode

A replay now starts at Stage 1's first update (scene 2) in every mode
except Practice. Arcade and Arrange spend about 200 updates in an
opening scene first, and the stage byte (0x00338E9C) is left over from
the previous game: 0 after boot, the last stage after a game. With 1
left over, the opening's first update runs the stage script at once.
Format 3 did this for Noir only. Practice starts at the game's first
update, as before.

## Start state

At the start point both the recorder and the player run the K62 clean
start (`game_start_reset`): shots, pod shots (0x0044D6C0, 96 × 0x34),
bullets, items, the XTC phase and the boss-cancel tracker. The player is
usually firing as the select screen or opening hands over; the shots in
flight would otherwise exist only in the recording.

The header adds, after format 3's cursor and tick:

* `shot0[4]`: 0x00338F48–0x00338F54. 0x00338F4C counts how long shot has
  been held (0–8) and sets the auto-fire rate at 0x0013B484. The game
  zeroes these at a game's start, but by Stage 1 shot is often held.
  Without it the first shots came 6 updates late and every random
  number after them was shifted.
* `pods0[72]`: the six pod records at 0x0044C8A0 (position, heading,
  target). Playback skips the select screen, so the pods are elsewhere.

Formats 2 and 3 still load and play as before.

## Results (PCSX2 2.8.2, release REPLAY menu, real memory card)

Per-update checkpoints (score, seed, scene and tick) over the whole run:

| Mode | Updates | Matching |
| --- | ---: | --- |
| Noir | 2,209 | all, end state matches |
| Noir | 2,257 | all, end state matches |
| Noir | 1,903 | to update 1,048; an enemy died one hit early in playback (open) |
| Arcade | 1,871 | all, end state matches |

Before format 4 the same Noir test split at update 1 or 2, and the
format 3 build at update 1.

## Trace build

`RPL_TRACE` with `RPL_CK_EVERY=1u` writes a checkpoint per update
(recording 0x01EA0000, playback 0x01EB0000). `RPL_TRACE` also logs
every gate check (0x01EC0000 / 0x01EC8000). `RPL_RNG_TRACE` with the
patch `(0x00111050, 0x0C0580C4, "jal", "rpl_rng_entry")` logs every RNG
advance with its caller (0x01ED0000 / 0x01EE0000). `RPL_HP_TRACE` keeps
each enemy slot's HP per update while recording and stores the first
difference found during playback at 0x016F0000.
