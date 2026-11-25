/* Our own 16-bit texture pages for Black Label (KURO) graphics (research/phase19-20).
 *
 * The game's textures are objects (page table 0x00341780: entry row * 32 + col -> index t, objects 0x00339DB0 +
 * t * 4) whose upload descriptors are prebuilt GS packets: A+D (BITBLTBUF / TRXPOS / TRXREG / TRXDIR), then IMAGE
 * from a pointer, plus the TEX0 the sprite uses. GS texture memory is a cache: hundreds of pages share a few
 * 260-block slots and are uploaded when drawn. A 16-bit (PSMCT16, RGBA 5551 = the arcade's own pixel format) 256 x 128
 * page is the same 64 KB as an 8-bit 256 x 256 page, so it fits a slot (the HUD page's).
 *
 * Every page of ours is a texture object of its own, cloned from the HUD page's object (page 3/1) with its own
 * descriptors and TEX0 block — as the game's own pages, which share cache slots (one object with its descriptor
 * swapped between sprites drew the wrong pixels).
 *  - KT_BAR (the rank bar, page 5's pixels): always registered, object index 1114 (the loader uses 0-1112; 1113-1115
 *    are zero) under the free entry row 1 / col 5.
 *  - pages 0-7 (the select screen, players 1 and 2): registered only while the select screen is up (ktex_claim /
 *    ktex_release: entries row 6 / cols 0-7, free in the retail table; object slots borrowed from the empty ones, the game update
 *    being stopped meanwhile, and given back).
 * Pixels at KT_PIXELS (0x01F20000-0x01F9FFFF: the select art segment loaded with the executable; page 5 rows 0-19 the
 * rank bar's, built at run time). Leaf code (no s-registers).
 */
#include "ibara_ps2.h"

#define TEX_TABLE  0x00341780u
#define TEX_OBJS   0x00339DB0u
#define TEX_SLOTS  1113u
#define HUD_ENTRY  (1u * 32u + 3u)
#define BAR_ENTRY  (1u * 32u + 5u)
#define BAR_INDEX  1114u
#define SEL_ROW    6u
#define KT_PIXELS  0x01F20000u
#define KT_PAGES   8u
#define KT_BAR     8u /* object slot of ours for the rank bar (after the select pages) */

struct ktex_obj {
	u32 obj[64];   /* clone of the HUD page object (0x100 bytes) */
	u32 desc[64];  /* image upload descriptor */
	u32 tex0[16];  /* object +0x28 block (TEX0 + links) */
	u32 tbl[2];    /* object +0x24: [image descriptor, CLUT descriptor] */
	u32 index;     /* object slot while registered */
} __attribute__((aligned(16)));
static struct ktex_obj kt[KT_PAGES + 1];
u32 kt_ready, kt_claimed;

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

static u32 hud_object(void)
{
	const s32 hud = EE_RAM(s32, TEX_TABLE + HUD_ENTRY * 4u);
	u32 obj;
	if (hud < 0)
		return 0;
	obj = EE_RAM(u32, TEX_OBJS + (u32)hud * 4u);
	return obj >= 0x00100000u && obj < 0x02000000u ? obj : 0;
}

static void clone(struct ktex_obj *k, u32 obj, u32 pixels, u32 dbp)
{
	u32 *d = k->desc;
	copy_words(k->obj, obj, 64);
	copy_words(k->tex0, EE_RAM(u32, obj + 0x28u), 16);
	copy_words(d, EE_RAM(u32, obj + 0x1Cu), 64);
	d[0] = pixels;                                /* IMAGE source */
	d[0x24 / 4] = 0x02u << 24 | 4u << 16 | dbp;   /* BITBLTBUF: PSMCT16, width 256, the HUD page's slot */
	d[0x40 / 4] = 256u;                           /* TRXREG: 256 x 128 */
	d[0x44 / 4] = 128u;
	/* +0x70..: the texture size 0x001C9320 scales the 0-1 coordinates by: 256 x 256, as TEX0 (128 there drew
	 * every row twice); IMAGE tag (+0x60) and size words (+0x90): 64 KB, as the template */
	d[0x70 / 4] = d[0x74 / 4] = d[0x78 / 4] = d[0x7C / 4] = 256u;
	d[0x80 / 4] = 0x02u;                          /* PSM */
	d[0x88 / 4] = TEX0_LO(dbp);
	d[0x8C / 4] = TEX0_HI;
	/* +0xC4: the GS cache slot it occupies (0x001B0450 writes it and the block address when it uploads); a texture
	 * not in GS memory reads -2. The clone must start there: with the HUD descriptor's slot copied, the cache
	 * manager took every clone for resident in that slot (no upload, wrong pixels) and its slot bookkeeping broke
	 * after a few hundred frames of several clones (a crash). */
	d[0xC4 / 4] = 0xFFFFFFFEu;
	/* the object (60 bytes) points (+0x28) at a header block: TEX0, two links to the descriptor table at block +0x10
	 * ([image, CLUT]); in the copy every link must lead to ours (with the HUD's links left in, half the game saw the
	 * HUD descriptors and the GS cache bookkeeping broke as soon as the stage's textures competed for slots) */
	k->tex0[0] = TEX0_LO(0);
	k->tex0[1] = TEX0_HI;
	k->tex0[2] = k->tex0[3] = (u32)&k->tex0[4];
	k->tex0[4] = (u32)d;
	k->tex0[5] = EE_RAM(u32, obj + 0x20u);
	k->tbl[0] = (u32)d;
	k->tbl[1] = EE_RAM(u32, obj + 0x20u);
	k->obj[0x1C / 4] = (u32)d;
	k->obj[0x24 / 4] = (u32)&k->tex0[4];
	k->obj[0x28 / 4] = (u32)k->tex0;
	k->obj[0x2C / 4] = (u32)k->tex0;
	k->obj[0x40 / 4] = TEX0_LO(0);
	k->obj[0x44 / 4] = TEX0_HI;
	/* the object's copy of the TIM2 picture header (+0x70 'TIM2'): 16-bit image, no CLUT, its GsTex0 */
	k->obj[0x84 / 4] = 0;
	k->obj[0x90 / 4] = (k->obj[0x90 / 4] & 0x0000FFFFu) | 0x01u << 24;
	k->obj[0x98 / 4] = TEX0_LO(0);
	k->obj[0x9C / 4] = TEX0_HI;
}

/* Build our objects from the HUD page's (once; the HUD page must be loaded). */
u32 ktex_init(void)
{
	u32 obj, di, dbp, p;
	if (kt_ready)
		return 1;
	obj = hud_object();
	if (!obj)
		return 0;
	di = EE_RAM(u32, obj + 0x1Cu);
	if (di < 0x00100000u || di >= 0x02000000u || (EE_RAM(u32, di + 0x24u) >> 24) != 0x13u)
		return 0;
	dbp = EE_RAM(u32, di + 0x24u) & 0x3FFFu;
	for (p = 0; p < KT_PAGES; p++)
		clone(&kt[p], obj, KT_PIXELS + p * 0x10000u, dbp);
	clone(&kt[KT_BAR], obj, KT_PIXELS + 5u * 0x10000u, dbp);
	kt[KT_BAR].index = BAR_INDEX;
	kt_ready = 1;
	return 1;
}

/* Keep the CLUT descriptor current (the HUD page may be reloaded) and the rank bar registered. */
static u32 refresh(void)
{
	const u32 obj = hud_object();
	const s32 e = EE_RAM(s32, TEX_TABLE + BAR_ENTRY * 4u);
	u32 p;
	if (!obj)
		return 0;
	for (p = 0; p <= KT_PAGES; p++) {
		kt[p].tbl[1] = EE_RAM(u32, obj + 0x20u);
		kt[p].tex0[5] = EE_RAM(u32, obj + 0x20u);
		kt[p].obj[0x20 / 4] = EE_RAM(u32, obj + 0x20u);
	}
	if (e != -1 && e != (s32)BAR_INDEX)
		return 0;
	EE_RAM(u32, TEX_OBJS + BAR_INDEX * 4u) = (u32)kt[KT_BAR].obj;
	EE_RAM(s32, TEX_TABLE + BAR_ENTRY * 4u) = (s32)BAR_INDEX;
	return 1;
}

/* Select screen: register pages 0-7 (row 6 entries, borrowed empty object slots). */
u32 ktex_claim(void)
{
	u32 p, slot = TEX_SLOTS;
	if (!kt_ready || kt_claimed)
		return kt_claimed;
	for (p = 0; p < KT_PAGES; p++)
		if (EE_RAM(s32, TEX_TABLE + (SEL_ROW * 32u + p) * 4u) != -1)
			return 0;
	for (p = 0; p < KT_PAGES; p++) {
		while (slot > 0 && EE_RAM(u32, TEX_OBJS + (slot - 1u) * 4u))
			slot--;
		if (!slot) {
			while (p--) {
				EE_RAM(u32, TEX_OBJS + kt[p].index * 4u) = 0;
				EE_RAM(s32, TEX_TABLE + (SEL_ROW * 32u + p) * 4u) = -1;
			}
			return 0;
		}
		kt[p].index = --slot;
		EE_RAM(u32, TEX_OBJS + slot * 4u) = (u32)kt[p].obj;
		EE_RAM(s32, TEX_TABLE + (SEL_ROW * 32u + p) * 4u) = (s32)slot;
	}
	kt_claimed = 1;
	return 1;
}

void ktex_release(void)
{
	u32 p;
	if (!kt_claimed)
		return;
	for (p = 0; p < KT_PAGES; p++) {
		if (EE_RAM(u32, TEX_OBJS + kt[p].index * 4u) == (u32)kt[p].obj)
			EE_RAM(u32, TEX_OBJS + kt[p].index * 4u) = 0;
		EE_RAM(s32, TEX_TABLE + (SEL_ROW * 32u + p) * 4u) = -1;
	}
	kt_claimed = 0;
}

/* Leaving KURO: the game's table as it was. */
void ktex_off(void)
{
	ktex_release();
	if (EE_RAM(s32, TEX_TABLE + BAR_ENTRY * 4u) == (s32)BAR_INDEX)
		EE_RAM(s32, TEX_TABLE + BAR_ENTRY * 4u) = -1;
	EE_RAM(u32, TEX_OBJS + BAR_INDEX * 4u) = 0;
}

void ktex_flush(void)
{
	__asm__ __volatile__("move $4, $0\n\tli $3, 100\n\tsyscall\n"
			     : : : "v0", "v1", "a0", "a1", "a2", "a3", "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8",
			       "t9", "memory");
}

/* 0x00110B70 with integer x, y, w, h (n32: arguments 5-8 arrive in $8-$11; loaded into f12-f15). Our frames are
 * 16-byte aligned (n32), as the game's code needs. */
void ktex_sprite(u32 flags, u32 u, u32 v, u32 tint, s32 x, s32 y, s32 w, s32 h);
__asm__(
	".set push\n.set noreorder\n.set hardfloat\n"
	".globl ktex_sprite\n"
	".type ktex_sprite, @function\n"
	"ktex_sprite:\n"
	"	mtc1	$8, $f12\n"
	"	mtc1	$9, $f13\n"
	"	mtc1	$10, $f14\n"
	"	mtc1	$11, $f15\n"
	"	cvt.s.w	$f12, $f12\n"
	"	cvt.s.w	$f13, $f13\n"
	"	cvt.s.w	$f14, $f14\n"
	"	j	0x00110B70\n"
	"	cvt.s.w	$f15, $f15\n"
	".size ktex_sprite, . - ktex_sprite\n"
	".set pop\n");

/* Draw page rectangle (px, py, pw, ph) (screen orientation: page x = screen x, page y = screen y) at game x, y
 * (x = the rectangle's lowest game x, i.e. its screen bottom edge; y = its screen left edge), with 0x00110B70's
 * flags and tint. Game orientation: w = ph (along game x), h = pw (along game y); u = 256 - py - ph.
 * page 0-7: the select screen's (claimed); KT_BAR: the rank bar's object (page 5 pixels). */
u32 ktex_draw(u32 page, u32 px, u32 py, u32 pw, u32 ph, u32 flags, u32 tint, s32 x, s32 y)
{
	u32 col, row;
	if (!kt_ready || page > KT_PAGES || !refresh())
		return 0;
	if (page == KT_BAR) {
		col = BAR_ENTRY % 32u;
		row = BAR_ENTRY / 32u;
	} else {
		if (!kt_claimed)
			return 0;
		col = page;
		row = SEL_ROW;
	}
	ktex_sprite(flags, col << 8 | (256u - py - ph), row << 8 | px, tint, x, y, (s32)ph, (s32)pw);
	return 1;
}
