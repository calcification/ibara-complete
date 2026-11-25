/* Black Label's RANK bar, centred under the high score (KURO only; research/phase19).
 *
 * BL (0C0703C0) draws an 80 x 14 sprite (6-px metal frame, 8-px RANK plate) at game x 292 / y 80 and a fill inside
 * the frame: length ((0xFFFFFF - rank) >> 8) * 70 >> 16 px (69 unless rank = 0), grey texture rows tinted with
 * L = (0xFFFFFF - rank) >> 16: R = max(0, 2L - 255), G = 2L <= 255 ? 2L : 510 - 2L, B = max(0, 255 - 2L); the whole
 * bar flashes white (tint 0xFFFFFF) at rank 0 and fades when a player is close to it.
 *
 * PS2's Arrange gauge 0x00129360 is a port of that routine with other art; the HUD pass calls frontend_rank_bar
 * to select the gauge. The art is not in this repository: bl_bar_art is
 * zero here and filled from the user's own ibarablk ROM by the patcher (patcher/apply_kuro_patch.py --bl-rom) or by
 * scripts/build_black_label_iso.py --bl-rom. Without it, KURO shows the Arrange gauge as before.
 *
 * The art goes onto our own 16-bit texture page (bl_tex.c: PSMCT16 = the arcade's 1:5:5:5 pixels, so the colours
 * are exact) and is drawn with the game's sprite routine 0x00110B70.
 */
#include "ibara_ps2.h"

#define BAR_W 80
#define BAR_H 14
#define FILL_STRIP 70
/* BL art (screen orientation, row-major, BE 5:5:5 words as in the ROM: bit 15 = opaque); the 16-byte tag before
 * it lets the patcher find it in the disc image. */
struct bl_bar_blob {
	char tag[16];
	u16 px[BAR_H * BAR_W];
};
struct bl_bar_blob bl_bar_blob = {"BLRANKBAR-ART-01", {0}};

/* our 16-bit page 5 (bl_tex.c), rows 0-19 (kept free by the select-screen atlas): the 80 x 14 art at (0, 0),
 * the 70 x 2 grey fill strip at (0, 16) */
#define BAR_PAGE 5u /* pixels */
#define BAR_TEX 8u  /* bl_tex.c KT_BAR: the rank bar's texture object */
#define FILL_PY 16u
u16 *ktex_pixels(u32 page);
u32 ktex_init(void);
void ktex_off(void);
void ktex_flush(void);
u32 ktex_draw(u32 page, u32 px, u32 py, u32 pw, u32 ph, u32 flags, u32 tint, s32 x, s32 y);
static u32 bar_built;

static int art_present(void)
{
	return (bl_bar_blob.px[3 * BAR_W + 40] & 0x0080u) != 0; /* a frame pixel (bit 15 of a big-endian word) */
}

/* arcade 1:5:5:5 (opaque, R, G, B) -> PS2 PSMCT16 (A, B, G, R) */
static u16 to_ct16(u32 w)
{
	return (u16)((w & 0x8000u) | (w & 31u) << 10 | (w & 0x3E0u) | ((w >> 10) & 31u));
}

static void build_page(void)
{
	u16 *const pix = ktex_pixels(BAR_PAGE);
	u32 x, y;
	for (y = 0; y < BAR_H; y++)
		for (x = 0; x < BAR_W; x++) {
			const u16 b = bl_bar_blob.px[y * BAR_W + x];
			pix[y * 256u + x] = to_ct16((u16)(b << 8 | b >> 8)); /* stored big-endian */
		}
	for (x = 0; x < FILL_STRIP; x++) { /* BL's fill texture: grey 23 / 13 */
		pix[FILL_PY * 256u + x] = to_ct16(0x8000u | 23u << 10 | 23u << 5 | 23u);
		pix[(FILL_PY + 1u) * 256u + x] = to_ct16(0x8000u | 13u << 10 | 13u << 5 | 13u);
	}
	ktex_flush();
	bar_built = 1;
}

/* Called by kuro.c when KURO is switched off. */
void bl_rank_bar_off(void)
{
	ktex_off();
}

#define RANK       0x00338EB4u /* $gp-28220: stored rank (0 hardest) */
#define FRAMES     0x00338CDCu /* $gp-28692: the frame counter Arrange's gauge flashes with */
#define CAMERA     0x00338DD4u /* $gp-28444: scroll position (16.16) */
#define OFF_X      0x00338D08u /* $gp-28648 / $gp-28640: HUD offsets Arrange's gauge adds */
#define OFF_Y      0x00338D10u
#define BOSS_UP    0x00338B68u /* $gp-29064: the gauges move down while it is set */
/* BL's x is 292; PS2's high-score line sits higher than the arcade's, so 9 px more puts the bar right under it
 * (PCSX2 screenshots), where BL has it. */
#define BAR_X      301
#define BAR_Y      80
/* PS2 prints the stage name under the high score (HUD text row 37, cols 5-18), where BL's bar is; BL has no stage
 * name there, so KURO blanks it while the bar is shown. */
#define HUD_STR(s, row, col, colour) GAME_CALL4(0x00111460u, s, row, col, colour)
static const char stage_blank[] = "              ";
static s32 bar_x = BAR_X;
#define ARRANGE_GAUGE() GAME_CALL0(0x00129360u)

/* The XTC graze sphere (research/phase21; BL 0C071110, the block at 0C071380): while a player holds the shot
 * (BL's player +0x270 = held frames 1..8), a 16 x 16 orb turns on the ship — blue for player 1, red for player 2,
 * 8 frames, one every 4 game frames — at the player's position + (+2 straight / -2 spread, 0) px (BL's per-kind
 * offsets, 0C1754E0), drawn twice: flags 0x1217FF00, then 0x12040000 with alpha held x 0x808; tint 0x808080.
 * Art: page 5 row 96, frame f at column 16 f (the select art segment, patcher --bl-rom). */
#define SPHERE_ROW 96u
#define SEL_ART_TAG 0x01F1FFF0u
u32 xtc_held(u32 side);

static int sphere_art(void)
{
	return EE_RAM(u32, SEL_ART_TAG) == 0x45534C42u && EE_RAM(u32, SEL_ART_TAG + 12u) == 0x004E4F2Du; /* "BLSE" .. "-ON\0" */
}

/* The XTC number popup (BL 0C071110 up to 0C0712F2; research/phase21): while the counter is non-zero, "+" and its
 * digits near where the player was when the value last changed. Anchor (16.16): game x = x + 32 px + (128 - left) /
 * 4 px (it drifts), screen y = y - camera; digit k (k = 0 least significant) at slot 5 - k, "+" at the slot after
 * the most significant digit: small digits (value <= 999) 8 x 8 at y + 8 slot + 4 (digits + 1) - 40, offset (-8,
 * -8); big ones 16 x 16 at y + 16 slot + 8 (digits + 1) - 80, offset (-16, -16). Flags 0x12040000, alpha
 * min(2 left, 192); tint 0x30F060, white on odd frames while left > 119.
 * Art on page 5: big digit d (10 = '+') at column 16 d, row 112; small d at column 176 + 8 d, row 112 ('+': 176, 120). */
u32 xtc_popup(u32 side, u32 *left, u32 *x, u32 *y);

static void bl_xtc_popup(s32 ox, s32 oy)
{
	u32 s;
	for (s = 0; s < 2u; s++) {
		u32 left, px, py, n, nd, m, slot, a, tint, flags;
		const u32 v = xtc_popup(s, &left, &px, &py);
		s32 ax, ay;
		const u32 big = v > 999u;
		const s32 sz = big ? 16 : 8;
		if (!v || !EE_RAM(u32, PS2_PLAYER_BASE + s * PS2_PLAYER_STRIDE))
			continue;
		for (nd = 1u, m = v; m; m /= 10u)
			nd++;
		a = left * 2u > 0xC0u ? 0xC0u : left * 2u;
		flags = 0x12040000u | a << 8 | a;
		tint = (left > 119u && (EE_RAM(u32, FRAMES) & 1u)) ? 0xFFFFFFu : 0x30F060u;
		ax = (s32)((px + ((128u - left) << 14) + 0x200000u) >> 16) - sz + ox;
		ay = (s32)((py - (EE_RAM(u32, CAMERA) & 0xFFFF0000u)) >> 16) + (big ? 8 * (s32)nd - 80 : 4 * (s32)nd - 40) - sz + oy;
		for (n = v, slot = 5u; slot > 0u; slot--) {
			const u32 d = n % 10u;
			if (slot < 5u && !d && !n)
				break;
			n /= 10u;
			if (big)
				ktex_draw(BAR_TEX, 16u * d, 112u, 16, 16, flags, tint, ax, ay + 16 * (s32)slot);
			else
				ktex_draw(BAR_TEX, 176u + 8u * d, 112u, 8, 8, flags, tint, ax, ay + 8 * (s32)slot);
		}
		if (big)
			ktex_draw(BAR_TEX, 160u, 112u, 16, 16, flags, tint, ax, ay + 16 * (s32)slot);
		else
			ktex_draw(BAR_TEX, 176u, 120u, 8, 8, flags, tint, ax, ay + 8 * (s32)slot);
	}
}

static void bl_sphere(s32 ox, s32 oy)
{
	u32 s;
	if (!sphere_art())
		return;
	bl_xtc_popup(ox, oy);
	for (s = 0; s < 2u; s++) {
		const u32 rec = PS2_PLAYER_BASE + s * PS2_PLAYER_STRIDE;
		const u32 held = xtc_held(s), f = s * 8u + ((EE_RAM(u32, FRAMES) >> 2) & 7u);
		const u32 kind = ((EE_RAM(u32, rec + 4u) >> 2) ^ s) & 1u; /* ship word = side * 4 XOR (kind * 4 + type) */
		s32 x, y;
		if (!held || !EE_RAM(u32, rec))
			continue;
		x = (s32)(EE_RAM(u32, rec + 0x10u) >> 16) + (kind ? -2 : 2) - 8 + ox;
		y = (s32)((EE_RAM(u32, rec + 0x14u) - (EE_RAM(u32, CAMERA) & 0xFFFF0000u)) >> 16) - 8 + oy;
		ktex_draw(BAR_TEX, 16u * f, SPHERE_ROW, 16, 16, 0x1217FF00u, 0x808080u, x, y);
		ktex_draw(BAR_TEX, 16u * f, SPHERE_ROW, 16, 16, 0x12040000u | held * 0x808u, 0x808080u, x, y);
	}
}

extern u32 kuro_on, opt_gauge, sel_active;

static void bl_rank_bar(void)
{
	const u32 rank = EE_RAM(u32, RANK);
	u32 tint = 0x808080u, flags = 0x10000000u, alpha = 0, s, len, l2, col;
	s32 ox, oy;
	HUD_STR(stage_blank, 37, 5, 0x80808000u);
	if (!art_present() || !ktex_init()) {
		if (opt_gauge)
			ARRANGE_GAUGE();
		return;
	}
	if (!bar_built)
		build_page();
	bl_sphere(EE_RAM(s32, OFF_X), EE_RAM(s32, OFF_Y));
	if (!opt_gauge)
		return;
	/* slide like BL (target BAR_X, 16 px lower while a boss gauge is up) */
	{
		const s32 target = EE_RAM(u32, BOSS_UP) ? BAR_X - 16 : BAR_X;
		bar_x += bar_x < target ? 1 : bar_x > target ? -1 : 0;
	}
	/* fade near a player (BL: ((|dy| - 48, >= 0) + |dx|) * 8 inside a 64 x 16 box, the most opaque of both) */
	for (s = 0; s < 2u; s++) {
		const u32 rec = PS2_PLAYER_BASE + s * PS2_PLAYER_STRIDE;
		s32 dy, dx, a;
		if (!EE_RAM(u32, rec))
			continue;
		dy = (BAR_Y + 40) - (s32)((EE_RAM(u32, rec + 0x14u) - (EE_RAM(u32, CAMERA) & 0xFFFF0000u)) >> 16);
		dx = bar_x + 8 - (s32)(EE_RAM(u32, rec + 0x10u) >> 16);
		if (dy < 0)
			dy = -dy;
		if (dx < 0)
			dx = -dx;
		if (dy > 63 || dx > 15)
			continue;
		a = (s32)((dy > 48 ? dy - 48 : 0) + dx) << 3;
		if ((u32)a > alpha || !alpha)
			alpha = (u32)a ? (u32)a : 1u;
	}
	if (alpha) {
		if (alpha > 255u)
			alpha = 255u;
		flags |= 0x2040000u | alpha << 8 | alpha;
	}
	if (rank == 0 && (EE_RAM(u32, FRAMES) & 2u))
		tint = 0xFFFFFFu;
	ox = EE_RAM(s32, OFF_X);
	oy = EE_RAM(s32, OFF_Y);
	/* the whole 80 x 14 art: screen rows 0-13 = game x bar_x + 6 down to bar_x - 7 */
	if (!ktex_draw(BAR_TEX, 0, 0, BAR_W, BAR_H, flags, tint, bar_x - 7 + ox, BAR_Y + oy)) {
		ARRANGE_GAUGE();
		return;
	}
	/* fill: art x 5, rows 2-3 (game x bar_x + 3 .. + 4) */
	len = ((0xFFFFFFu - rank) >> 8) * 70u >> 16;
	if (len == 70u && rank != 0)
		len = 69u;
	if (!len)
		return;
	l2 = ((0xFFFFFFu - rank) >> 16) * 2u;
	{
		const u32 r = l2 > 255u ? l2 - 255u : 0, g = l2 <= 255u ? l2 : 510u - l2, b = l2 < 255u ? 255u - l2 : 0;
		/* BL: out = src * (t >> 2) / 31 (5-bit); GS modulate: tex * c / 128 -> c = t * 128 / 124 */
		const u32 rr = r * 33u >> 5, gg = g * 33u >> 5, bb = b * 33u >> 5;
		col = (rr > 255u ? 255u : rr) << 16 | (gg > 255u ? 255u : gg) << 8 | (bb > 255u ? 255u : bb);
	}
	ktex_draw(BAR_TEX, 0, FILL_PY, len, 2, flags, col, bar_x + 3 + ox, BAR_Y + 5 + oy);
}

void frontend_rank_bar(void)
{
	if ((kuro_on && sel_active) || EE_RAM(u8, 0x00338E7Cu)) /* ship selection or attract demo */
		return;
	if (kuro_on)
		bl_rank_bar();
	else if (opt_gauge || EE_RAM(u32, 0x00338F44u)) /* Arrange retains its retail gauge */
		ARRANGE_GAUGE();
}

void kuro_weapon_bar(void)
{
	if (!sel_active)
		GAME_CALL0(0x001285C0u);
}
