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
#define RPL_FORMAT 3u           /* format 2 has the same prefix and no cursor or initial stage tick */
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
};
#define RPL_FORMAT2_SIZE __builtin_offsetof(struct rpl_head, target_cursor)

enum { RPL_OFF, RPL_REC, RPL_PLAY };
u32 rpl_mode = RPL_REC;      /* what the next game does */
static u32 cur;              /* what this game does (latched at its start) */
static u32 last_recorded;    /* the buffer holds a finished recording (not a playback) */
extern u32 kuro_on;
static u8 active, started;
static u32 pos, run, play_left;
static u16 prev[FIELDS], next[FIELDS], last_raw[2]; /* playback: next = the coming update, decoded ahead */
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
static void decode(void)
{
	u32 i, mask;
	if (run) {
		run--;
	} else {
		const u8 op = RPL_BUF[pos++];
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

static u32 adler(const u8 *p, u32 n)
{
	u32 a = 1, b = 0;
	while (n--) {
		a = (a + *p++) % 65521u;
		b = (b + a) % 65521u;
	}
	return b << 16 | a;
}

static u32 stage_one_start(void)
{
	/* Noir's opening and select can consume different numbers of updates.
	 * Normal format-3 runs start on the first Stage 1 update. Format 2
	 * retains its original input indexing. Practice can start elsewhere. */
	if (rpl_mode == RPL_PLAY)
		return HEAD->version == RPL_FORMAT && HEAD->mode == 2u;
	return kuro_on && !EE_RAM(u32, 0x00338FA4u);
}

static void game_start(void)
{
	struct rpl_head *h = HEAD;
	u32 i;
	started = 1;
	cur = rpl_mode;
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
	} else if (cur == RPL_PLAY) {
		EE_RAM(u32, SEED) = h->seed0;
		EE_RAM(u32, FRAMES) = h->frames0;
		/* Format 2 lacks a cursor. Use the cold-start value as a stable fallback. */
		EE_RAM(u16, TARGET_CURSOR) = h->version == RPL_FORMAT ? (u16)h->target_cursor : 0u;
		if (h->version == RPL_FORMAT && h->mode == 2u)
			EE_RAM(u32, TICK) = h->tick0;
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
	const u32 header = legacy ? RPL_FORMAT2_SIZE : sizeof(*h);

	return size >= header && h->magic == RPL_MAGIC && h->head_size == header &&
	       h->length == size - header &&
	       (legacy || (h->version == RPL_FORMAT && h->target_cursor < TARGET_COUNT)) &&
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
	u16 f[FIELDS];
	u32 i, mask;
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
			void xtc_reset(void);
			void bl_enemy_reset(void);
			xtc_reset();
			bl_enemy_reset();
		}
		game_start();
	} else {
		EE_RAM(u32, FRAMES) += 1u;
	}
#if defined(RPL_TEST) || defined(RPL_TRACE)
	{ /* TEST: checkpoints (update, score, seed, scene << 24 | tick) every 30 updates; record at 0x01EA0000, play 0x01EB0000 */
		const u32 u = cur == RPL_REC ? HEAD->updates : rpl_stat[0];
		if ((cur == RPL_REC || cur == RPL_PLAY) && u % 30u == 0 && u / 30u < 1000u) {
			u32 *c = (u32 *)(cur == RPL_REC ? 0x01EA0000u : 0x01EB0000u) + (u / 30u) * 4u;
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
		fields(f, rank - rank_prev);
#ifdef RPL_DRIFT_PROBE
		drift_sample(0u, HEAD->updates, f, FIELDS);
#endif
		rank_prev = rank;
		for (i = 0, mask = 0; i < FIELDS; i++)
			if (f[i] != prev[i])
				mask |= 1u << i;
		if (!mask && HEAD->updates) {
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
		HEAD->updates++;
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
	if (play_left)
		decode();
	else
		exit_to_menu(); /* the recording is over */
}

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
