/* TEST BUILDS ONLY (--define BL_SPAWN_LOG): PS2 enemy-spawn logger for stage comparisons with BL (MAME).
 *
 * Options: BL_SPAWN_RANK (lock rank), BL_LOCK_SHOT (lock shot level), BL_LOG_STAGE (log only that stage),
 * BL_BOSS_TYPE (boss sampler type), BL_NOSHOT (refill BL_BOSS_TYPE parts' HP every frame),
 * BL_CORE_STATE / BL_CORE_FLAGS / BL_CORE_TURRET (what the stage-1 boss sampler records).
 * Every logic frame (called from xtc_frame): keeps P1 invincible and records each newly alive enemy part of
 * the PS2 pool 0x0045A840 (192 x 0xB4; +00 flags bit 31 alive, +04 type, +08 subtype, +24/+28 x/y 16.16,
 * +3C hp, +40 score) into a rolling log at SPAWN_LOG. Read the retained records from a savestate.
 */
#include "ibara_ps2.h"

/* Diagnostic bake only: compare the rose timer under the arcade rank input.
 * The test definition supplies the recorded arcade difficulty byte.
 */
#ifdef BL_ROSE_TIMER_TEST
_Static_assert(BL_ROSE_TIMER_TEST >= 0 && BL_ROSE_TIMER_TEST <= 3, "rose test difficulty must be 0..3");

u32 bl_test_rose_timer(u32 part, u32 scale, u32 base)
{
	if (!(EE_RAM(u32, part) & 0x100u))
		return 0;
	const u32 stage = EE_RAM(u8, 0x00338E9Cu);
	const u32 rank = EE_RAM(u32, PS2_RANK_INV);
	const u32 bias = stage * (BL_ROSE_TIMER_TEST + 1u) * 0x40000u;
	const u32 rank_byte = rank > bias ? (rank - bias) >> 16 : 0;
	const u32 limit = base + (rank_byte * scale >> 8);
	const u8 tick = EE_RAM(u8, part + 0x9Bu) + 1u;
	EE_RAM(u8, part + 0x9Bu) = tick < limit ? tick : 0;
	return tick >= limit;
}
#endif

#ifdef BL_SPAWN_LOG
#define EN_BASE 0x0045A840u
#define EN_STRIDE 0xB4u
#define EN_COUNT 192u
#define SPAWN_LOG 0x01F20000u
#define SPAWN_MAX 2600u
#define LOG_STAGE 0x00338E9Cu
#define LOG_STAGE_TICK 0x00338EA0u
#define LOG_RING_MAGIC 0x31474E52u /* RNG1 */

struct log_header {
	volatile u32 total; /* monotonic sequence, including records overwritten */
	u32 magic, capacity, reserved;
};

static void start_ring(struct log_header *ring, u32 capacity)
{
	ring->total = 0;
	ring->magic = LOG_RING_MAGIC;
	ring->capacity = capacity;
	ring->reserved = 0;
}

struct spawn_rec {
	u32 frame;
	u16 slot, hp;
	u32 type, subtype, score;
	s16 x, y;
	u32 stage_tick;
	u8 stage;
};

#define BULLET_LOG 0x01F35000u
#define BULLET_MAX 7000u
/* BL_COUNTS retains per-type and per-bin totals alongside the rolling records. */
#define COUNT_LOG 0x01F5C000u
struct bullet_rec {
	u32 frame;
	u16 type;
	u8 slot, stage;
	s16 x, y;
	s16 dx, dy; /* 8.8 pixels per frame, averaged over the bullet's first 6 frames (as the MAME logger) */
	u32 stage_tick;
};
static u32 bl_alive_mask[8];
static u32 bl_pending[256]; /* one-based record sequence awaiting its velocity */
static u8 bl_age[256];
static s32 bl_x0[256], bl_y0[256]; /* full 16.16 start position */

/* Boss sampler: every 4 frames, each alive part of type BL_BOSS_TYPE (default 5 = stage-1 boss) with subtype < 3
 * or score >= 50000: HP, position, mode byte (+0x9A) and step byte (+0xA6). */
#ifndef BL_BOSS_TYPE
#define BL_BOSS_TYPE 5u
#endif
#define CORE_LOG 0x01F60000u
#ifdef BL_CORE_FLAGS
#define CORE_MAX 16000u
#else
#define CORE_MAX 8000u
#endif
struct core_rec {
	u32 frame;
	u16 slot, hp;
	u32 subtype;
	s16 x, y;
	u8 mode, step, stage;
	u32 stage_tick;
};

/* Part-record tables seen (+0x10 of each new part): count, then (type, table) pairs; read by
 * tools/stage_compare/diff_part_tables.py to compare HP/score records with BL's. */
#define TABLE_LOG 0x01FC0000u
#define TABLE_MAX 512u

_Static_assert(sizeof(struct log_header) == 16, "logger header layout");
_Static_assert(sizeof(struct spawn_rec) == 32, "spawn record layout");
_Static_assert(sizeof(struct bullet_rec) == 20, "bullet record layout");
_Static_assert(sizeof(struct core_rec) == 24, "boss record layout");
_Static_assert(SPAWN_LOG + 16 + SPAWN_MAX * sizeof(struct spawn_rec) <= BULLET_LOG, "spawn log bounds");
_Static_assert(BULLET_LOG + 16 + BULLET_MAX * sizeof(struct bullet_rec) <= COUNT_LOG, "bullet log bounds");
_Static_assert(CORE_LOG + 16 + CORE_MAX * sizeof(struct core_rec) <= TABLE_LOG, "boss log bounds");

static u32 sl_frame, sl_first, sl_started;
static u8 sl_stage;

static void table_seen(u32 type, u32 table)
{
	volatile u32 *n = (volatile u32 *)TABLE_LOG;
	volatile u32 *e = (volatile u32 *)(TABLE_LOG + 16);
	u32 i;
	for (i = 0; i < *n; i++)
		if (e[2 * i] == type && e[2 * i + 1] == table)
			return;
	if (*n < TABLE_MAX) {
		e[2 * *n] = type;
		e[2 * *n + 1] = table;
		(*n)++;
	}
}
#ifdef BL_RATE_TEST
/* TEST BUILDS ONLY (with BL_TEST_ALL_WEAPONS): from game frame 2400, change weapon every 1200 frames in BL's order
 * (current weapon +0x270 and the three pods' shot kinds +0x26D..+0x26F = weapon x 2, as the change routine 0x00139850) and count
 * new shots of pool 0x0044C9C0 per (weapon, type) over frames 200..1199 of each segment: u32 [7][16] at 0x01FE0000
 * (research/phase16, compared with BL's bl_pod_rate.lua). */
static u32 rt_frame;
static u8 rt_alive[160];
static void rate_test_frame(void)
{
	static const u8 next_weapon[7] = {1, 4, 0, 5, 3, 6, 2};
	const u32 rec = 0x0044C380u;
	u32 seg, k;
	rt_frame++;
	if (rt_frame < 2400u || EE_RAM(u8, rec + 0x26D) == 0xFFu)
		return;
	seg = (rt_frame - 2400u) % 1200u;
	if (seg == 0) {
		const u8 w = next_weapon[EE_RAM(u8, rec + 0x270) % 7u];
		EE_RAM(u8, rec + 0x270) = w;
		EE_RAM(u8, rec + 0x26D) = (u8)(2u * w); /* shot kind = weapon x 2 (0x00139968), as BL */
		EE_RAM(u8, rec + 0x26E) = (u8)(2u * w);
		EE_RAM(u8, rec + 0x26F) = (u8)(2u * w);
		for (k = 0; k < 3u; k++) { /* and each pod record, as 0x00139938 (player 1: side 0) */
			const u32 pod = 0x0044C8A0u + 0x30u * k;
			EE_RAM(u32, pod + 4) = 2u * w;
			EE_RAM(u32, pod + 16) = 2u * w;
			EE_RAM(u32, pod + 8) = 0;
			EE_RAM(u32, pod + 12) = 0;
			EE_RAM(u8, pod + 42) = 0;
			EE_RAM(u8, pod + 43) = 0;
		}
	}
	for (k = 0; k < 160u; k++) {
		const u32 a = 0x0044C9C0u + 0x34u * k;
		const u8 on = (EE_RAM(u32, a) >> 30) == 3u;
		if (on && !rt_alive[k] && seg >= 200u && rt_frame < 2400u + 1200u * 8u)
			EE_RAM(u32, 0x01FE0000u + 4u * (16u * (EE_RAM(u8, rec + 0x270) % 7u) + (EE_RAM(u32, a + 4) & 15u)))++;
		if (on && seg >= 200u && rt_frame < 2400u + 1200u * 8u) /* alive-shot frames: u32 [7][16] at 0x01FE0200 */
			EE_RAM(u32, 0x01FE0200u + 4u * (16u * (EE_RAM(u8, rec + 0x270) % 7u) + (EE_RAM(u32, a + 4) & 15u)))++;
		rt_alive[k] = on;
	}
}
#endif
#ifdef BL_TRACE_WEAPON
/* TEST BUILDS ONLY (with BL_TEST_ALL_WEAPONS): at game frame 2400 switch to weapon BL_TRACE_WEAPON (as BL_RATE_TEST),
 * then from frame 3600 trace one pod shot of type BL_TRACE_TYPE per frame: records of 14 words
 * (frame, +0x00..+0x30) at 0x01FD0010 (count at 0x01FD0000; the BL_SHOT_LOG area), 1000 frames. Slot reuse continues the trace (as bl_trace.lua). */
static u32 tr_frame, tr_slot = 0xFFFFFFFFu;
static void trace_frame(void)
{
	const u32 rec = 0x0044C380u;
	u32 k;
	tr_frame++;
	if (tr_frame == 2400u && EE_RAM(u8, rec + 0x26D) != 0xFFu) {
		const u8 w = BL_TRACE_WEAPON;
		EE_RAM(u8, rec + 0x270) = w;
		for (k = 0; k < 3u; k++) {
			const u32 pod = 0x0044C8A0u + 0x30u * k;
			EE_RAM(u8, rec + 0x26D + k) = (u8)(2u * w);
			EE_RAM(u32, pod + 4) = 2u * w;
			EE_RAM(u32, pod + 16) = 2u * w;
			EE_RAM(u32, pod + 8) = 0;
			EE_RAM(u32, pod + 12) = 0;
			EE_RAM(u8, pod + 42) = 0;
			EE_RAM(u8, pod + 43) = 0;
		}
	}
	if (tr_frame < 3600u || tr_frame >= 4600u)
		return;
	if (tr_slot == 0xFFFFFFFFu) {
		for (k = 0; k < 48u; k++) {
			const u32 a = 0x0044D6C0u + 0x34u * k;
			if ((EE_RAM(u32, a) >> 30) == 3u && (EE_RAM(u32, a + 4) & 0xFFu) == BL_TRACE_TYPE) {
				tr_slot = k;
				break;
			}
		}
	}
	if (tr_slot != 0xFFFFFFFFu) {
		const u32 a = 0x0044D6C0u + 0x34u * tr_slot;
		volatile u32 *n = (volatile u32 *)0x01FD0000u;
		volatile u32 *e = (volatile u32 *)(0x01FD0010u + 56u * *n);
		e[0] = tr_frame;
		for (k = 0; k < 13u; k++)
			e[1 + k] = EE_RAM(u32, a + 4u * k);
		(*n)++;
	}
}
#endif
#ifdef BL_BCOUNT
/* TEST BUILDS ONLY: per game frame, enemy bullets alive (can hit, not a segment) and boss parts alive (type
 * BL_BOSS_TYPE, default 5): records (bullets, boss parts, boss gauge state $gp-29076, gauge HP $gp-29072) of 4 x u16 at 0x01FD0010, count at
 * 0x01FD0000 (the BL_SHOT_LOG area), 12000 frames. */
#ifndef BL_BOSS_TYPE
#define BL_BOSS_TYPE 5u
#endif
static void bcount_frame(void)
{
	volatile u32 *n = (volatile u32 *)0x01FD0000u;
	u32 i, b = 0, bp = 0;
	if (*n >= 12000u)
		return;
	for (i = 0; i < 256u; i++)
		if ((EE_RAM(u32, PS2_BULLETS_BASE + i * PS2_BULLET_STRIDE) & (BULLET_CAN_HIT | BULLET_SEGMENT)) == BULLET_CAN_HIT)
			b++;
	for (i = 0; i < EN_COUNT; i++) {
		const u32 a = EN_BASE + i * EN_STRIDE;
		if ((EE_RAM(u32, a) & 0x80000000u) && EE_RAM(u32, a + 4) == BL_BOSS_TYPE)
			bp++;
	}
	EE_RAM(u16, 0x01FD0010u + 8u * *n) = (u16)b;
	EE_RAM(u16, 0x01FD0012u + 8u * *n) = (u16)bp;
	EE_RAM(u16, 0x01FD0014u + 8u * *n) = (u16)EE_RAM(u32, 0x00338B5Cu); /* boss gauge state $gp-29076 */
	EE_RAM(u16, 0x01FD0016u + 8u * *n) = (u16)EE_RAM(u32, 0x00338B60u); /* boss gauge HP $gp-29072 */
	(*n)++;
}
#endif
#ifdef BL_MIDLOG
/* TEST BUILDS ONLY: "dying" periods of big enemy parts (alive, HP 0, score >= 1000) and boss-gauge changes:
 * records (frame, type | subtype << 16, slot | kind << 8 (0 start, 1 end, 2 gauge), flags or gauge state/HP)
 * of 4 x u32 at 0x01FD0010, count at 0x01FD0000. */
static u8 ml_dying[EN_COUNT];
static u32 ml_frame, ml_gauge;
static void ml_put(u32 a, u32 b, u32 c, u32 d)
{
	volatile u32 *n = (volatile u32 *)0x01FD0000u;
	if (*n >= 4000u)
		return;
	EE_RAM(u32, 0x01FD0010u + 16u * *n) = a;
	EE_RAM(u32, 0x01FD0014u + 16u * *n) = b;
	EE_RAM(u32, 0x01FD0018u + 16u * *n) = c;
	EE_RAM(u32, 0x01FD001Cu + 16u * *n) = d;
	(*n)++;
}
static u16 ml_hp[EN_COUNT];
static void midlog_frame(void)
{
	u32 i, g;
	if (!ml_frame)
		EE_RAM(u32, 0x01FD0000u) = 0;
	ml_frame++;
	for (i = 0; i < EN_COUNT; i++) { /* kills: HP > 0 last frame, 0 now (alive or freed), score >= 1000 */
		const u32 a = EN_BASE + i * EN_STRIDE;
		const u32 fl = EE_RAM(u32, a);
		const u16 hp = EE_RAM(u16, a + 0x3C);
		if (ml_hp[i] && hp == 0 && EE_RAM(u32, a + 0x40) >= 1000u)
			ml_put(ml_frame, EE_RAM(u32, a + 4) | EE_RAM(u32, a + 8) << 16, i | (fl & 0x80000000u ? 0u : 1u) << 8,
			       EE_RAM(u32, a + 0x40));
		ml_hp[i] = (fl & 0x80000000u) ? hp : 0;
		(void)ml_dying;
	}
	{ /* the cancel hook arming (bc_left 16): kind 3, enemy bullets alive this frame */
		extern u32 bc_left __attribute__((weak)); /* absent from builds without bl_enemy.c */
		static u32 last_left;
		if (&bc_left && bc_left == 15u && last_left != 16u && last_left != 15u) {
			u32 b = 0;
			for (g = 0; g < 256u; g++)
				if (EE_RAM(u32, PS2_BULLETS_BASE + g * PS2_BULLET_STRIDE) & BULLET_CAN_HIT)
					b++;
			ml_put(ml_frame, EE_RAM(u8, 0x00338E9Cu), 3u << 8, b);
		}
		last_left = &bc_left ? bc_left : 0u;
	}
	g = EE_RAM(u32, 0x00338B5Cu) << 16 | (EE_RAM(u32, 0x00338B60u) ? 1u : 0u);
	if (g != ml_gauge)
		ml_put(ml_frame, 0, 2u << 8, EE_RAM(u32, 0x00338B5Cu) << 16 | (EE_RAM(u32, 0x00338B60u) & 0xFFFFu));
	ml_gauge = g;
}
#endif
#ifdef BL_BOMBLOG
/* TEST BUILDS ONLY: P1 bombs. Keeps at least one bomb; every frame P1 is alive, records (alive P1 projectile
 * records per type 0..14, 15 = other) as 16 x u8, enemy bullets (u8) and the bomb stock (u8): 18-byte rows at
 * 0x01FD0010, up to 3000, row count at 0x01FD0000. */
static void bomblog_frame(void)
{
	volatile u32 *n = (volatile u32 *)0x01FD0000u;
	const u32 rec = PS2_PLAYER_BASE;
	u32 i, b;
	u8 *row;
	if (!(EE_RAM(u32, rec) & 0x80000000u) || *n >= 3000u)
		return;
	if (EE_RAM(u8, rec + PS2_PLAYER_BOMBS) == 0)
		EE_RAM(u8, rec + PS2_PLAYER_BOMBS) = 1;
#ifdef BL_FORCE_SHIP /* experiment: P1 ship word (+4, pilot * 4 + type) */
	EE_RAM(u32, rec + 4) = BL_FORCE_SHIP;
#endif
	row = (u8 *)(0x01FD0010u + 18u * *n);
	for (i = 0; i < 16u; i++)
		row[i] = 0;
	for (i = 0; i < 128u; i++) {
		const u32 a = PS2_SHOTS_BASE + i * PS2_SHOT_STRIDE;
		if (EE_RAM(u32, a) & 0x80000000u) {
			const u32 t = EE_RAM(u32, a + 4);
			row[t < 15u ? t : 15u]++;
		}
	}
	b = 0;
	for (i = 0; i < 256u; i++)
		if ((EE_RAM(u32, PS2_BULLETS_BASE + i * PS2_BULLET_STRIDE) & (BULLET_CAN_HIT | BULLET_SEGMENT)) == BULLET_CAN_HIT)
			b++;
	row[16] = (u8)(b > 255u ? 255u : b);
	row[17] = EE_RAM(u8, rec + PS2_PLAYER_BOMBS);
	(*n)++;
}
#endif
#ifdef BL_ROSE_LIFE
/* TEST BUILDS ONLY (research/phase33): one 24-byte record per stage-6 rose (type 79) when it goes away, as
 * bl_stage_log.lua ROSES=1: u32 first / last stage tick, u8 slot, subtype, HP at spawn, last HP, minimum HP, pad,
 * s16 spawn x, y, last x, y. Header at 0x01FD0000: magic "RLF1", count, dropped; records from 0x01FD0010 (5,000). */
#define RL_BASE 0x01FD0000u
#define RL_MAX 5000u
struct rl_rec { u32 f0, f1; u8 slot, sub, hp0, hp, min, pad; s16 x0, y0, x, y; };
static struct rl_rec rl_cur[EN_COUNT];
static u8 rl_on[EN_COUNT];
static u32 rl_state[EN_COUNT];

static void rose_life_frame(u32 tick)
{
	volatile u32 *h = (volatile u32 *)RL_BASE;
	struct rl_rec *log = (struct rl_rec *)(RL_BASE + 16u);
	u32 i;
	if (h[0] != 0x31464C52u) {
		h[0] = 0x31464C52u;
		h[1] = h[2] = 0;
		EE_RAM(u32, 0x01FEE000u) = 0;
		for (i = 0; i < EN_COUNT; i++)
			rl_on[i] = 0, rl_state[i] = 0xFFFFFFFFu;
	}
	/* type-74 phase machine changes (timer +0x50, phase +0x9F, sub-state +0xA0, kind +0x98): 16-byte records
	 * (tick, slot, +0x50, 9F | A0 << 8 | 98 << 16) at 0x01FEE010, count at 0x01FEE000, 500 records */
	for (i = 0; i < EN_COUNT; i++) {
		const u32 a = EN_BASE + i * EN_STRIDE;
		volatile u32 *ch = (volatile u32 *)0x01FEE000u;
		if ((EE_RAM(u32, a) & 0x80000000u) && EE_RAM(u32, a + 4) == 74u) {
			const u32 st = EE_RAM(u8, a + 0x9F) | EE_RAM(u8, a + 0xA0) << 8 | EE_RAM(u8, a + 0x98) << 16;
			if (st != rl_state[i] && ch[0] < 500u) {
				volatile u32 *r = (volatile u32 *)(0x01FEE010u + 16u * ch[0]++);
				r[0] = tick;
				r[1] = i;
				r[2] = EE_RAM(u32, a + 0x50);
				r[3] = st;
			}
			rl_state[i] = st;
		}
	}
	for (i = 0; i < EN_COUNT; i++) {
		const u32 a = EN_BASE + i * EN_STRIDE;
		const u32 on = (EE_RAM(u32, a) & 0x80000000u) && EE_RAM(u32, a + 4) == 79u;
		struct rl_rec *r = &rl_cur[i];
		if (rl_on[i] && (!on || (u8)EE_RAM(u32, a + 8) != r->sub)) {
			if (h[1] < RL_MAX)
				log[h[1]++] = *r;
			else
				h[2]++;
			rl_on[i] = 0;
		}
		if (on) {
			const u8 hp = (u8)EE_RAM(u16, a + 0x3C);
			const s16 x = (s16)(EE_RAM(u32, a + 0x24) >> 16), y = (s16)(EE_RAM(u32, a + 0x28) >> 16);
			if (!rl_on[i]) {
				rl_on[i] = 1;
				r->f0 = tick;
				r->slot = (u8)i;
				r->sub = (u8)EE_RAM(u32, a + 8);
				r->hp0 = r->min = hp;
				r->x0 = x;
				r->y0 = y;
			}
			r->f1 = tick;
			r->hp = hp;
			if (hp < r->min)
				r->min = hp;
			r->x = x;
			r->y = y;
		}
	}
}
#endif
static u32 sl_type[EN_COUNT];
static u16 sl_hp0[EN_COUNT]; /* HP at first sight (BL_NOSHOT keeps boss parts at it) */
static u8 sl_alive[EN_COUNT];

void spawn_log_frame(void)
{
	struct log_header *spawns = (struct log_header *)SPAWN_LOG;
	struct log_header *bullets = (struct log_header *)BULLET_LOG;
	struct log_header *core = (struct log_header *)CORE_LOG;
	struct spawn_rec *log = (struct spawn_rec *)(spawns + 1);
	const u8 stage = EE_RAM(u8, LOG_STAGE);
	const u32 stage_tick = EE_RAM(u32, LOG_STAGE_TICK);
	unsigned i;

	sl_frame++;
#ifdef BL_ROSE_LIFE
	if (stage == 7u)
		rose_life_frame(stage_tick);
#endif
#ifdef BL_RATE_TEST
	rate_test_frame();
#endif
#ifdef BL_TRACE_WEAPON
	trace_frame();
#endif
#ifdef BL_BCOUNT
	bcount_frame();
#endif
#ifdef BL_MIDLOG
	midlog_frame();
#endif
#ifdef BL_BOMBLOG
	bomblog_frame();
#endif
	if (EE_RAM(u32, PS2_PLAYER_BASE + PS2_PLAYER_FLAGS) != 0)
		EE_RAM(u8, PS2_PLAYER_BASE + PS2_PLAYER_INVINCIBLE) = 240;
#ifdef BL_LOCK_SHOT /* controlled damage comparisons: fixed shot level */
	if (EE_RAM(u32, PS2_PLAYER_BASE + PS2_PLAYER_FLAGS) != 0)
		EE_RAM(u8, PS2_PLAYER_BASE + PS2_PLAYER_LIVES + 1) = BL_LOCK_SHOT;
#endif
#ifdef BL_RANKLOG /* research/phase24: rank held at BL_RANKLOG and 3 bombs until P1's first bomb; then every rank
		     * change (frame since the bomb, old, new) -> 0x01FD0000 (count, then 12-byte rows) */
	{
		static u32 armed, since, last;
		volatile u32 *n = (volatile u32 *)0x01FD0000u;
		volatile u32 *row = (volatile u32 *)0x01FD0010u;
		const u32 rec = PS2_PLAYER_BASE;
		if (EE_RAM(u32, rec + PS2_PLAYER_FLAGS) != 0) {
			if (!armed) {
				*n = 0;
				if (EE_RAM(u8, rec + PS2_PLAYER_BOMBS) < 3u && since > 120u) {
					armed = 1;
					since = 0;
					last = EE_RAM(u32, PS2_RANK_INV);
				} else {
					EE_RAM(u8, rec + PS2_PLAYER_BOMBS) = 3;
					EE_RAM(u32, PS2_RANK_INV) = BL_RANKLOG;
					since++;
				}
			} else {
				const u32 r = EE_RAM(u32, PS2_RANK_INV);
				since++;
				if (r != last && *n < 1000u) {
					row[3 * *n] = since;
					row[3 * *n + 1] = last;
					row[3 * *n + 2] = r;
					(*n)++;
				}
				last = r;
			}
		}
	}
#endif
#ifdef BL_SPAWN_RANK
	EE_RAM(u32, PS2_RANK_INV) = BL_SPAWN_RANK; /* controlled comparisons: same stored rank as the MAME run */
#endif
#ifdef BL_SHOT_LOG /* every new player shot (pool 0x0044C9C0, 160 x 0x34): frame, slot, type +4, +8, +0xC */
	{
		static u8 shot_alive[160];
		static u32 shot_frame;
		volatile u32 *n = (volatile u32 *)0x01FD0000u;
		volatile u32 *e = (volatile u32 *)0x01FD0010u;
		unsigned k;
		if (!shot_frame)
			*n = 0;
		shot_frame++;
		{ /* per-frame alive counts: slot 0xFF, type field = type-0 count, +8 = type-2 count */
			unsigned c0 = 0, c2 = 0;
			for (k = 0; k < 160; k++) {
				const u32 a = 0x0044C9C0u + 0x34u * k;
				if ((EE_RAM(u32, a) >> 30) == 3u) {
					if ((EE_RAM(u32, a + 4) & 0xFF) == 0)
						c0++;
					else if ((EE_RAM(u32, a + 4) & 0xFF) == 2)
						c2++;
				}
			}
			if (*n < 30000u) {
				e[2 * *n] = (shot_frame + 1) << 8 | 0xFF;
				e[2 * *n + 1] = (c0 & 0xFF) << 16 | (c2 & 0xFF) << 8;
				(*n)++;
			}
		}
		for (k = 0; k < 160; k++) {
			const u32 a = 0x0044C9C0u + 0x34u * k;
			const int on = (EE_RAM(u32, a) >> 30) == 3u;
			if (on && !shot_alive[k] && *n < 30000u) {
				e[2 * *n] = shot_frame << 8 | k;
				e[2 * *n + 1] = (EE_RAM(u32, a + 4) & 0xFF) << 16 | (EE_RAM(u32, a + 8) & 0xFF) << 8 | (EE_RAM(u32, a + 12) & 0xFF);
				(*n)++;
			}
			shot_alive[k] = (u8)on;
		}
	}
#endif
#ifdef BL_ALL_TABLES /* part-record tables of every stage (tools/stage_compare --all-tables), before the stage filter */
	for (i = 0; i < EN_COUNT; i++) {
		const u32 a = EN_BASE + i * EN_STRIDE;
		if (EE_RAM(u32, a) & 0x80000000u)
			table_seen(EE_RAM(u32, a + 4), EE_RAM(u32, a + 0x10));
	}
#endif
	if (stage != sl_stage) {
		sl_stage = stage;
		for (i = 0; i < EN_COUNT; i++) {
			sl_alive[i] = 0;
			sl_hp0[i] = 0;
		}
		for (i = 0; i < 256; i++)
			bl_pending[i] = 0;
		for (i = 0; i < 8; i++)
			bl_alive_mask[i] = 0;
	}
#ifdef BL_LOG_STAGE
	if (stage != BL_LOG_STAGE)
		return;
#endif
	if (!sl_started) {
		start_ring(spawns, SPAWN_MAX);
		start_ring(bullets, BULLET_MAX);
		start_ring(core, CORE_MAX);
#ifndef BL_ALL_TABLES
		EE_RAM(u32, TABLE_LOG) = 0;
#endif
		sl_started = 1;
#ifdef BL_COUNTS
		for (i = 0; i < 0x1800u / 4u; i++)
			EE_RAM(u32, COUNT_LOG + 4u * i) = 0;
#endif
	}
	{
		struct bullet_rec *bl = (struct bullet_rec *)(bullets + 1);
		for (i = 0; i < 256; i++) {
			const u32 a = PS2_BULLETS_BASE + i * PS2_BULLET_STRIDE;
			const u32 fl = EE_RAM(u32, a);
			const int on = (fl & (BULLET_CAN_HIT | BULLET_SEGMENT)) == BULLET_CAN_HIT;
			const u32 bit = 1u << (i & 31);
			const s32 x = EE_RAM(s32, a + PS2_BULLET_X), y = EE_RAM(s32, a + PS2_BULLET_Y);
			if (bl_pending[i]) {
				const u32 sequence = bl_pending[i];
				if (!on || bullets->total - sequence >= BULLET_MAX)
					bl_pending[i] = 0;
				else if (++bl_age[i] == 6) {
					struct bullet_rec *r = &bl[(sequence - 1) % BULLET_MAX];
					r->dx = (s16)(((x - bl_x0[i]) >> 8) / 6);
					r->dy = (s16)(((y - bl_y0[i]) >> 8) / 6);
					bl_pending[i] = 0;
				}
			}
#ifdef BL_COUNTS
			if (on && !(bl_alive_mask[i >> 5] & bit) && sl_first) {
				const u32 bin = (sl_frame - sl_first) / 500u;
				if (bin < 64u)
					EE_RAM(u16, COUNT_LOG + 0x1000u + 2u * (bin * 16u + (EE_RAM(u32, a + 4) & 15u))) += 1;
			}
#endif
			if (on && !(bl_alive_mask[i >> 5] & bit) && sl_first) {
				const u32 serial = bullets->total;
				struct bullet_rec *r = &bl[serial % BULLET_MAX];
				r->frame = sl_frame - sl_first;
				r->type = (u16)EE_RAM(u32, a + 4);
				r->slot = (u8)i;
				r->x = (s16)(x >> 16);
				r->y = (s16)(y >> 16);
				r->dx = r->dy = 0;
				bl_x0[i] = x;
				bl_y0[i] = y;
				r->stage = stage;
				r->stage_tick = stage_tick;
				bullets->total = serial + 1;
				bl_pending[i] = serial + 1;
				bl_age[i] = 0;
			}
			if (on)
				bl_alive_mask[i >> 5] |= bit;
			else
				bl_alive_mask[i >> 5] &= ~bit;
		}
	}
	for (i = 0; i < EN_COUNT; i++) {
		const u32 a = EN_BASE + i * EN_STRIDE;
		const u32 fl = EE_RAM(u32, a);
		const u32 t = EE_RAM(u32, a + 4);
		const int on = (fl & 0x80000000u) != 0;
#ifdef BL_COUNTS
		if (on && (!sl_alive[i] || sl_type[i] != t) && t < 128u) {
			const u32 f = sl_first ? sl_frame - sl_first : 0;
			const u32 c = COUNT_LOG + 12u * t;
			if (!EE_RAM(u32, c))
				EE_RAM(u32, c + 4) = f;
			EE_RAM(u32, c) += 1;
			EE_RAM(u32, c + 8) = f;
		}
#endif
		if (on && (!sl_alive[i] || sl_type[i] != t)) {
			const u32 serial = spawns->total;
			struct spawn_rec *r = &log[serial % SPAWN_MAX];
			if (!sl_first)
				sl_first = sl_frame;
			r->frame = sl_frame - sl_first;
			r->slot = (u16)i;
			r->hp = EE_RAM(u16, a + 0x3C);
			r->type = t;
			r->subtype = EE_RAM(u32, a + 8);
			r->score = EE_RAM(u32, a + 0x40);
			sl_hp0[i] = r->hp;
			table_seen(t, EE_RAM(u32, a + 0x10));
			r->x = (s16)(EE_RAM(s32, a + 0x24) >> 16);
			r->y = (s16)(EE_RAM(s32, a + 0x28) >> 16);
			r->stage = stage;
			r->stage_tick = stage_tick;
			spawns->total = serial + 1;
		}
#ifdef BL_NOSHOT /* untouched-boss timelines: boss parts never lose HP while the stage is logged */
		if (on && t == BL_BOSS_TYPE && !sl_hp0[i])
			sl_hp0[i] = EE_RAM(u16, a + 0x3C); /* parts that get their HP after the spawn frame */
		if (on && t == BL_BOSS_TYPE && sl_hp0[i])
			EE_RAM(u16, a + 0x3C) = sl_hp0[i];
#endif
		sl_alive[i] = (u8)on;
		sl_type[i] = t;
		#if defined(BL_CORE_TURRET) /* spiral turrets (type 5, subtype 0x50..0x57) every 4 frames */
		if (on && t == 5 && sl_first && !((sl_frame - sl_first) & 3) && (EE_RAM(u32, a + 8) & ~7u) == 0x50u) {
#elif defined(BL_CORE_FLAGS) /* every type-5 part every 16 frames, flags in x (low) / y (high) */
		if (on && t == 5 && sl_first && !((sl_frame - sl_first) & 15)) {
#else
#ifdef BL_CORE_EVERY
#define CORE_MASK 0u
#else
#define CORE_MASK 3u
#endif
		if (on && t == BL_BOSS_TYPE && sl_first && !((sl_frame - sl_first) & CORE_MASK) &&
#ifdef BL_CORE_ONLY0
		    EE_RAM(u32, a + 8) == 0u) {
#else
		    (EE_RAM(u32, a + 8) < 3u || EE_RAM(u32, a + 0x40) >= 50000u)) {
#endif
#endif
			const u32 serial = core->total;
			struct core_rec *ring = (struct core_rec *)(core + 1);
			struct core_rec *sample = &ring[serial % CORE_MAX];
			sample->frame = sl_frame - sl_first;
			sample->slot = (u16)(i | EE_RAM(u8, PS2_PLAYER_BASE + PS2_PLAYER_LIVES + 1) << 8); /* + P1 shot level */
			sample->hp = EE_RAM(u16, a + 0x3C);
			sample->subtype = EE_RAM(u32, a + 8);
			sample->mode = EE_RAM(u8, a + 0x9A);
#ifdef BL_CORE_HIT /* hit-flash timer (+0x84) instead of the step byte */
			sample->step = EE_RAM(u8, a + 0x84);
#else
			sample->step = EE_RAM(u8, a + 0xA6);
#endif
#if defined(BL_CORE_TURRET) /* x = parent's step byte (+0xA6) | stage counter << 8, y = turret timer (+0x9B) */
			sample->x = (s16)(EE_RAM(u8, EN_BASE + EN_STRIDE * (u32)EE_RAM(s16, a + 0x7C) + 0xA6) | EE_RAM(u8, 0x00338E9Cu) << 8);
			sample->y = EE_RAM(u8, a + 0x9B);
#elif defined(BL_CORE_FLAGS)
			sample->x = (s16)fl;
			sample->y = (s16)(fl >> 16);
#elif defined(BL_CORE_STATE) /* boss step (+0xA6) and mode (+0x9A) instead of the position */
			sample->x = EE_RAM(u8, a + 0xA6);
			sample->y = EE_RAM(u8, a + 0x9A);
#else
			sample->x = (s16)(EE_RAM(s32, a + 0x24) >> 16);
			sample->y = (s16)(EE_RAM(s32, a + 0x28) >> 16);
#endif
			sample->stage = stage;
			sample->stage_tick = stage_tick;
			core->total = serial + 1;
		}
	}
}
#endif
