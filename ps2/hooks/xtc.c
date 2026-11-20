/* Kuro BL's XTC (Xtreme Terror Counter) graze system, re-implemented for the PS2 engine.
 *
 * Behavioural specification (Black Label arcade, from ibara360's documentation of BL's graze test at SH-3
 * 0C06EF50 and its timer at 0C071110; written here from that description, not translated from code):
 *   - one player is tested per frame, alternating sides;
 *   - each enemy bullet that can hit (flags & 0x10000000, not a long-bullet segment) inside the graze box,
 *     while the player can be hit, the shot button has been held >= 5 frames and the option pods are out:
 *     score += 10 and the counter's quarter-steps += 1, capped at 39996 (displayed value = quarters >> 2);
 *   - whenever the displayed value changes the wipe timer is set to 128; it counts down every frame and
 *     clears the counter at 0. A bomb clears it 16 frames after the bomb starts (TODO: bomb event on PS2);
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
};

__attribute__((section(".hookhdr"), used)) struct xtc_state xtc = { 0x31435458u, 0u, {{0, 0, 0, 0}, {0, 0, 0, 0}}, 0u, 0u };

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

/* Once per game logic frame (hooked after the retail collision pass). */
void xtc_frame(void)
{
	unsigned s;

	for (s = 0; s < 2; s++) {
		struct xtc_player *p = &xtc.pl[s];
		const u32 rec = PS2_PLAYER_BASE + s * PS2_PLAYER_STRIDE;
		const int down = (EE_RAM(u16, rec + PS2_PLAYER_HELD) & PS2_PAD_SHOT) != 0;
		if (EE_RAM(u32, rec + PS2_PLAYER_FLAGS) == 0) { /* side not in the game: a new run starts clean */
			p->quarters = 0;
			p->left = 0;
			p->held = 0;
			continue;
		}
		if (!down)
			p->held = 0;
		else if (p->held < XTC_MAX_HELD)
			p->held++;
		if (p->left && --p->left == 0)
			p->quarters = 0;
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
