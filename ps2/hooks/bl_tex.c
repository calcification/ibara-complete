/* Our own 16-bit texture pages for KURO's Black Label graphics (research/phase19-20).
 *
 * The game's textures are objects (page table 0x00341780: entry -> index t, objects 0x00339DB0 + t * 4) whose
 * upload descriptors are prebuilt GS packets: A+D (BITBLTBUF / TRXPOS / TRXREG / TRXDIR), then IMAGE from a
 * pointer, plus the TEX0 the sprite uses. GS texture memory is a cache: hundreds of pages share a few 260-block
 * slots and are uploaded when drawn. A 16-bit (PSMCT16, RGBA 5551 = the arcade's own pixel format) 256 x 128 page
 * is the same 64 KB as an 8-bit 256 x 256 page, so it fits a slot.
 *
 * ktex_init clones the HUD page's object and descriptors (page 3/1) as templates, makes them 16-bit 256 x 128 and
 * registers one object of ours (index KT_INDEX, unused by the loader, which stops at 1113 textures) under a free page
 * entry (row 1, col 5). Several pages share that object: a sprite keeps the descriptor it was drawn with
 * (0x001C9320), so ktex_draw points the object at the wanted page's descriptor before each call.
 * Pixel buffers: KT_PIXELS (0x01F20000-0x01F7FFFF, untouched by the game in play and on loads: the test loggers
 * used it through six stages). Leaf code (no s-registers).
 */
#include "ibara_ps2.h"

#define TEX_TABLE  0x00341780u
#define TEX_OBJS   0x00339DB0u
#define HUD_ENTRY  (1u * 32u + 3u)
#define KT_ENTRY   (1u * 32u + 5u) /* free in the retail table */
#define KT_INDEX   1114u           /* object slots 0-1112 are the loader's; 1113-1115 are zero */
#define KT_PIXELS  0x01F20000u
#define KT_PAGES   6u

static u32 kt_obj[64] __attribute__((aligned(16)));          /* clone of the HUD page object (0x100 bytes) */
static u32 kt_desc[KT_PAGES][64] __attribute__((aligned(16))); /* image upload descriptors, one per page */
static u32 kt_table[2];                                       /* object +0x24: [image descriptor, CLUT descriptor] */
static u32 kt_tex0[16] __attribute__((aligned(16)));          /* object +0x28 block (TEX0 + links) */
u32 kt_ready;

static void copy_words(u32 *dst, u32 src, u32 n)
{
	u32 i;
	for (i = 0; i < n; i++)
		dst[i] = EE_RAM(u32, src + 4u * i);
}

/* TEX0 for our PSMCT16 page at GS block dbp: TBW 4, PSM 2, TW 8, TH 8, TCC 1, TFX modulate, no CLUT. TH is 256
 * although only rows 0-127 are uploaded and used: 0x00110B70 maps texture coordinates in 256-pixel pages (TH 7 drew
 * the art twice as tall), and rows 0-127 of a 256-wide PSMCT16 texture are the same 64 KB of blocks either way. */
#define TEX0_LO(dbp) ((dbp) | 4u << 14 | 0x02u << 20 | 8u << 26 | (8u & 3u) << 30)
#define TEX0_HI      ((8u >> 2) | 1u << 2)

u16 *ktex_pixels(u32 page)
{
	return (u16 *)(KT_PIXELS + page * 0x10000u);
}

/* Build our object and descriptors from the HUD page's (once per KURO entry; the HUD page must be loaded). */
u32 ktex_init(void)
{
	const s32 hud = EE_RAM(s32, TEX_TABLE + HUD_ENTRY * 4u);
	u32 obj, di, dc, p, dbp;
	if (kt_ready)
		return 1;
	if (hud < 0)
		return 0;
	obj = EE_RAM(u32, TEX_OBJS + (u32)hud * 4u);
	if (obj < 0x00100000u || obj >= 0x02000000u)
		return 0;
	di = EE_RAM(u32, obj + 0x1Cu);
	dc = EE_RAM(u32, obj + 0x20u);
	if (di < 0x00100000u || di >= 0x02000000u || (EE_RAM(u32, di + 0x24u) >> 24) != 0x13u)
		return 0;
	dbp = EE_RAM(u32, di + 0x24u) & 0x3FFFu; /* the HUD page's cache slot */
	copy_words(kt_obj, obj, 64);
	copy_words(kt_tex0, EE_RAM(u32, obj + 0x28u), 16);
	for (p = 0; p < KT_PAGES; p++) {
		u32 *d = kt_desc[p];
		copy_words(d, di, 64);
		d[0] = KT_PIXELS + p * 0x10000u;                 /* IMAGE source */
		d[0x24 / 4] = 0x02u << 24 | 4u << 16 | dbp;      /* BITBLTBUF: PSMCT16, width 256, same slot */
		d[0x40 / 4] = 256u;                             /* TRXREG */
		d[0x44 / 4] = 128u;
		/* IMAGE tag (+0x60) and size words (+0x90): 64 KB, as the template */
		/* +0x70..: the texture size 0x001C9320 scales the 0-1 coordinates by: 256 x 256, as TEX0 (only the
		 * transfer, TRXREG above, is 128 rows; 128 here drew every row twice) */
		d[0x70 / 4] = 256u;
		d[0x74 / 4] = 256u;
		d[0x78 / 4] = 256u;
		d[0x7C / 4] = 256u;
		d[0x80 / 4] = 0x02u;                            /* PSM */
		d[0x88 / 4] = TEX0_LO(dbp);
		d[0x8C / 4] = TEX0_HI;
	}
	kt_tex0[0] = TEX0_LO(0);
	kt_tex0[1] = TEX0_HI;
	kt_table[0] = (u32)kt_desc[0];
	kt_table[1] = dc;
	kt_obj[0x1C / 4] = (u32)kt_desc[0];
	kt_obj[0x24 / 4] = (u32)kt_table;
	kt_obj[0x28 / 4] = (u32)kt_tex0;
	kt_obj[0x2C / 4] = (u32)kt_tex0;
	kt_obj[0x40 / 4] = TEX0_LO(0);
	kt_obj[0x44 / 4] = TEX0_HI;
	/* the object's copy of the TIM2 picture header (+0x70 'TIM2'): 16-bit image, no CLUT, its GsTex0 */
	kt_obj[0x84 / 4] = 0;                                   /* CLUT size */
	kt_obj[0x90 / 4] = (kt_obj[0x90 / 4] & 0x0000FFFFu) | 0x00u << 16 | 0x01u << 24; /* CLUT type none, 16-bit */
	kt_obj[0x98 / 4] = TEX0_LO(0);
	kt_obj[0x9C / 4] = TEX0_HI;
	kt_ready = 1;
	return 1;
}

/* (Re)register our object; returns 0 when the page entry is taken by the game. */
static u32 ktex_register(void)
{
	const s32 e = EE_RAM(s32, TEX_TABLE + KT_ENTRY * 4u);
	const s32 hud = EE_RAM(s32, TEX_TABLE + HUD_ENTRY * 4u);
	u32 obj;
	if (e != -1 && e != (s32)KT_INDEX)
		return 0;
	if (hud < 0)
		return 0;
	obj = EE_RAM(u32, TEX_OBJS + (u32)hud * 4u); /* its CLUT descriptor (a texture is drawn with two uploads) */
	if (obj < 0x00100000u || obj >= 0x02000000u)
		return 0;
	kt_table[1] = EE_RAM(u32, obj + 0x20u);
	EE_RAM(u32, TEX_OBJS + KT_INDEX * 4u) = (u32)kt_obj;
	EE_RAM(s32, TEX_TABLE + KT_ENTRY * 4u) = (s32)KT_INDEX;
	return 1;
}

/* Leaving KURO: the game's table as it was. */
void ktex_off(void)
{
	if (EE_RAM(s32, TEX_TABLE + KT_ENTRY * 4u) == (s32)KT_INDEX)
		EE_RAM(s32, TEX_TABLE + KT_ENTRY * 4u) = -1;
	EE_RAM(u32, TEX_OBJS + KT_INDEX * 4u) = 0;
}

void ktex_flush(void)
{
	__asm__ __volatile__("move $4, $0\n\tli $3, 100\n\tsyscall\n"
			     : : : "v0", "v1", "a0", "a1", "a2", "a3", "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8",
			       "t9", "memory");
}

/* 0x00110B70 with integer x, y, w, h (loaded into f12-f15). */
void ktex_sprite(u32 flags, u32 u, u32 v, u32 tint, s32 x, s32 y, s32 w, s32 h);
__asm__(
	".set push\n.set noreorder\n.set hardfloat\n"
	".globl ktex_sprite\n"
	".type ktex_sprite, @function\n"
	"ktex_sprite:\n"
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
	".size ktex_sprite, . - ktex_sprite\n"
	".set pop\n");

/* Draw page rectangle (px, py, pw, ph) of our page `page` (screen orientation: page x = screen x, page y = screen y)
 * at game x, y (x = the rectangle's lowest game x, i.e. its screen bottom edge; y = its screen left edge), with
 * 0x00110B70's flags and tint. Game orientation: w = ph (along game x), h = pw (along game y); u = 256 - py - ph. */
u32 ktex_draw(u32 page, u32 px, u32 py, u32 pw, u32 ph, u32 flags, u32 tint, s32 x, s32 y)
{
	if (!kt_ready || page >= KT_PAGES || !ktex_register())
		return 0;
	kt_table[0] = (u32)kt_desc[page];
	kt_obj[0x1C / 4] = (u32)kt_desc[page];
	ktex_sprite(flags, 0x500u + 256u - py - ph, 0x100u + px, tint, x, y, (s32)ph, (s32)pw);
	return 1;
}
