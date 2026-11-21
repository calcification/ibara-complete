/* Black Label's RANK bar, centred under the high score (KURO only; research/phase19).
 *
 * BL (0C0703C0) draws an 80 x 14 sprite (6-px metal frame, 8-px RANK plate) at game x 292 / y 80 and a fill inside
 * the frame: length ((0xFFFFFF - rank) >> 8) * 70 >> 16 px (69 unless rank = 0), grey texture rows tinted with
 * L = (0xFFFFFF - rank) >> 16: R = max(0, 2L - 255), G = 2L <= 255 ? 2L : 510 - 2L, B = max(0, 255 - 2L); the whole
 * bar flashes white (tint 0xFFFFFF) at rank 0 and fades when a player is close to it.
 *
 * PS2's Arrange gauge 0x00129360 is a port of that routine with other art; KURO calls bl_rank_bar instead (the HUD
 * pass's `jal 0x00129360` at 0x0012E42C, a KURO table word). The art is not in this repository: bl_bar_art is
 * zero here and filled from the user's own ibarablk ROM by the patcher (patcher/apply_kuro_patch.py --bl-rom) or by
 * scripts/build_black_label_iso.py --bl-rom. Without it, KURO shows the Arrange gauge as before.
 *
 * The art is painted into fully transparent parts of the HUD texture page (TIM2, 256 x 256 PSMT8, page 3/1 of the
 * game's texture table) with each colour mapped to the nearest colour of that page's palette (all 256 entries are in
 * use, so the colours are approximate), and drawn with the game's sprite routine 0x00110B70.
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

#define TEX_TABLE  0x00341780u /* (page row * 32 + page col) -> texture index (-1 none) */
#define TEX_OBJS   0x00339DB0u /* texture index -> object; object +0x10 = its TIM2 in EE RAM */
#define HUD_PAGE   (1u * 32u + 3u)
#define TIM2_MAGIC 0x324D4954u

/* Where our pieces go: over Arrange's own gauge art (page x 0-127, y 160-171: its frame u/v 852/256 = x 0-119,
 * y 160-171, and its fill strip 856/376 = x 120-127, y 160-167), which only Arrange's gauge draws and KURO does not.
 * The region is saved before painting and put back when KURO is switched off. (Fully transparent rows elsewhere are
 * not free: other HUD sprites stretch transparent texels from them, e.g. a1 = 828 samples row 195.) */
#define REG_Y 160u
#define REG_H 12u
#define REG_W 128u
#define FRAME_PX 0u   /* frame: art rows 0-5, cols 0-79 -> page x 0-79, y 160-165 */
#define FRAME_PY 160u
#define PLATE_C0 20u  /* plate: art rows 6-13, cols 20-60 -> page x 80-120, y 160-167 */
#define PLATE_W 41u
#define PLATE_PX 80u
#define PLATE_PY 160u
#define FILL_PX 0u    /* fill strip: 70 x 2 grey -> page x 0-69, y 166-167 */
#define FILL_PY 166u
static u8 reg_saved[REG_H * REG_W];

static u8 bar_idx[BAR_H * BAR_W]; /* palette index per art pixel (0 = transparent) */
static u8 fill_idx[2];
static u32 bar_mapped_tim; /* TIM2 the indices were computed for */
u32 bar_painted_tim;       /* TIM2 our pixels were last written into */

static int art_present(void)
{
	return (bl_bar_blob.px[3 * BAR_W + 40] & 0x0080u) != 0; /* a frame pixel (bit 15 of a big-endian word) */
}

static u32 hud_tim2(void)
{
	const s32 idx = EE_RAM(s32, TEX_TABLE + HUD_PAGE * 4u);
	u32 obj, tim;
	if (idx < 0)
		return 0;
	obj = EE_RAM(u32, TEX_OBJS + (u32)idx * 4u);
	if (obj < 0x00100000u || obj >= 0x02000000u)
		return 0;
	tim = EE_RAM(u32, obj + 0x10u);
	if (tim < 0x00100000u || tim >= 0x02000000u || EE_RAM(u32, tim) != TIM2_MAGIC)
		return 0;
	if (EE_RAM(u16, tim + 0x10u + 0x14u) != 256u || EE_RAM(u16, tim + 0x10u + 0x16u) != 256u)
		return 0; /* not the 256 x 256 page we expect */
	return tim;
}

/* CLUT entry of palette index i (TIM2 32-bit CLUTs are stored in the GS's CSM1 order) */
static u32 clut_rgba(u32 clut, u32 i)
{
	u32 p = i;
	if ((i & 0x18u) == 0x08u)
		p = i + 8u;
	else if ((i & 0x18u) == 0x10u)
		p = i - 8u;
	return EE_RAM(u32, clut + p * 4u);
}

static u8 nearest(u32 clut, u32 r, u32 g, u32 b)
{
	u32 i, best = 1, bestd = 0xFFFFFFFFu;
	for (i = 1; i < 256u; i++) {
		const u32 c = clut_rgba(clut, i);
		s32 dr, dg, db;
		u32 d;
		if (!(c >> 24))
			continue; /* transparent entry */
		dr = (s32)(c & 0xFFu) - (s32)r;
		dg = (s32)((c >> 8) & 0xFFu) - (s32)g;
		db = (s32)((c >> 16) & 0xFFu) - (s32)b;
		d = (u32)(dr * dr * 3 + dg * dg * 4 + db * db * 2);
		if (d < bestd) {
			bestd = d;
			best = i;
		}
	}
	return (u8)best;
}

static void map_colours(u32 tim)
{
	const u32 clut = tim + 0x40u + 0x10000u;
	u32 i;
	for (i = 0; i < BAR_H * BAR_W; i++) {
		const u16 w = (u16)(bl_bar_blob.px[i] << 8 | bl_bar_blob.px[i] >> 8); /* stored big-endian */
		bar_idx[i] = (w & 0x8000u) ? nearest(clut, ((w >> 10) & 31u) << 3, ((w >> 5) & 31u) << 3, (w & 31u) << 3) : 0;
	}
	fill_idx[0] = nearest(clut, 23u << 3, 23u << 3, 23u << 3);
	fill_idx[1] = nearest(clut, 13u << 3, 13u << 3, 13u << 3);
	bar_mapped_tim = tim;
}

static void flush_dcache(void)
{
	__asm__ __volatile__("move $4, $0\n\tli $3, 100\n\tsyscall\n"
			     : : : "v0", "v1", "a0", "a1", "a2", "a3", "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8",
			       "t9", "memory");
}

/* Paint our pieces (on: after saving the region) or put the saved region back (off). */
static u32 paint(u32 tim, u32 on)
{
	u8 *const pix = (u8 *)(tim + 0x40u);
	u32 x, y;
	if (on) {
		if (bar_mapped_tim != tim)
			map_colours(tim);
		for (y = 0; y < REG_H; y++)
			for (x = 0; x < REG_W; x++)
				reg_saved[y * REG_W + x] = pix[(REG_Y + y) * 256u + x];
		for (y = 0; y < REG_H; y++) /* clear the rest of the region (Arrange's art) */
			for (x = 0; x < REG_W; x++)
				pix[(REG_Y + y) * 256u + x] = 0;
		for (y = 0; y < 6u; y++)
			for (x = 0; x < BAR_W; x++)
				pix[(FRAME_PY + y) * 256u + FRAME_PX + x] = bar_idx[y * BAR_W + x];
		for (y = 0; y < 8u; y++)
			for (x = 0; x < PLATE_W; x++)
				pix[(PLATE_PY + y) * 256u + PLATE_PX + x] = bar_idx[(6u + y) * BAR_W + PLATE_C0 + x];
		for (x = 0; x < FILL_STRIP; x++) {
			pix[FILL_PY * 256u + FILL_PX + x] = fill_idx[0];
			pix[(FILL_PY + 1u) * 256u + FILL_PX + x] = fill_idx[1];
		}
	} else {
		for (y = 0; y < REG_H; y++)
			for (x = 0; x < REG_W; x++)
				pix[(REG_Y + y) * 256u + x] = reg_saved[y * REG_W + x];
	}
	flush_dcache();
	bar_painted_tim = on ? tim : 0;
	return on;
}

/* Called by kuro.c when KURO is switched off: the page is the retail one again. */
void bl_rank_bar_off(void)
{
	const u32 tim = hud_tim2();
	if (tim && bar_painted_tim == tim)
		paint(tim, 0);
	bar_painted_tim = 0;
}

/* 0x00110B70(flags, page col * 256 + u, page row * 256 + v, tint, x, y, w, h): the float arguments in f12-f15. */
void bar_sprite(u32 flags, u32 u, u32 v, u32 tint, s32 x, s32 y, s32 w, s32 h);
__asm__(
	".set push\n.set noreorder\n.set hardfloat\n"
	".globl bar_sprite\n"
	".type bar_sprite, @function\n"
	"bar_sprite:\n"
	"	lw	$8, 16($29)\n"
	"	mtc1	$8, $f12\n"
	"	lw	$8, 20($29)\n"
	"	mtc1	$8, $f13\n"
	"	lw	$8, 24($29)\n"
	"	mtc1	$8, $f14\n"
	"	lw	$8, 28($29)\n"
	"	mtc1	$8, $f15\n"
	"	cvt.s.w	$f12, $f12\n"
	"	cvt.s.w	$f13, $f13\n"
	"	cvt.s.w	$f14, $f14\n"
	"	j	0x00110B70\n"
	"	cvt.s.w	$f15, $f15\n"
	".size bar_sprite, . - bar_sprite\n"
	".set pop\n");

/* page rectangle (x0, y0, W, H) -> 0x00110B70's texture arguments (game orientation: page x = v, page y = 256 - u - w) */
#define U_ARG(y0, H) (0x300u + 256u - (y0) - (H))
#define V_ARG(x0) (0x100u + (x0))

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
typedef void (*hud_str_fn)(const char *s, int row, int col, u32 colour);
#define HUD_STR ((hud_str_fn)0x00111460u)
static const char stage_blank[] = "              ";
static s32 bar_x = BAR_X;
#define ARRANGE_GAUGE ((void (*)(void))0x00129360u)

void bl_rank_bar(void)
{
	const u32 rank = EE_RAM(u32, RANK);
	const u32 tim = hud_tim2();
	u32 tint = 0x808080u, flags = 0x10000000u, alpha = 0, s, len, l2, col;
	s32 ox, oy;
	if (!art_present() || !tim) {
		ARRANGE_GAUGE();
		return;
	}
	HUD_STR(stage_blank, 37, 5, 0x80808000u);
	if (bar_painted_tim != tim || ((u8 *)(tim + 0x40u))[(FRAME_PY + 3u) * 256u + FRAME_PX + 40u] != bar_idx[3 * BAR_W + 40])
		paint(tim, 1);
	/* slide like BL (target 292, 16 px lower while a boss gauge is up) */
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
#ifdef BAR_TEST /* wrapper check: Arrange's gauge frame with Arrange's arguments */
	bar_sprite(0x10000000u, 852u, 256u, 0x808080u, 294 + ox, 120 + oy, 12, 120);
#endif
	/* frame (screen rows 0-5: game x bar_x + 1 .. + 6) and plate (rows 6-13: bar_x - 7 .. bar_x) */
	bar_sprite(flags, U_ARG(FRAME_PY, 6u), V_ARG(FRAME_PX), tint, bar_x + 1 + ox, BAR_Y + oy, 6, BAR_W);
	bar_sprite(flags, U_ARG(PLATE_PY, 8u), V_ARG(PLATE_PX), tint, bar_x - 7 + ox, BAR_Y + (s32)PLATE_C0 + oy, 8,
		   (s32)PLATE_W);
	/* fill: art x 5, rows 2-3 */
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
	bar_sprite(flags, U_ARG(FILL_PY, 2u), V_ARG(FILL_PX), col, bar_x + 3 + ox, BAR_Y + 5 + oy, 2, (s32)len);
}
