/* TEST BUILDS ONLY (MC_TEST, research/phase46): exercises mcfile.c from the frontend.
 * After MC_TEST_DELAY frames in the frontend with the game's card manager idle: save a MC_TEST_SIZE-byte pattern as
 * REPLAY1.DAT, load it back and compare, save a second pattern over it, load and compare again, then save a small
 * second file. Results in mc_test[] (read from a savestate): step, then per stage (error, loaded size, mismatches).
 * MC_TEST_LOAD_ONLY: only load REPLAY1.DAT and check it against either pattern (after an interrupted save). */
#include "ibara_ps2.h"

#ifndef MC_TEST_DELAY
#define MC_TEST_DELAY 300u
#endif
#ifndef MC_TEST_SIZE
#define MC_TEST_SIZE 300000u
#endif
#define SRC ((u8 *)0x01C00000u)
#define DST ((u8 *)0x01D00000u)
#define MAIN_STATE 0x00338B08u

u32 mc_save(const char *name, const void *src, u32 size);
u32 mc_load(const char *name, void *dst, u32 max);
u32 mc_busy(void);
s32 mc_error(void);
u32 mc_done(void);
u32 mc_loaded(void);
void mc_tick(void);

u32 mc_test[32] = {0x5453434Du}; /* 'MCST', step, then 3 words per stage */
static u32 frames, stage;

static void fill(u32 seed)
{
	u32 i, x = seed;
	for (i = 0; i < MC_TEST_SIZE; i++) {
		x = x * 1103515245u + 12345u;
		SRC[i] = (u8)(x >> 16);
	}
}

static u32 compare(u32 seed)
{
	u32 i, x = seed, bad = 0;
	for (i = 0; i < MC_TEST_SIZE; i++) {
		x = x * 1103515245u + 12345u;
		bad += DST[i] != (u8)(x >> 16);
	}
	return bad;
}

/* mc_test[2 + 3k]: error of job k, [3 + 3k]: bytes loaded, [4 + 3k]: mismatches (loads) */
static void record(u32 k, u32 bad)
{
	mc_test[2 + k * 3] = (u32)mc_error() | (mc_done() ? 0x80000000u : 0u);
	mc_test[3 + k * 3] = mc_loaded();
	mc_test[4 + k * 3] = bad;
}

void mc_test_frame(void)
{
	mc_tick();
	if (EE_RAM(u32, MAIN_STATE) != 9u || frames < MC_TEST_DELAY) {
		frames++;
		return;
	}
	if (mc_busy())
		return;
	mc_test[1] = stage;
#ifdef MC_TEST_LOAD_ONLY
	if (stage == 0)
		mc_load("REPLAY1.DAT", DST, 0x00100000u);
	else if (stage == 1)
		record(0, compare(1u) << 16 | (compare(2u) & 0xFFFFu));
	else
		return;
#else
	/* jobs: 0 save pattern 1, 1 load, 2 save pattern 2 over it, 3 load, 4 save SETTINGS.DAT */
	switch (stage) {
	case 0: fill(1u); mc_save("REPLAY1.DAT", SRC, MC_TEST_SIZE); break;
	case 1: record(0, 0); mc_load("REPLAY1.DAT", DST, 0x00100000u); break;
	case 2: record(1, compare(1u)); fill(2u); mc_save("REPLAY1.DAT", SRC, MC_TEST_SIZE); break;
	case 3: record(2, 0); mc_load("REPLAY1.DAT", DST, 0x00100000u); break;
	case 4: record(3, compare(2u)); mc_save("SETTINGS.DAT", SRC, 4096u); break;
	case 5: record(4, 0); break;
	default: return;
	}
#endif
	stage++;
}
