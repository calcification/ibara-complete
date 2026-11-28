/* Replays for release (research/phase47): every game is recorded into RAM; a recording can be saved to the memory
 * card (mcfile.c) and played back. Method from research/phase44 (and Codex's phase 45):
 *   - inputs are recorded per game update (game_start.c calls rpl_update at 0x0012E5CC), not per pad read;
 *   - per update: the pad block words the game reads through its accessors (0x00341FA0 + port * 0x50: +0 current,
 *     +8 pressed, +0x0C auto-repeat; the block is rebuilt per vsync), both players' button words (+0x24C .. +0x254)
 *     and the rank change (Arcade rank creep runs per loop pass with a timing-dependent step);
 *   - the frame counter 0x00338CDC counts updates during a game, not vsyncs (it drives item cycling);
 *   - the start state (seed, frame counter, spawn counters, rank state, both player records) is in the header.
 * File: struct rpl_head, then the update stream. Stream: a byte 0x00-0x7F repeats the previous update n + 1 times;
 * 0x80 is followed by a 3-byte mask of changed 16-bit fields (FIELDS of them) and the new values.
 * Format 4: an update whose loader checks ran is preceded by 0x81, a count byte and the checks (u16 each: kind << 12 |
 * argument << 1 | result) -- see "Loader gates" below.
 * The header carries the stream length and a checksum (Adler-32 over the header after the checksum and the stream). */
#include "ibara_ps2.h"

#define SEED       0x00337D08u
#define FRAMES     0x00338CDCu
#define GROUP_ID   0x00338E4Cu
#define TARGET_CURSOR 0x00338B98u /* shared round-robin enemy search in 0x00137DA0 */
#define TARGET_COUNT 192u
#define SCENE      0x00338E9Cu
#define TICK       0x00338EA0u
#define RANK       0x00338EB4u
#define ATTRACT    0x00338E7Cu
#define MAIN_STATE 0x00338B08u
#define PADBLK     0x00341FA0u
#define FIELDS     18u /* 2 ports x (current, pressed, repeat), 2 players x 5 words, rank change (2 halves) */

#define RPL_MAGIC  0x42464249u /* "IBFB" */
#define RPL_FORMAT 4u           /* 4: loader gates in the stream; 3: same header, no gates; 2: no cursor or tick0 */
#define RPL_BUF    ((u8 *)0x01700000u) /* header + stream; RAM unused in the frontend and in games */
#define RPL_MAX    0x00700000u

struct rpl_head {
	u32 magic, sum, version, head_size;
	u32 length;        /* stream bytes after the header */
	u32 updates;       /* updates recorded */
	u32 mode;          /* bit 0..3: 0 Arcade, 1 Arrange, 2 Noir; bit 8: Practice */
	u32 stage, end_score, end_seed, end_tick, difficulty; /* Arcade GAME START: 0 NORMAL, 1 HARDER, 2 EXTENDED */
	u8 arcade[8];      /* Arcade CONTINUE and CONFIG (DIFFICULTY 1 / 2, EXTEND, PLAYER STOCK, BOMB STOCK) */
	u32 fighter[2];    /* CONFIG > FIGHTER TYPE per side (the ship; Noir's select screen writes it) */
	u32 seed0, frames0, group0[2], rank0[4];
	u32 players0[2u * PS2_PLAYER_STRIDE / 4u];
	u32 target_cursor, tick0;
	u32 shot0[4];      /* format 4: 0x00338F48..54, the shot-held counter and its neighbours (zeroed at a game's start;
			    * a Noir recording starts at Stage 1, after the select screen, with shot often already held) */
	u32 pods0[6u * 0x30u / 4u]; /* format 4: the pod records 0x0044C8A0 (3 per side: position, heading, target) */
};
#define PODS 0x0044C8A0u
#define RPL_FORMAT2_SIZE __builtin_offsetof(struct rpl_head, target_cursor)
#define RPL_FORMAT3_SIZE __builtin_offsetof(struct rpl_head, shot0)
#define SHOT_STATE 0x00338F48u

enum { RPL_OFF, RPL_REC, RPL_PLAY };
u32 rpl_mode = RPL_REC;      /* what the next game does */
static u32 cur;              /* what this game does (latched at its start) */
static u32 last_recorded;    /* the buffer holds a finished recording (not a playback) */
extern u32 kuro_on;
static u8 active, started;
static u32 pos, run, play_left;
static u16 prev[FIELDS], next[FIELDS], last_raw[2]; /* playback: next = the coming update, decoded ahead */
static u16 pend[FIELDS];     /* recording: this update's fields, written after its loader gates at the next update */
static u32 emitted;          /* recording: updates written */
static u32 rank_prev;
static u32 play_pending;     /* a loaded replay waits for its game */
static u8 user_arcade[8];
static u32 user_fighter[2];
#define ARCADE_CONTINUE 0x00338BECu
#define ARCADE_CONFIG   0x00338BF4u
#define FIGHTER_TYPE    0x004E5050u
#define PAD_START       0x2000u /* Start in the pad block's current word */

static volatile u8 *arcade_setting(u32 i)
{
	return (volatile u8 *)(i == 0 ? ARCADE_CONTINUE : ARCADE_CONFIG + 4u * (i - 1u));
}
u32 rpl_stat[8];             /* plays: updates, end mismatch, stream errors, (debug) */

#define HEAD ((struct rpl_head *)RPL_BUF)

static void fields(u16 *f, u32 rank_change)
{
	u32 p, i;
	for (p = 0; p < 2; p++) {
		f[p * 3 + 0] = (u16)EE_RAM(u32, PADBLK + p * 0x50u + 0x0u);
		f[p * 3 + 1] = (u16)EE_RAM(u32, PADBLK + p * 0x50u + 0x8u);
		f[p * 3 + 2] = (u16)EE_RAM(u32, PADBLK + p * 0x50u + 0xCu);
	}
	for (p = 0; p < 2; p++)
		for (i = 0; i < 5u; i++)
			f[6 + p * 5 + i] = EE_RAM(u16, PS2_PLAYER_BASE + p * PS2_PLAYER_STRIDE + PS2_PLAYER_HELD + 2u * i);
	f[16] = (u16)rank_change;
	f[17] = (u16)(rank_change >> 16);
}

static u16 prev_applied; /* the current word applied for port 0 at this update */
static void apply(const u16 *f)
{
	prev_applied = f[0];
	u32 p, i;
	for (p = 0; p < 2; p++) {
		EE_RAM(u32, PADBLK + p * 0x50u + 0x0u) = f[p * 3 + 0];
		EE_RAM(u32, PADBLK + p * 0x50u + 0x8u) = f[p * 3 + 1];
		EE_RAM(u32, PADBLK + p * 0x50u + 0xCu) = f[p * 3 + 2];
	}
	for (p = 0; p < 2; p++)
		for (i = 0; i < 5u; i++)
			EE_RAM(u16, PS2_PLAYER_BASE + p * PS2_PLAYER_STRIDE + PS2_PLAYER_HELD + 2u * i) = f[6 + p * 5 + i];
	rank_prev += (u32)f[16] | (u32)f[17] << 16;
	EE_RAM(u32, RANK) = rank_prev;
}

/* playback: decode the next update's fields into next[]; pad reads until then see its pads (as recorded, the pads
 * read before an update are the ones it uses) */
static u16 gate_ev[2][256];  /* recording: [0] this update's gates; playback: [ev_nx] the coming update's, else this one's */
static u32 gate_cnt[2], gate_i;
static u8 ev_nx, in_update, gates_on;

static void decode(void)
{
	u32 i, mask;
	gate_cnt[ev_nx] = 0;
	if (run) {
		run--;
	} else {
		u8 op = RPL_BUF[pos++];
		if (op == 0x81u) { /* this update's loader gates, then its fields */
			const u32 n = RPL_BUF[pos++];
			for (i = 0; i < n; i++, pos += 2u)
				gate_ev[ev_nx][i] = (u16)(RPL_BUF[pos] | RPL_BUF[pos + 1] << 8);
			gate_cnt[ev_nx] = n;
			op = RPL_BUF[pos++];
		}
		if (op < 0x80u) {
			run = op;
		} else if (op == 0x80u) {
			mask = (u32)RPL_BUF[pos] | (u32)RPL_BUF[pos + 1] << 8 | (u32)RPL_BUF[pos + 2] << 16;
			pos += 3;
			for (i = 0; i < FIELDS; i++)
				if (mask & 1u << i) {
					next[i] = (u16)(RPL_BUF[pos] | RPL_BUF[pos + 1] << 8);
					pos += 2;
				}
		} else {
			rpl_stat[2]++;
		}
	}
	last_raw[0] = next[0];
	last_raw[1] = next[3];
}

static void put(u8 b)
{
	if (pos < RPL_MAX)
		RPL_BUF[pos++] = b;
}

static void flush_run(void)
{
	if (run) {
		put((u8)(run - 1u));
		run = 0;
	}
}

/* recording: write the previous update -- its loader gates, then its fields as a change or as part of a run */
static void emit(const u16 *f)
{
	u32 i, mask;
	const u32 n = gate_cnt[0];
	for (i = 0, mask = 0; i < FIELDS; i++)
		if (f[i] != prev[i])
			mask |= 1u << i;
	if (n) {
		flush_run();
		put(0x81u);
		put((u8)n);
		for (i = 0; i < n; i++) {
			put((u8)gate_ev[0][i]);
			put((u8)(gate_ev[0][i] >> 8));
		}
	}
	gate_cnt[0] = 0;
	if (!mask && emitted) {
		if (++run == 128u)
			flush_run();
	} else {
		flush_run();
		put(0x80u);
		put((u8)mask);
		put((u8)(mask >> 8));
		put((u8)(mask >> 16));
		for (i = 0; i < FIELDS; i++)
			if (mask & 1u << i) {
				put((u8)f[i]);
				put((u8)(f[i] >> 8));
				prev[i] = f[i];
			}
	}
	emitted++;
}

static u32 adler(const u8 *p, u32 n)
{
	u32 a = 1, b = 0;
	while (n--) {
		a = (a + *p++) % 65521u;
		b = (b + a) % 65521u;
	}
	return b << 16 | a;
}

/* A replay starts at Stage 1's first update (scene 2): what comes before it (Arcade's and Arrange's opening scene,
 * Noir's opening and select screen) can take a different number of updates in a playback, and starts with state the
 * previous game left. Format 3 did this for Noir only; format 2 starts at the game's first update; Practice starts at
 * the game's first update (on any stage). */
static u32 head_stage_one(const struct rpl_head *h)
{
	return h->version >= 4u ? !(h->mode & 0x100u) : h->version == 3u && h->mode == 2u;
}

static u32 stage_one_start(void)
{
	if (rpl_mode == RPL_PLAY)
		return head_stage_one(HEAD);
	return !EE_RAM(u32, 0x00338FA4u);
}

static void game_start(void)
{
	struct rpl_head *h = HEAD;
	u32 i;
	started = 1;
	cur = rpl_mode;
#ifdef RPL_TRACE
	{ /* TEST: the enemy pool at the start (flags, type, state, parent) at 0x01EF0000 (record) / 0x01EF8000 (play) */
		u32 *t = (u32 *)(cur == RPL_PLAY ? 0x01EF8000u : 0x01EF0000u);
		for (i = 0; i < 192u; i++) {
			const u32 e = 0x0045A840u + i * 0xB4u;
			t[i * 4] = EE_RAM(u32, e);
			t[i * 4 + 1] = EE_RAM(u32, e + 4u);
			t[i * 4 + 2] = EE_RAM(u32, e + 8u);
			t[i * 4 + 3] = EE_RAM(u16, e + 124u) | (u32)EE_RAM(u16, e + 130u) << 16;
		}
	}
#endif
#ifdef RPL_TEST
	{ /* TEST: game 1 ignored, game 2 recorded, game 3 played back */
		static u32 n;
		cur = n == 0 ? RPL_OFF : n == 1 ? RPL_REC : RPL_PLAY;
		n++;
	}
#endif
	if (cur == RPL_REC) {
		for (i = 0; i < sizeof(*h) / 4u; i++)
			((u32 *)h)[i] = 0;
		h->magic = RPL_MAGIC;
		h->version = RPL_FORMAT;
		h->head_size = sizeof(*h);
		h->seed0 = EE_RAM(u32, SEED);
		h->frames0 = EE_RAM(u32, FRAMES);
		h->target_cursor = EE_RAM(u16, TARGET_CURSOR);
		h->tick0 = EE_RAM(u32, TICK);
		for (i = 0; i < 4u; i++)
			h->shot0[i] = EE_RAM(u32, SHOT_STATE + 4u * i);
		for (i = 0; i < 6u * 0x30u / 4u; i++)
			h->pods0[i] = EE_RAM(u32, PODS + 4u * i);
		h->group0[0] = EE_RAM(u32, GROUP_ID);
		h->group0[1] = EE_RAM(u32, GROUP_ID + 4u);
		for (i = 0; i < 4u; i++)
			h->rank0[i] = EE_RAM(u32, 0x00338EACu + 4u * i);
		for (i = 0; i < 2u * PS2_PLAYER_STRIDE / 4u; i++)
			h->players0[i] = EE_RAM(u32, PS2_PLAYER_BASE + 4u * i);
		h->stage = EE_RAM(u8, SCENE);
		for (i = 0; i < 6u; i++)
			h->arcade[i] = *arcade_setting(i);
		h->difficulty = EE_RAM(u8, 0x00338F0Cu); /* $gp-28132: the GAME START submenu's choice */
		h->fighter[0] = EE_RAM(u32, FIGHTER_TYPE);
		h->fighter[1] = EE_RAM(u32, FIGHTER_TYPE + 4u);
		h->mode = (kuro_on ? 2u : EE_RAM(u32, 0x00338F44u) ? 1u : 0u) | (EE_RAM(u32, 0x00338FA4u) ? 0x100u : 0u);
		last_recorded = 0;
		pos = sizeof(*h);
		run = 0;
		rank_prev = EE_RAM(u32, RANK);
		for (i = 0; i < FIELDS; i++)
			prev[i] = 0;
		emitted = 0;
		gate_cnt[0] = 0;
	} else if (cur == RPL_PLAY) {
		EE_RAM(u32, SEED) = h->seed0;
		EE_RAM(u32, FRAMES) = h->frames0;
		/* Format 2 lacks a cursor. Use the cold-start value as a stable fallback. */
		EE_RAM(u16, TARGET_CURSOR) = h->version >= 3u ? (u16)h->target_cursor : 0u;
		if (head_stage_one(h))
			EE_RAM(u32, TICK) = h->tick0;
		if (h->version >= 4u)
			for (i = 0; i < 4u; i++)
				EE_RAM(u32, SHOT_STATE + 4u * i) = h->shot0[i];
		if (h->version >= 4u)
			for (i = 0; i < 6u * 0x30u / 4u; i++)
				EE_RAM(u32, PODS + 4u * i) = h->pods0[i];
		EE_RAM(u32, GROUP_ID) = h->group0[0];
		EE_RAM(u32, GROUP_ID + 4u) = h->group0[1];
		for (i = 0; i < 4u; i++)
			EE_RAM(u32, 0x00338EACu + 4u * i) = h->rank0[i];
		for (i = 0; i < 2u * PS2_PLAYER_STRIDE / 4u; i++)
			EE_RAM(u32, PS2_PLAYER_BASE + 4u * i) = h->players0[i];
		pos = h->head_size;
		run = 0;
		play_left = h->updates;
		rank_prev = h->rank0[2]; /* 0x00338EB4 */
		for (i = 0; i < FIELDS; i++)
			next[i] = 0;
		rpl_stat[0] = rpl_stat[1] = rpl_stat[2] = 0;
		gates_on = h->version >= 4u;
		ev_nx = 0;
		gate_cnt[0] = gate_cnt[1] = gate_i = 0;
		if (play_left)
			decode();
	}
}

#ifdef RPL_DRIFT_PROBE
void drift_sample(u32 playback, u32 update, const u16 *input, u32 count);
void drift_stop(void);
u32 drift_gate_may_update(u32 update);

u32 rpl_drift_may_update(void)
{
	if (!started || cur != RPL_PLAY || HEAD->mode != 2u || !play_left)
		return 1u;
	return drift_gate_may_update(rpl_stat[0] + 1u);
}
#endif

static void game_end(void)
{
#ifdef RPL_DRIFT_PROBE
	drift_stop();
#endif
	struct rpl_head *h = HEAD;
	active = started = 0;
	if (cur == RPL_REC) {
		if (h->updates)
			emit(pend); /* the last update, with its loader gates */
		flush_run();
		h->length = pos - sizeof(*h);
		last_recorded = 1;
		h->sum = adler(RPL_BUF + 8, pos - 8u);
	} else if (cur == RPL_PLAY) {
		u32 i;
		rpl_mode = RPL_REC; /* back to recording after a playback, with the player's own settings */
		play_pending = 0;
		for (i = 0; i < 6u; i++)
			*arcade_setting(i) = user_arcade[i];
		EE_RAM(u32, FIGHTER_TYPE) = user_fighter[0];
		EE_RAM(u32, FIGHTER_TYPE + 4u) = user_fighter[1];
	}
	cur = RPL_OFF;
}

/* 1 if the buffer holds a complete recording that passes its checksum */
static __attribute__((optimize("Os"))) u32 valid_replay(u32 size)
{
	const struct rpl_head *h = HEAD;
	const u32 legacy = h->version == 2u;
	const u32 header = legacy ? RPL_FORMAT2_SIZE : h->version == 3u ? RPL_FORMAT3_SIZE : sizeof(*h);

	return size >= header && h->magic == RPL_MAGIC && h->head_size == header &&
	       h->length == size - header &&
	       (legacy || ((h->version == 3u || h->version == RPL_FORMAT) && h->target_cursor < TARGET_COUNT)) &&
	       h->sum == adler(RPL_BUF + 8, size - 8u);
}

u32 rpl_valid(void)
{
	const struct rpl_head *h = HEAD;
	return h->head_size <= RPL_MAX && h->length <= RPL_MAX - h->head_size &&
	       valid_replay(h->head_size + h->length);
}
u32 rpl_size(void) { return HEAD->head_size + HEAD->length; }
u8 *rpl_buffer(void) { return RPL_BUF; }
u32 rpl_buffer_max(void) { return RPL_MAX; }

/* After a replay is loaded into the buffer: check it, keep the player's settings, apply the recording's, and play it
 * in the next game. 0 if the file is not a valid replay. */
u32 rpl_play_loaded(u32 size)
{
	const struct rpl_head *h = HEAD;
	u32 i;
	if (size > RPL_MAX || !valid_replay(size))
		return 0;
	for (i = 0; i < 6u; i++) {
		user_arcade[i] = *arcade_setting(i);
		*arcade_setting(i) = h->arcade[i];
	}
	user_fighter[0] = EE_RAM(u32, FIGHTER_TYPE);
	user_fighter[1] = EE_RAM(u32, FIGHTER_TYPE + 4u);
	EE_RAM(u32, FIGHTER_TYPE) = h->fighter[0];
	EE_RAM(u32, FIGHTER_TYPE + 4u) = h->fighter[1];
	last_recorded = 0;
	play_pending = 1;
	rpl_mode = RPL_PLAY;
	return 1;
}

u32 rpl_play_difficulty(void) { return HEAD->difficulty; }

/* the in-game HUD pass (bl_rankbar.c frontend_rank_bar): "REPLAY  <MODE>" while a replay plays, with the game's HUD
 * text writer 0x00111460(text, column, row, attributes) as its PRESS START */
void rpl_hud(void)
{
	static const char *const label[] = {"REPLAY  ARCADE", "REPLAY  ARRANGE", "REPLAY  NOIR"};
	if (cur == RPL_PLAY && started)
		GAME_CALL4(0x00111460u, (u32)label[HEAD->mode & 3u], 8u, 3u, 0xC040C000u);
}

/* Noir's select screen during a playback: the recorded ship (kind * 4 + type) per side */
u32 rpl_play_fighters(u32 *f)
{
	if (!play_pending)
		return 0;
	f[0] = HEAD->fighter[0];
	f[1] = HEAD->fighter[1];
	return 1;
}

/* A playback ends as the pause menu's RETURN MENU does: the pause byte opens the pause-menu call (0x0012E778,
 * rpl_pause_menu), which answers 1 at once; the main loop then leaves the game for the mode's menu. */
static u8 exit_req;
#define PAUSE_BYTE 0x00338F10u /* $gp-28128 */
static void exit_to_menu(void)
{
	exit_req = 1;
	EE_RAM(u8, PAUSE_BYTE) = 1;
}

u32 sel_menu(void);
u32 rpl_pause_menu(void)
{
	if (exit_req) {
		exit_req = 0;
		return 1; /* RETURN MENU */
	}
	return kuro_on ? sel_menu() : GAME_CALL0(0x00128E10u);
}

/* For the end-of-run prompt: 1 if the last game was recorded and long enough to offer; mode (0 Arcade, 1 Arrange,
 * 2 Noir), the stage reached and the final score. */
u32 rpl_offer_info(u32 *mode, u32 *stage, u32 *score)
{
	const struct rpl_head *h = HEAD;
	if (mode) {
		const u32 scene = h->end_tick >> 24; /* scene 2 is stage 1 */
		*mode = h->mode & 0xFFu;
		*stage = scene >= 2u ? scene - 1u : 1u;
		*score = h->end_score;
	}
	return last_recorded && h->updates >= 600u;
}
const u8 *rpl_data(void) { return RPL_BUF; }

/* each pad read (both ports): game start / end; frame counter per update; playback feeds the recorded pads */
#ifdef REPLAY_BUILD
u32 replay_pad(u32 port, u32 buttons);
#endif
u32 rpl_pad(u32 port, u32 buttons)
{
#ifdef REPLAY_BUILD
	return replay_pad(port, buttons); /* research/phase44 harness builds */
#endif
#ifdef RPL_STATELOG
	if (port == 0u) { /* TEST: (vsync count, main state, $gp-27968) at each change, at 0x01EC0000 */
		static u32 last = 0xFFFFFFFFu, n, t;
		const u32 st = EE_RAM(u32, MAIN_STATE) | (u32)EE_RAM(u8, ATTRACT) << 8 | EE_RAM(u32, 0x00338FB0u) << 16;
		t++;
		if (st != last && n < 1000u) {
			EE_RAM(u32, 0x01EC0004u + n * 8u) = t;
			EE_RAM(u32, 0x01EC0008u + n * 8u) = st;
			EE_RAM(u32, 0x01EC0000u) = ++n;
			last = st;
		}
	}
#endif
	if (port == 0u) {
		in_update = 0; /* the pads are read once per frame, before its update (0x00113390) */
		const u32 in_game = EE_RAM(u32, MAIN_STATE) == 5u && !EE_RAM(u8, ATTRACT);
		if (active && !in_game)
			game_end();
		if (!active && in_game)
			active = 1;
	}
	if (!started || port > 1u)
		return buttons;
	if (port == 0u)
		EE_RAM(u32, FRAMES) -= 1u; /* 0x00113390 counts vsyncs; during a game it counts updates */
	if (cur == RPL_PLAY) {
		/* the pad block is rebuilt from the controller every vsync and holds the recording only from an update's
		 * start to the next rebuild: Start that the recording does not have is the player's */
		if (port == 0u && (buttons & PAD_START) && !(next[0] & PAD_START) && !(prev_applied & PAD_START))
			exit_to_menu(); /* START on the controller ends the playback (the pad block holds the recording) */
		return last_raw[port];
	}
	return buttons;
}

#ifdef RPL_TRACE
volatile u32 rpl_test_finish; /* PCSX2 fixture: finish a recording before the next update */
#endif

/* the start of each game update (game_start.c, after its start-of-game reset) */
void rpl_update(void)
{
	if (!active)
		return;
#ifdef RPL_TRACE
	if (started && cur == RPL_REC && rpl_test_finish) {
		rpl_test_finish = 0;
		game_end();
		EE_RAM(u32, 0x00338B30u) = 3u; /* normal game-over teardown at 0x0012E898 */
		return;
	}
#endif
	if (!started) {
		if (stage_one_start()) {
			if (EE_RAM(u8, SCENE) != 2u)
				return;
			void game_start_reset(void); /* game_start.c: shots, bullets, items, XTC, boss cancel */
			game_start_reset();
		}
		game_start();
	} else {
		EE_RAM(u32, FRAMES) += 1u;
	}
#ifdef RPL_HP_TRACE
	{ /* TEST: every enemy slot's (flags >> 16 | hp) per update: recording at 0x01650000 (1,800 updates); playback compares
	   * and keeps its first difference (update, slot, recorded, played, the slot's 0xB4 bytes) at 0x016F0000 */
		const u32 u = cur == RPL_REC ? HEAD->updates : rpl_stat[0];
		u32 k;
		if (u < 1800u && (cur == RPL_REC || cur == RPL_PLAY)) {
			u16 *d = (u16 *)(0x01650000u + u * 384u);
			for (k = 0; k < 192u; k++) {
				const u32 e = 0x0045A840u + k * 0xB4u;
				const u16 v = (u16)(EE_RAM(u32, e) & 0x80000000u ? 0x8000u | (EE_RAM(u32, e + 0x3Cu) & 0x7FFFu) : 0u);
				if (cur == RPL_REC) {
					d[k] = v;
				} else if (d[k] != v && !EE_RAM(u32, 0x016F0000u)) {
					u32 *o = (u32 *)0x016F0000u, j;
					o[0] = 1u; o[1] = u; o[2] = k; o[3] = d[k] | (u32)v << 16;
					for (j = 0; j < 0xB4u / 4u; j++)
						o[4 + j] = EE_RAM(u32, e + 4u * j);
				}
			}
		}
	}
#endif
#ifdef RPL_POOL_AT
	{ /* TEST: the whole enemy pool at the start of updates RPL_POOL_AT .. +7, at 0x01650000 (record) / 0x016A0000 */
		const u32 u = cur == RPL_REC ? HEAD->updates : rpl_stat[0];
		if ((cur == RPL_REC || cur == RPL_PLAY) && u >= RPL_POOL_AT && u < RPL_POOL_AT + 8u) {
			u32 *d = (u32 *)((cur == RPL_REC ? 0x01650000u : 0x016A0000u) + (u - RPL_POOL_AT) * 192u * 0xB4u);
			const u32 *e = (const u32 *)0x0045A840u;
			u32 k;
			for (k = 0; k < 192u * 0xB4u / 4u; k++)
				d[k] = e[k];
		}
	}
#endif
#if defined(RPL_TEST) || defined(RPL_TRACE)
#ifndef RPL_CK_EVERY
#define RPL_CK_EVERY 30u
#endif
	{ /* TEST: checkpoints (update, score, seed, scene << 24 | tick) every RPL_CK_EVERY updates; record at 0x01EA0000,
	   * play 0x01EB0000 */
		const u32 u = cur == RPL_REC ? HEAD->updates : rpl_stat[0];
		if ((cur == RPL_REC || cur == RPL_PLAY) && u % RPL_CK_EVERY == 0 && u / RPL_CK_EVERY < 4000u) {
			u32 *c = (u32 *)(cur == RPL_REC ? 0x01EA0000u : 0x01EB0000u) + (u / RPL_CK_EVERY) * 4u;
			c[0] = u;
			c[1] = EE_RAM(u32, PS2_PLAYER_BASE + PS2_PLAYER_SCORE);
			c[2] = EE_RAM(u32, SEED);
			c[3] = (u32)EE_RAM(u8, SCENE) << 24 | (EE_RAM(u32, TICK) & 0xFFFFFFu);
		}
	}
#endif
	if (cur == RPL_REC) {
		const u32 rank = EE_RAM(u32, RANK);
		/* the state at the start of the last update recorded, checked at the same point of a playback */
		HEAD->end_score = EE_RAM(u32, PS2_PLAYER_BASE + PS2_PLAYER_SCORE);
		HEAD->end_seed = EE_RAM(u32, SEED);
		HEAD->end_tick = (u32)EE_RAM(u8, SCENE) << 24 | (EE_RAM(u32, TICK) & 0xFFFFFFu);
		if (HEAD->updates)
			emit(pend); /* the previous update, now that its loader gates are known */
		fields(pend, rank - rank_prev);
#ifdef RPL_DRIFT_PROBE
		drift_sample(0u, HEAD->updates, pend, FIELDS);
#endif
		rank_prev = rank;
		HEAD->updates++;
		in_update = 1;
		return;
	}
	if (cur != RPL_PLAY || !play_left)
		return;
	play_left--;
	rpl_stat[0]++;
	if (!play_left) {
		const struct rpl_head *h = HEAD;
		rpl_stat[1] = (EE_RAM(u32, PS2_PLAYER_BASE + PS2_PLAYER_SCORE) != h->end_score) |
			      (EE_RAM(u32, SEED) != h->end_seed) << 1 |
			      (((u32)EE_RAM(u8, SCENE) << 24 | (EE_RAM(u32, TICK) & 0xFFFFFFu)) != h->end_tick) << 2;
	}
#ifdef RPL_DRIFT_PROBE
	drift_sample(1u, rpl_stat[0] - 1u, next, FIELDS);
#endif
	apply(next);
	ev_nx ^= 1u; /* this update's gates; decode the coming update's into the other buffer */
	gate_i = 0;
	in_update = 1;
	if (play_left)
		decode();
	else
		exit_to_menu(); /* the recording is over */
}

/* Loader gates (research/phase47/LOADER_GATES.md). The disc and texture loaders run beside the game, so how many updates
 * a load takes varies from run to run, and a few game decisions read the loader:
 *   G_RES    0x00135D70(type): are an enemy type's textures resident? (every enemy factory; a miss queues them)
 *   G_BG     script FF08 0x00114E20: are the background layers' textures resident?
 *   G_QUEUE  script FF27 0x00114820: is the texture queue empty?
 *   G_QUEUES script FF28 0x001147E0: are the disc and texture queues empty?
 *   G_REQ    script FF0C 0x00114B40 / FF10 0x00114B20: queue a texture group (0 when the loader has no room)
 * A script command that returns 0 runs again at the next update; a factory that gets 0 from G_RES spawns nothing.
 * Recording keeps every answer per update. Playback gives the game the recorded answers: a check that comes true
 * early answers 0 until its recorded update; before an update whose recorded check came true, rpl_may_update holds
 * the game on the native draw-only path (0x0012E1EC: the loaders run, the input and the stage clock wait) until the
 * check passes here too. */
enum { G_RES, G_BG, G_QUEUE, G_QUEUES, G_REQ, G_REQ2 };
#define GATE_HOLD_MAX 600u /* draw-only passes before one update gives up and plays on (10 seconds) */
u32 rpl_gate_stat[5];      /* plays: holds, forced passes, forced misses, unmatched checks, longest hold */
static u32 gate_holds;
u32 rpl_res_orig(u32 type);

static u32 gate_real(u32 kind, u32 arg)
{
	switch (kind) {
	case G_RES:
		return rpl_res_orig(arg) != 0;
	case G_BG:
		return GAME_CALL0(0x00114E20u) != 0;
	case G_QUEUE:
		return GAME_CALL0(0x00114820u) != 0;
	case G_QUEUES:
		return GAME_CALL0(0x001147E0u) != 0;
	case G_REQ:
		return GAME_CALL0(0x00114B40u) != 0;
	default:
		return GAME_CALL0(0x00114B20u) != 0;
	}
}

static u32 gate(u32 kind, u32 arg)
{
	const u32 real = gate_real(kind, arg);
	const u32 key = kind << 12 | (arg & 0x7FFu) << 1;
#ifdef RPL_TRACE
	{ /* TEST: every check (update, key | real, in_update << 1 | started, cur) at 0x01EC0000 (record) / 0x01EC8000 */
		static u32 n[2];
		const u32 side = cur == RPL_PLAY;
		if (cur != RPL_OFF && n[side] < 2047u) {
			u32 *t = (u32 *)(side ? 0x01EC8010u : 0x01EC0010u) + n[side] * 4u;
			t[0] = side ? rpl_stat[0] : HEAD->updates;
			t[1] = key | real;
			t[2] = (u32)in_update << 1 | started;
			t[3] = side ? gate_i : gate_cnt[0];
			EE_RAM(u32, side ? 0x01EC8000u : 0x01EC0000u) = ++n[side];
		}
	}
#endif
	/* Checks between updates count too: while the script waits on the loaders, the main state machine runs 0x0013BFA0
	 * before the game loop each frame, and once the queues empty it runs the stage script there. They belong to the
	 * previous update (its list is written at the next update; playback still has it until the next update). */
	if (!started)
		return real;
	if (cur == RPL_REC) {
		if (gate_cnt[0] < 255u)
			gate_ev[0][gate_cnt[0]++] = (u16)(key | real);
		else
			rpl_gate_stat[3]++;
		return real;
	}
	if (cur != RPL_PLAY || !gates_on)
		return real;
	if (gate_holds && kind <= G_QUEUES)
		return 0; /* held: the recording has not reached this update's checks yet */
	{
		const u32 n = gate_cnt[ev_nx ^ 1u];
		const u16 *ev = gate_ev[ev_nx ^ 1u];
		if (gate_i < n && (ev[gate_i] & ~1u) == key) {
			const u32 want = ev[gate_i++] & 1u;
			if (want != real)
				rpl_gate_stat[want ? 1 : 2]++;
			return want;
		}
	}
	rpl_gate_stat[3]++;
	return real;
}

u32 rpl_gate_res(u32 type) { return gate(G_RES, type & 0xFFFFu); }
u32 rpl_gate_bg(void) { return gate(G_BG, 0); }
u32 rpl_gate_queue(void) { return gate(G_QUEUE, 0); }
u32 rpl_gate_queues(void) { return gate(G_QUEUES, 0); }
u32 rpl_gate_req(void) { return gate(G_REQ, 0); }
u32 rpl_gate_req2(void) { return gate(G_REQ2, 0); }

/* game_start.c, before each game update: 0 runs a draw-only pass instead (the update and its input wait) */
u32 rpl_may_update(void)
{
	u32 i;
	if (started && cur == RPL_PLAY && gates_on && play_left) {
		const u32 n = gate_cnt[ev_nx];
		const u16 *ev = gate_ev[ev_nx];
		for (i = 0; i < n; i++) {
			const u32 kind = ev[i] >> 12;
			/* the queue requests move the script cursor and are not checked ahead */
			if ((ev[i] & 1u) && kind <= G_QUEUES && !gate_real(kind, ev[i] >> 1 & 0x7FFu)) {
				if (gate_holds >= GATE_HOLD_MAX)
					break;
				gate_holds++;
				rpl_gate_stat[0]++;
				if (gate_holds > rpl_gate_stat[4])
					rpl_gate_stat[4] = gate_holds;
				return 0;
			}
		}
	}
	gate_holds = 0;
	return 1;
}

/* The gates' entries: the game's callers keep 128-bit s-registers; a0 passes through */
#define GATE_ENTRY(name, fn) \
	".globl " name "\n" name ":\n" \
	"	addiu $sp,$sp,-0xB0\n	sq $ra,0x00($sp)\n	sq $s0,0x10($sp)\n	sq $s1,0x20($sp)\n" \
	"	sq $s2,0x30($sp)\n	sq $s3,0x40($sp)\n	sq $s4,0x50($sp)\n	sq $s5,0x60($sp)\n" \
	"	sq $s6,0x70($sp)\n	sq $s7,0x80($sp)\n	sq $fp,0x90($sp)\n	jal " fn "\n	sq $gp,0xA0($sp)\n" \
	"	lq $gp,0xA0($sp)\n	lq $fp,0x90($sp)\n	lq $s7,0x80($sp)\n	lq $s6,0x70($sp)\n" \
	"	lq $s5,0x60($sp)\n	lq $s4,0x50($sp)\n	lq $s3,0x40($sp)\n	lq $s2,0x30($sp)\n" \
	"	lq $s1,0x20($sp)\n	lq $s0,0x10($sp)\n	lq $ra,0x00($sp)\n	jr $ra\n	addiu $sp,$sp,0xB0\n"
__asm__(
	".set push\n.set noreorder\n.set noat\n"
	/* 0x00135D70's first word is `j rpl_res_entry` (its second, `dsll32 v0,a0,16`, runs in the delay slot) */
	GATE_ENTRY("rpl_res_entry", "rpl_gate_res")
	GATE_ENTRY("rpl_gate_bg_entry", "rpl_gate_bg")
	GATE_ENTRY("rpl_gate_queue_entry", "rpl_gate_queue")
	GATE_ENTRY("rpl_gate_queues_entry", "rpl_gate_queues")
	GATE_ENTRY("rpl_gate_req_entry", "rpl_gate_req")
	GATE_ENTRY("rpl_gate_req2_entry", "rpl_gate_req2")
	/* the original 0x00135D70: its two first words, then the rest */
	".globl rpl_res_orig\n"
	"rpl_res_orig:\n"
	"	addiu $sp,$sp,-32\n"
	"	j 0x00135D78\n"
	"	dsll32 $v0,$a0,16\n"
	".set pop\n");

#ifdef RPL_RNG_TRACE
/* TEST: every RNG advance in a game (update or ~0 before the start, caller, seed, frames) at 0x01ED0000 (recording)
 * / 0x01EE0000 (playback); 0x00111050 `jal 0x00160310` -> rpl_rng_entry */
void rpl_rng_log(u32 ra)
{
	static u32 n[2];
	const u32 side = rpl_mode == RPL_PLAY || cur == RPL_PLAY;
	if (!active || n[side] >= 4095u)
		return;
	u32 *t = (u32 *)(side ? 0x01EE0010u : 0x01ED0010u) + n[side] * 4u;
	t[0] = !started ? 0xFFFFFFFFu : side ? rpl_stat[0] : HEAD->updates;
	t[1] = ra;
	t[2] = EE_RAM(u32, SEED);
	t[3] = EE_RAM(u32, FRAMES);
	EE_RAM(u32, side ? 0x01EE0000u : 0x01ED0000u) = ++n[side];
}
__asm__(
	".set push\n.set noreorder\n.set noat\n"
	".globl rpl_rng_entry\n"
	"rpl_rng_entry:\n"
	"	addiu $sp,$sp,-0xE0\n	sq $ra,0x00($sp)\n	sq $s0,0x10($sp)\n	sq $s1,0x20($sp)\n	sq $s2,0x30($sp)\n"
	"	sq $s3,0x40($sp)\n	sq $s4,0x50($sp)\n	sq $s5,0x60($sp)\n	sq $s6,0x70($sp)\n	sq $s7,0x80($sp)\n"
	"	sq $fp,0x90($sp)\n	sq $gp,0xA0($sp)\n	sq $a0,0xB0($sp)\n	sq $a1,0xC0($sp)\n"
	"	jal rpl_rng_log\n	ld $a0,0xE0($sp)\n"
	"	lq $a1,0xC0($sp)\n	lq $a0,0xB0($sp)\n	lq $gp,0xA0($sp)\n	lq $fp,0x90($sp)\n	lq $s7,0x80($sp)\n"
	"	lq $s6,0x70($sp)\n	lq $s5,0x60($sp)\n	lq $s4,0x50($sp)\n	lq $s3,0x40($sp)\n	lq $s2,0x30($sp)\n"
	"	lq $s1,0x20($sp)\n	lq $s0,0x10($sp)\n	lq $ra,0x00($sp)\n"
	"	j 0x00160310\n	addiu $sp,$sp,0xE0\n"
	".set pop\n");
#endif

/* Replaces `jal 0x0010DDD0` at 0x00112B1C / 0x00112B28 (a0 = port, set in the delay slot): calls the original, then
 * rpl_pad(port, buttons), and returns its value; callee-saved registers kept with 128-bit sq. */
__asm__(
	".set push\n.set noreorder\n.set noat\n"
	".globl rpl_pad_entry\n"
	"rpl_pad_entry:\n"
	"	addiu $sp,$sp,-0xC0\n"
	"	sq $ra,0x00($sp)\n"
	"	sq $s0,0x10($sp)\n"
	"	sq $s1,0x20($sp)\n"
	"	sq $s2,0x30($sp)\n"
	"	sq $s3,0x40($sp)\n"
	"	sq $s4,0x50($sp)\n"
	"	sq $s5,0x60($sp)\n"
	"	sq $s6,0x70($sp)\n"
	"	sq $s7,0x80($sp)\n"
	"	sq $fp,0x90($sp)\n"
	"	sq $gp,0xA0($sp)\n"
	"	jal 0x0010DDD0\n"
	"	sw $a0,0xB0($sp)\n"
	"	lw $a0,0xB0($sp)\n"
	"	jal rpl_pad\n"
	"	move $a1,$v0\n"
	"	lq $gp,0xA0($sp)\n"
	"	lq $fp,0x90($sp)\n"
	"	lq $s7,0x80($sp)\n"
	"	lq $s6,0x70($sp)\n"
	"	lq $s5,0x60($sp)\n"
	"	lq $s4,0x50($sp)\n"
	"	lq $s3,0x40($sp)\n"
	"	lq $s2,0x30($sp)\n"
	"	lq $s1,0x20($sp)\n"
	"	lq $s0,0x10($sp)\n"
	"	lq $ra,0x00($sp)\n"
	"	jr $ra\n"
	"	addiu $sp,$sp,0xC0\n"
	".set pop\n");
