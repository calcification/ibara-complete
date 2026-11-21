/* Kuro BL's XTC (Xtreme Terror Counter) graze system, re-implemented for the PS2 engine.
 *
 * Behavioural specification (Black Label arcade, from ibara360's documentation of BL's graze test at SH-3
 * 0C06EF50 and its timer at 0C071110; written here from that description, not translated from code):
 *   - one player is tested per frame, alternating sides;
 *   - each enemy bullet that can hit (flags & 0x10000000, not a long-bullet segment) inside the graze box,
 *     while the player can be hit, the shot button has been held >= 5 frames and the option pods are out:
 *     score += 10 and the counter's quarter-steps += 1, capped at 39996 (displayed value = quarters >> 2);
 *   - whenever the displayed value changes the wipe timer is set to 128; it counts down every frame and
 *     clears the counter at 0. A bomb clears it 16 frames after the bomb starts (PS2: a drop in the
 *     player's bomb power, bombs x 40 + fragments);
 *   - box half sizes: 14 + e + 1 along the game's x, 19 + e + 1 along its y, with
 *     e = ((((2^24 - rank_inv) >> 3) * held) >> 3) >> 16, held = shot-held frames (0..8). Strict "<".
 *
 * PS2 adaptation notes: the PS2 player record (stride 0x290) has no BL XTC fields, so state lives here in
 * the cave. Shot-held frames are counted from the record's held-button word (+0x24C & 0x10). Player and
 * bullet positions share one space on PS2 (no camera term). "Pods out" has no located PS2 equivalent yet;
 * XTC_REQUIRE_PODS stays 0 (documented deviation) until it is found.
 */
#include "ibara_ps2.h"

#ifndef XTC_REQUIRE_PODS
#define XTC_REQUIRE_PODS 0
#endif
#define XTC_MAX_QUARTERS 39996
#define XTC_TIMER 128
#define XTC_MIN_HELD 5
#define XTC_MAX_HELD 8

struct xtc_player {
	s32 quarters;  /* counter x4 */
	u16 left;      /* frames until the wipe */
	u8 held;       /* shot-held frames, 0..8 */
	u8 pad_;
};

struct xtc_state {
	u32 magic;     /* 'XTC1' */
	u32 side;      /* the side tested next frame */
	struct xtc_player pl[2];
	u32 grazes;    /* total, for debugging */
	u32 points;    /* total score added by XTC (runtime check: points == 10 * grazes) */
	u16 power[2];  /* last bomb power (bombs * 40 + fragments) per side */
	u8 wipe[2];    /* frames until a bomb's wipe (0 = none pending) */
	u16 bombs_seen; /* debug: bomb starts detected */
};

__attribute__((section(".hookhdr"), used)) struct xtc_state xtc = { 0x31435458u, 0u, {{0, 0, 0, 0}, {0, 0, 0, 0}}, 0u, 0u, {0, 0}, {0, 0}, 0 };

static inline s32 iabs(s32 v) { return v < 0 ? -v : v; }

static int xtc_test_player(unsigned side)
{
	const u32 rec = PS2_PLAYER_BASE + side * PS2_PLAYER_STRIDE;
	struct xtc_player *p = &xtc.pl[side];
	const u32 rank_inv = EE_RAM(u32, PS2_RANK_INV) & 0x00FFFFFFu;
	const s32 px = EE_RAM(s32, rec + PS2_PLAYER_X) >> 16;
	const s32 py = EE_RAM(s32, rec + PS2_PLAYER_Y) >> 16;
	s32 e, hx, hy;
	unsigned k;
	int n = 0;

	if (!(EE_RAM(u32, rec + PS2_PLAYER_FLAGS) & PLAYER_CAN_BE_HIT))
		return 0;
	if (p->held < XTC_MIN_HELD)
		return 0;
	e = (s32)(((((0x01000000u - rank_inv) >> 3) * p->held) >> 3) >> 16);
	hx = 14 + e + 1;
	hy = 19 + e + 1;
	for (k = 0; k < PS2_BULLET_COUNT; k++) {
		const u32 b = PS2_BULLETS_BASE + k * PS2_BULLET_STRIDE;
		const u32 f = EE_RAM(u32, b + PS2_BULLET_FLAGS);
		s32 bx, by;
		if ((f & (BULLET_CAN_HIT | BULLET_SEGMENT)) != BULLET_CAN_HIT)
			continue;
		bx = EE_RAM(s32, b + PS2_BULLET_X) >> 16;
		by = EE_RAM(s32, b + PS2_BULLET_Y) >> 16;
		if (iabs(bx - px) < hx && iabs(by - py) < hy)
			n++;
	}
	return n;
}

static void xtc_add(unsigned side, int n)
{
	struct xtc_player *p = &xtc.pl[side];
	const u32 rec = PS2_PLAYER_BASE + side * PS2_PLAYER_STRIDE;
	while (n-- > 0) {
		const s32 shown = p->quarters >> 2;
		EE_RAM(u32, rec + PS2_PLAYER_SCORE) += 10;
		xtc.points += 10;
		if (p->quarters < XTC_MAX_QUARTERS)
			p->quarters++;
		if ((p->quarters >> 2) != shown)
			p->left = XTC_TIMER;
		xtc.grazes++;
	}
}

#ifdef BL_TEST_ALL_WEAPONS
/* TEST BUILDS ONLY (--define BL_TEST_ALL_WEAPONS): own all seven weapons, current MG, when a side starts. */
static void test_grant_weapons(u32 rec)
{
	unsigned i;
	if (EE_RAM(u8, rec + 0x278) != 0)
		return;
	for (i = 0; i < 7; i++)
		EE_RAM(u8, rec + 0x271 + i) = 1;
	EE_RAM(u8, rec + 0x278) = 7;
	EE_RAM(u8, rec + 0x270) = 5;
}
#endif

#ifdef BL_TEST_SHOT_LEVELS
/* TEST BUILDS ONLY: drive the game's small-P pickup handler (0x0012FB00(side, item)) once a game starts.
 * Results (level, shot P) after each case are left in bl_shot_test[]. */
typedef void (*pickup_fn)(int side, int item);
u8 bl_shot_test[8];
u32 bl_rank_test; /* stored rank after one fragment pickup starting from 0x00800000 */
u32 bl_rank_test2[2]; /* rank after a level-1 rose and after a level-3 medal (each from 0x00800000) */
static void test_shot_levels(u32 rec)
{
	volatile u8 *streak = (volatile u8 *)(0x00495130u + 8u * EE_RAM(u8, 0x0033FCF0u - 28276));
	if (bl_shot_test[7])
		return;
	bl_shot_test[7] = 1;
	EE_RAM(u8, rec + 0x25B) = 2; EE_RAM(u8, rec + 0x25C) = 0; streak[0] = 5;   /* secret case */
	((pickup_fn)0x0012FB00u)(0, 0);
	bl_shot_test[0] = EE_RAM(u8, rec + 0x25B); bl_shot_test[1] = EE_RAM(u8, rec + 0x25C);
	EE_RAM(u8, rec + 0x25B) = 5; EE_RAM(u8, rec + 0x25C) = 5; streak[0] = 0;   /* level 5 -> 6 case */
	((pickup_fn)0x0012FB00u)(0, 0);
	bl_shot_test[2] = EE_RAM(u8, rec + 0x25B); bl_shot_test[3] = EE_RAM(u8, rec + 0x25C);
	EE_RAM(u32, PS2_RANK_INV) = 0x00800000u;                                     /* fragment rank case */
	((pickup_fn)0x0012F400u)(0, 0);
	bl_rank_test = EE_RAM(u32, PS2_RANK_INV);
	EE_RAM(u32, PS2_RANK_INV) = 0x00800000u;                                     /* rose, level 1 */
	EE_RAM(u32, PS2_ITEMS_BASE + 255 * 0x58 + 8) = 1;
	((pickup_fn)0x0012F680u)(0, 255);
	bl_rank_test2[0] = EE_RAM(u32, PS2_RANK_INV);
	EE_RAM(u32, PS2_RANK_INV) = 0x00800000u;                                     /* medal, level 3 */
	EE_RAM(u16, PS2_ITEMS_BASE + 255 * 0x58 + 8) = 3;
	((pickup_fn)0x0012F7B0u)(0, 255);
	bl_rank_test2[1] = EE_RAM(u32, PS2_RANK_INV);
}
#endif

#ifdef BL_SPAWN_LOG
void spawn_log_frame(void);
#endif

/* BLACK LABEL build only (ps2/hooks/bl_player.c); absent in the XTC-only test profile. */
void bl_player_frame(u32 rec) __attribute__((weak));

/* Once per game logic frame (hooked after the retail collision pass). */
void xtc_frame(void)
{
	unsigned s;

#ifdef BL_SPAWN_LOG
	spawn_log_frame();
#endif
	for (s = 0; s < 2; s++) {
		struct xtc_player *p = &xtc.pl[s];
		const u32 rec = PS2_PLAYER_BASE + s * PS2_PLAYER_STRIDE;
		const int down = (EE_RAM(u16, rec + PS2_PLAYER_HELD) & PS2_PAD_SHOT) != 0;
		if (EE_RAM(u32, rec + PS2_PLAYER_FLAGS) == 0) { /* side not in the game: a new run starts clean */
			p->quarters = 0;
			p->left = 0;
			p->held = 0;
			xtc.power[s] = 0;
			xtc.wipe[s] = 0;
			continue;
		}
#ifdef BL_TEST_ALL_WEAPONS
		test_grant_weapons(rec);
#endif
		if (bl_player_frame)
			bl_player_frame(rec);
#ifdef BL_TEST_SHOT_LEVELS
		if (s == 0 && (EE_RAM(u32, rec + PS2_PLAYER_FLAGS) & PLAYER_CAN_BE_HIT) &&
		    EE_RAM(u32, 0x00338F40u) == 0) /* rank helpers do nothing while $gp-0x6DB0 (0x00338F40) is set */
			test_shot_levels(rec);
#endif
		if (!down)
			p->held = 0;
		else if (p->held < XTC_MAX_HELD)
			p->held++;
		if (p->left && --p->left == 0)
			p->quarters = 0;
		{
			const u16 power = (u16)(EE_RAM(u8, rec + PS2_PLAYER_BOMBS) * 40 + EE_RAM(u8, rec + PS2_PLAYER_FRAGS));
			if (power < xtc.power[s]) { /* a bomb started: BL wipes the counter 16 frames later */
				xtc.wipe[s] = 16;
				xtc.bombs_seen++;
			}
			xtc.power[s] = power;
			if (xtc.wipe[s] && --xtc.wipe[s] == 0) {
				p->quarters = 0;
				p->left = 0;
			}
		}
	}
	s = xtc.side;
	xtc.side ^= 1u;
	xtc_add(s, xtc_test_player(s));
}

/* Value the HUD should show for a side (0..9999). */
int xtc_shown(unsigned side)
{
	return xtc.pl[side & 1].quarters >> 2;
}

/* Instant KURO (kuro.c): a fresh counter each time KURO mode is entered (the executable is no longer reloaded). */
void xtc_reset(void)
{
	unsigned s;
	xtc.side = 0u;
	for (s = 0; s < 2u; s++) {
		xtc.pl[s].quarters = 0;
		xtc.pl[s].left = 0;
		xtc.pl[s].held = 0;
		xtc.power[s] = 0;
		xtc.wipe[s] = 0;
	}
}
