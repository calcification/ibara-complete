/* Stage 6 measurement build. The launcher and production hooks never enable this file. */
#include "ibara_ps2.h"

#define STAGE_COUNT 0x00338E9Cu
#define ROSE_STAGE 7u
#define BULLET_PALETTE_INDEX 0x00338E94u
#define ROSE_TEST_BASE 0x01F5E000u
#define ROSE_TEST_MAGIC 0x31534F52u /* ROS1 */

struct rose_test {
	u32 magic;
	u32 mode; /* bit 0: extra bullet, bit 1: rank-adjusted rose group size */
	u32 rose_attempts;
	u32 barrage_calls;
	u32 palette_misses;
#ifdef BL_ROSE_BATCH
	u32 requested_seed;
	u32 applied_seed;
	u32 seed_tick;
	u32 burst_frames;
	u32 last_burst_tick;
#endif
};

static volatile struct rose_test *const test = (volatile struct rose_test *)ROSE_TEST_BASE;

typedef u32 (*rose_create_fn)(u32, u32, u32, u32, u32, u32, u32);
typedef u32 (*bullet_emit_fn)(u32, u32, u32, u32, u32, const s16 *);
static const s16 single_bullet[] = {1, 0};

u32 bl_rose_probe_create(u32 part, u32 kind, u32 x, u32 y, u32 visual, u32 angle, u32 tilt)
{
	const u32 result = ((rose_create_fn)0x00163140u)(part, kind, x, y, visual, angle, tilt);

	if (EE_RAM(u8, STAGE_COUNT) != ROSE_STAGE)
		return result;
	test->rose_attempts++;
#ifdef BL_ROSE_BATCH
	const u32 tick = EE_RAM(u32, 0x00338EA0u);
	if (tick != test->last_burst_tick) {
		test->burst_frames++;
		test->last_burst_tick = tick;
	}
#endif
	if (!(test->mode & 1u))
		return result;

	/* The native emitter picks the projectile from its normal stage palette. Only count on
	 * the type-14 mapping measured for this comparison. Do not change the global palette.
	 */
	const u32 index = EE_RAM(u8, BULLET_PALETTE_INDEX);
	if (index > 4u || EE_RAM(u32, 0x00201474u + index * 4u) != 14u) {
		test->palette_misses++;
		return result;
	}
	test->barrage_calls++;
	((bullet_emit_fn)0x00123950u)(5, x, y, angle, 0x2C000u, single_bullet);
	return result;
}

void bl_rose_probe_players(void)
{
	static u8 was_shooting;
	const u32 p1 = PS2_PLAYER_BASE;
	const u8 shooting = EE_RAM(u8, STAGE_COUNT) == ROSE_STAGE && EE_RAM(u32, p1) != 0;
	if (test->magic != ROSE_TEST_MAGIC) {
		test->mode = test->rose_attempts = test->barrage_calls = test->palette_misses = 0;
#ifdef BL_ROSE_MODE /* trial mode built in, for runs without the PINE runner */
		test->mode = BL_ROSE_MODE;
#endif
#ifdef BL_ROSE_BATCH
		test->requested_seed = test->applied_seed = test->seed_tick = 0;
		test->burst_frames = test->last_burst_tick = 0;
#endif
		test->magic = ROSE_TEST_MAGIC;
	}
#ifdef BL_ROSE_BATCH
	if (shooting && !test->seed_tick && test->requested_seed != 0
	    && EE_RAM(u32, 0x00338EA0u) == 10000u) {
		test->applied_seed = test->requested_seed;
		test->seed_tick = 10000u;
		EE_RAM(u32, 0x00337D08u) = test->applied_seed;
	}
#elif defined(BL_ROSE_SEED) /* repeat trials (research/phase33): the game's random seed ($gp-32744), once, before the first core */
	{
		static u8 seeded;
		if (!seeded && EE_RAM(u8, STAGE_COUNT) == ROSE_STAGE && EE_RAM(u32, 0x00338EA0u) >= 10000u) {
			EE_RAM(u32, 0x00337D08u) = BL_ROSE_SEED;
			seeded = 1;
		}
	}
#endif
	if (shooting) {
		/* Supply the processed inputs immediately before the native player update. */
		EE_RAM(u16, p1 + PS2_PLAYER_HELD) = PS2_PAD_SHOT;
		EE_RAM(u16, p1 + PS2_PLAYER_PRESSED) = was_shooting ? 0 : PS2_PAD_SHOT;
		EE_RAM(u16, p1 + 0x250u) = was_shooting ? PS2_PAD_SHOT : 0;
		EE_RAM(u16, p1 + 0x252u) = 0;
	}
	was_shooting = shooting;
	GAME_CALL0(0x0013AB30u);
}

/* The three retail initializers have already loaded rank in the jump delay
 * slot. Only the size calculation sees the adjusted value. At default Black
 * Label difficulty 3 the bias is stage * 0x100000, also used by bl_fire_timer.
 */
__asm__(
	".set push\n.set noreorder\n.set noat\n"
	".macro rose_group name, rank, constant, resume\n"
	".globl \\name\n"
	"\\name:\n"
	"	li \\constant,16\n"
	"	lui $1,0x01F6\n"
	"	lw $1,-8188($1)\n" /* ROSE_TEST_BASE + offsetof(mode) */
	"	andi $1,$1,2\n"
	"	beq $1,$0,1f\n"
	"	nop\n"
	"	lbu $1,-28244($28)\n"
	"	sll $1,$1,20\n"
	"	subu \\rank,\\rank,$1\n"
	"	bgez \\rank,1f\n"
	"	nop\n"
	"	move \\rank,$0\n"
	"1:	j \\resume\n"
	"	nop\n"
	".endm\n"
	"rose_group bl_rose_group_1,$3,$4,0x00178DEC\n"
	"rose_group bl_rose_group_2,$2,$3,0x00178EB8\n"
	"rose_group bl_rose_group_3,$2,$3,0x0017905C\n"
	".purgem rose_group\n"
	".set pop\n");
