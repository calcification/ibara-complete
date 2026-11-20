/* TEST BUILDS ONLY (--define BL_SPAWN_LOG): PS2 enemy-spawn logger for stage comparisons with BL (MAME).
 *
 * Every logic frame (called from xtc_frame): keeps P1 invincible and records each newly alive enemy part of
 * the PS2 pool 0x0045A840 (192 x 0xB4; +00 flags bit 31 alive, +04 type, +08 subtype, +24/+28 x/y 16.16,
 * +3C hp, +40 score) into a log at SPAWN_LOG (count word, then 24-byte records). Read it from a savestate.
 */
#include "ibara_ps2.h"

#ifdef BL_SPAWN_LOG
#define EN_BASE 0x0045A840u
#define EN_STRIDE 0xB4u
#define EN_COUNT 192u
#define SPAWN_LOG 0x01F20000u
#define SPAWN_MAX 2600u

struct spawn_rec {
	u32 frame;
	u16 slot, hp;
	u32 type, subtype, score;
	s16 x, y;
};

static u32 sl_frame, sl_first, sl_started;
static u32 sl_type[EN_COUNT];
static u8 sl_alive[EN_COUNT];

void spawn_log_frame(void)
{
	volatile u32 *count = (volatile u32 *)SPAWN_LOG;
	struct spawn_rec *log = (struct spawn_rec *)(SPAWN_LOG + 16);
	unsigned i;

	sl_frame++;
	if (EE_RAM(u32, PS2_PLAYER_BASE + PS2_PLAYER_FLAGS) != 0)
		EE_RAM(u8, PS2_PLAYER_BASE + PS2_PLAYER_INVINCIBLE) = 240;
	if (!sl_started) {
		*count = 0;
		sl_started = 1;
	}
	for (i = 0; i < EN_COUNT; i++) {
		const u32 a = EN_BASE + i * EN_STRIDE;
		const u32 fl = EE_RAM(u32, a);
		const u32 t = EE_RAM(u32, a + 4);
		const int on = (fl & 0x80000000u) != 0;
		if (on && (!sl_alive[i] || sl_type[i] != t) && *count < SPAWN_MAX) {
			struct spawn_rec *r = &log[*count];
			if (!sl_first)
				sl_first = sl_frame;
			r->frame = sl_frame - sl_first;
			r->slot = (u16)i;
			r->hp = EE_RAM(u16, a + 0x3C);
			r->type = t;
			r->subtype = EE_RAM(u32, a + 8);
			r->score = EE_RAM(u32, a + 0x40);
			r->x = (s16)(EE_RAM(s32, a + 0x24) >> 16);
			r->y = (s16)(EE_RAM(s32, a + 0x28) >> 16);
			(*count)++;
		}
		sl_alive[i] = (u8)on;
		sl_type[i] = t;
	}
}
#endif
