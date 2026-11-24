/* Timing probe for retail Arcade. A forced cadence tests the update path before calibration. */
#include "ibara_ps2.h"

#define ATTRACT 0x00338E7Cu
#define SCENE 0x00338E9Cu
#define TRANSITION 0x00338F40u
#define ARRANGE 0x00338F44u

#define PLAYER_STILL_HELD 0x250u
#define PLAYER_RELEASED 0x252u
#define SHOT_AND_BOMB 0x0030u
#ifdef SLOWDOWN_HARDWARE
#define PAD1_BUTTONS 0x00341FA0u
#define TOGGLE_BUTTONS 0x0A00u /* L2 | R2 in the retail pad word */
#endif
#ifdef SLOWDOWN_CAPTURE
#define PAD_BOMB 0x0020u
#define OUTER_LOOP 0x00338CDCu
#define GAMEPLAY_TICK 0x00338EA0u
#define PRACTICE 0x00338FA4u
#define ENEMY_BASE 0x0045A840u
#define ENEMY_STRIDE 0xB4u
#define ENEMY_COUNT 192u
#define ITEM_STRIDE 0x58u
#define ITEM_COUNT 256u
#define CAPTURE_BASE 0x000D0000u
#define CAPTURE_LIMIT 2048u
#define CADENCE_WORDS (CAPTURE_LIMIT / 32u)

struct workload_sample {
	u32 outer_loop;
	u32 gameplay_tick;
	u32 rank;
	s32 player_x;
	s32 player_y;
	u16 held_buttons;
	u16 released_buttons;
	u16 hostile_bullets;
	u16 active_enemies;
	u16 rose_pods;
	u16 active_items;
	u8 bombs;
	u8 holding;
	u8 scene;
	u8 flying_form;
};

_Static_assert(sizeof(struct workload_sample) == 36, "workload capture format");
_Static_assert(CAPTURE_BASE + CAPTURE_LIMIT * sizeof(struct workload_sample) <= PS2_CAVE_END,
	       "workload capture exceeds research cave");

#ifdef SLOWDOWN_CYCLES
#define CYCLE_BASE (CAPTURE_BASE + CAPTURE_LIMIT * sizeof(struct workload_sample))
struct cycle_marks {
	u32 simulation_start;
	u32 draw_start;
	u32 submit_start;
	u32 submit_end;
	u32 complete;
};
_Static_assert(sizeof(struct cycle_marks) == 20, "cycle capture format");
_Static_assert(CYCLE_BASE + CAPTURE_LIMIT * sizeof(struct cycle_marks) <= PS2_CAVE_END,
	       "cycle capture exceeds research cave");
volatile u32 arcade_slowdown_cycle_row;
#endif
#endif

struct pad_edges {
	u16 pressed;
	u16 released;
};

struct slowdown_probe {
	u32 signature;
	u32 enabled;
	u32 held_ticks;
	u32 holding;
	struct pad_edges pending[2];
#ifdef SLOWDOWN_HARDWARE
	u32 chord_down;
#endif
#ifdef SLOWDOWN_CAPTURE
	u32 capture_signature;
	u32 capture;
	u32 samples;
	u32 bomb_start;
	u32 bomb_release;
	u32 shot_ticks;
	u32 cadence_ticks;
	u32 cadence_holds[CADENCE_WORDS];
#endif
};

volatile struct slowdown_probe arcade_slowdown __attribute__((section(".hookhdr"))) = {
	.signature = 0x31574453u, /* SDW1 */
#if defined(SLOWDOWN_CYCLES)
	.capture_signature = 0x34544C53u, /* SLT4 */
#elif defined(SLOWDOWN_CAPTURE)
	.capture_signature = 0x33544C53u, /* SLT3 */
#endif
};

_Static_assert(__builtin_offsetof(struct slowdown_probe, holding) == 12, "slowdown rank stub field");

#ifdef ARCADE_SLOWDOWN_CONFIG
void arcade_slowdown_gate(void);
void arcade_slowdown_rank_gate(void);

void arcade_slowdown_apply(u32 active)
{
	/* Restore the two displaced retail branches while the option is off. */
	EE_RAM(u32, 0x0012E1E4u) = active ?
		0x08000000u | (((u32)arcade_slowdown_gate >> 2) & 0x03FFFFFFu) : 0x144000F9u;
	EE_RAM(u32, 0x0012E47Cu) = active ?
		0x08000000u | (((u32)arcade_slowdown_rank_gate >> 2) & 0x03FFFFFFu) : 0x14400022u;
	arcade_slowdown.enabled = 0;
	arcade_slowdown.holding = 0;
	arcade_slowdown.chord_down = 0;
	arcade_slowdown.pending[0] = (struct pad_edges){0};
	arcade_slowdown.pending[1] = (struct pad_edges){0};
}
#endif

#ifdef SLOWDOWN_CAPTURE
_Static_assert(__builtin_offsetof(struct slowdown_probe, capture_signature) == 0x18, "capture control format");
_Static_assert(__builtin_offsetof(struct slowdown_probe, cadence_ticks) == 0x30, "cadence control format");

static inline u32 scheduled_hold(u8 scene)
{
	if (scene != 7 || !EE_RAM(u32, PRACTICE))
		return 0;
	const u32 start = arcade_slowdown.bomb_release + 1u;
	const u32 offset = EE_RAM(u32, GAMEPLAY_TICK) - start;
	const u32 count = arcade_slowdown.cadence_ticks;
	if (offset >= count || offset >= CAPTURE_LIMIT)
		return 0;
	volatile u32 *word = &arcade_slowdown.cadence_holds[offset / 32u];
	const u32 bit = 1u << (offset % 32u);
	const u32 holds = *word;
	if (!(holds & bit))
		return 0;
	/* Consume the hold even if a native pause intervenes before this tick advances. */
	*word = holds & ~bit;
	return 1;
}

static inline void script_button(u32 bit, u32 tick, u32 start, u32 release)
{
	if (tick < start || tick > release)
		return;
	const u32 player = PS2_PLAYER_BASE;
	EE_RAM(u16, player + PS2_PLAYER_HELD) =
		(EE_RAM(u16, player + PS2_PLAYER_HELD) & ~bit) | (tick == release ? 0u : bit);
	EE_RAM(u16, player + PS2_PLAYER_PRESSED) =
		(EE_RAM(u16, player + PS2_PLAYER_PRESSED) & ~bit) | (tick == start ? bit : 0u);
	EE_RAM(u16, player + PLAYER_STILL_HELD) =
		(EE_RAM(u16, player + PLAYER_STILL_HELD) & ~bit) |
		(tick > start && tick < release ? bit : 0u);
	EE_RAM(u16, player + PLAYER_RELEASED) =
		(EE_RAM(u16, player + PLAYER_RELEASED) & ~bit) | (tick == release ? bit : 0u);
}

/* Supply the processed P1 pad bits just before an advancing Practice tick.
 * The retail code still handles the charge, bomb cost, and projectiles. */
static inline void script_practice_pad(u32 tick, u8 scene)
{
	const u32 start = arcade_slowdown.bomb_start;
	const u32 release = arcade_slowdown.bomb_release;
	if (!start || start >= release || scene != 7 || !EE_RAM(u32, PRACTICE) ||
	    !(EE_RAM(u32, PS2_PLAYER_BASE) & PLAYER_CAN_BE_HIT))
		return;

	script_button(PAD_BOMB, tick, start, release);
	const u32 shot_ticks = arcade_slowdown.shot_ticks;
	if (shot_ticks)
		script_button(PS2_PAD_SHOT, tick, start, release + shot_ticks);
}

static inline void record_workload(u8 scene, u32 holding)
{
	const u32 index = arcade_slowdown.samples;
	if (index >= CAPTURE_LIMIT)
		return;

	const u32 tick = EE_RAM(u32, GAMEPLAY_TICK);
	const u32 player = PS2_PLAYER_BASE;
	if (!holding)
		script_practice_pad(tick, scene);

	u16 hostile = 0;
	for (u32 i = 0; i < PS2_BULLET_COUNT; ++i) {
		const u32 flags = EE_RAM(u32, PS2_BULLETS_BASE + i * PS2_BULLET_STRIDE);
		hostile += (flags & (BULLET_CAN_HIT | BULLET_SEGMENT)) == BULLET_CAN_HIT;
	}

	u16 enemies = 0, pods = 0, items = 0;
	u8 flying_form = 0;
	for (u32 i = 0; i < ENEMY_COUNT; ++i) {
		const u32 addr = ENEMY_BASE + i * ENEMY_STRIDE;
		if (!(EE_RAM(u32, addr) & 0x80000000u))
			continue;
		const u32 type = EE_RAM(u32, addr + 4);
		const u32 subtype = EE_RAM(u32, addr + 8);
		++enemies;
		pods += type == 0x4Fu && subtype == 0;
		flying_form |= type == 0x4Au && subtype == 0xDu;
	}
	for (u32 i = 0; i < ITEM_COUNT; ++i)
		items += (EE_RAM(u32, PS2_ITEMS_BASE + i * ITEM_STRIDE) & 0x80000000u) != 0;

	volatile struct workload_sample *out = (volatile struct workload_sample *)CAPTURE_BASE + index;
	out->outer_loop = EE_RAM(u32, OUTER_LOOP);
	out->gameplay_tick = tick;
	out->rank = EE_RAM(u32, PS2_RANK_INV);
	out->player_x = EE_RAM(s32, player + PS2_PLAYER_X);
	out->player_y = EE_RAM(s32, player + PS2_PLAYER_Y);
	out->held_buttons = EE_RAM(u16, player + PS2_PLAYER_HELD);
	out->released_buttons = EE_RAM(u16, player + PLAYER_RELEASED);
	out->hostile_bullets = hostile;
	out->active_enemies = enemies;
	out->rose_pods = pods;
	out->active_items = items;
	out->bombs = EE_RAM(u8, player + PS2_PLAYER_BOMBS);
	out->holding = holding;
	out->scene = scene;
	out->flying_form = flying_form;
#ifdef SLOWDOWN_CYCLES
	volatile struct cycle_marks *marks = (volatile struct cycle_marks *)CYCLE_BASE + index;
	marks->complete = 0;
	arcade_slowdown_cycle_row = (u32)marks;
#endif
	arcade_slowdown.samples = index + 1;
}
#endif

u32 arcade_slowdown_step(u32 native_update)
{
	const u32 was_holding = arcade_slowdown.holding;
#ifdef SLOWDOWN_CYCLES
	arcade_slowdown_cycle_row = 0;
#endif
#ifdef SLOWDOWN_CAPTURE
	const u32 recording = arcade_slowdown.capture == 1;
#elif !defined(SLOWDOWN_HARDWARE)
	const u32 recording = 0;
#endif
#ifdef SLOWDOWN_HARDWARE
	const u32 down = (EE_RAM(u32, PAD1_BUTTONS) & TOGGLE_BUTTONS) == TOGGLE_BUTTONS;
	const u32 toggle = down && !arcade_slowdown.chord_down;
	arcade_slowdown.chord_down = down;
#else
	if (arcade_slowdown.enabled != 1 && !was_holding && !recording)
		return native_update;
#endif

	const u8 scene = EE_RAM(u8, SCENE);
	const u32 ships = EE_RAM(u32, PS2_PLAYER_BASE) |
			  EE_RAM(u32, PS2_PLAYER_BASE + PS2_PLAYER_STRIDE);

	arcade_slowdown.holding = 0;
	if (!native_update || scene < 2 || scene > 7 || EE_RAM(u8, ATTRACT) ||
	    EE_RAM(u32, ARRANGE) || EE_RAM(u32, TRANSITION) || !(ships & PLAYER_CAN_BE_HIT)) {
		arcade_slowdown.pending[0] = (struct pad_edges){0};
		arcade_slowdown.pending[1] = (struct pad_edges){0};
		return native_update;
	}

#ifdef SLOWDOWN_HARDWARE
	if (toggle)
		arcade_slowdown.enabled ^= 1u;
	if (arcade_slowdown.enabled != 1 && !was_holding)
		return native_update;
#endif
	const u32 enabled = arcade_slowdown.enabled == 1;
	u32 hold = enabled && !was_holding;
#ifdef SLOWDOWN_CAPTURE
	if (recording && !was_holding)
		hold |= scheduled_hold(scene);
	if (!hold && !was_holding) {
		if (recording)
			record_workload(scene, 0);
		return native_update;
	}
#endif

	u32 player = PS2_PLAYER_BASE;
	for (u32 side = 0; side < 2; ++side, player += PS2_PLAYER_STRIDE) {
		volatile struct pad_edges *pending = &arcade_slowdown.pending[side];
		if (hold) {
			pending->pressed = EE_RAM(u16, player + PS2_PLAYER_PRESSED) & SHOT_AND_BOMB;
			pending->released = EE_RAM(u16, player + PLAYER_RELEASED) & SHOT_AND_BOMB;
		} else {
			const u16 pressed = pending->pressed;
			const u16 released = pending->released;
			if (pressed) {
				EE_RAM(u16, player + PS2_PLAYER_PRESSED) |= pressed;
				EE_RAM(u16, player + PLAYER_STILL_HELD) &= ~pressed;
				EE_RAM(u16, player + PS2_PLAYER_HELD) |= pressed & PS2_PAD_SHOT;
			}
			if (released)
				EE_RAM(u16, player + PLAYER_RELEASED) |= released;
			*pending = (struct pad_edges){0};
		}
	}

	arcade_slowdown.holding = hold;
	arcade_slowdown.held_ticks += hold;
#ifdef SLOWDOWN_CAPTURE
	if (recording)
		record_workload(scene, hold);
#endif
	return !hold;
}

/* The jump replaces a branch in the middle of the retail loop. R5900 caller
 * registers can contain 128-bit values, so preserve them across the n32 call.
 */
__asm__(
	".set push\n"
	".set noreorder\n"
	".set noat\n"
	".text\n"
	".globl arcade_slowdown_gate\n"
	"arcade_slowdown_gate:\n"
	"addiu $sp,$sp,-288\n"
	"sq $1,0($sp)\n"
	"sq $2,16($sp)\n"
	"sq $3,32($sp)\n"
	"sq $4,48($sp)\n"
	"sq $5,64($sp)\n"
	"sq $6,80($sp)\n"
	"sq $7,96($sp)\n"
	"sq $8,112($sp)\n"
	"sq $9,128($sp)\n"
	"sq $10,144($sp)\n"
	"sq $11,160($sp)\n"
	"sq $12,176($sp)\n"
	"sq $13,192($sp)\n"
	"sq $14,208($sp)\n"
	"sq $15,224($sp)\n"
	"sq $24,240($sp)\n"
	"sq $25,256($sp)\n"
	"sq $ra,272($sp)\n"
	"jal arcade_slowdown_step\n"
	"move $4,$2\n"
	"move $24,$2\n"
	"lq $ra,272($sp)\n"
	"lq $25,256($sp)\n"
	"lq $15,224($sp)\n"
	"lq $14,208($sp)\n"
	"lq $13,192($sp)\n"
	"lq $12,176($sp)\n"
	"lq $11,160($sp)\n"
	"lq $10,144($sp)\n"
	"lq $9,128($sp)\n"
	"lq $8,112($sp)\n"
	"lq $7,96($sp)\n"
	"lq $6,80($sp)\n"
	"lq $5,64($sp)\n"
	"lq $4,48($sp)\n"
	"lq $3,32($sp)\n"
	"lq $2,16($sp)\n"
	"lq $1,0($sp)\n"
	"beqz $24,1f\n"
	"lq $24,240($sp)\n"
	"j 0x0012e5cc\n"
	"addiu $sp,$sp,288\n"
	"1: j 0x0012e1ec\n"
	"addiu $sp,$sp,288\n"
	".globl arcade_slowdown_rank_gate\n"
	"arcade_slowdown_rank_gate:\n"
	"bnez $2,2f\n"
	"nop\n"
	"lui $2,%hi(arcade_slowdown+12)\n"
	"lw $2,%lo(arcade_slowdown+12)($2)\n"
	"bnez $2,2f\n"
	"nop\n"
	"j 0x0012e484\n"
	"nop\n"
	"2: j 0x0012e508\n"
	"nop\n"
	".set pop\n"
);

#ifdef SLOWDOWN_CYCLES
/* Sample CP0 Count at the first simulation and draw calls, then bracket the
 * final draw call. The workload scan is outside the measured intervals. */
__asm__(
	".set push\n"
	".set noreorder\n"
	".macro slowdown_mark offset\n"
	"sq $8,0($sp)\n"
	"sq $9,16($sp)\n"
	"lui $8,%hi(arcade_slowdown_cycle_row)\n"
	"lw $8,%lo(arcade_slowdown_cycle_row)($8)\n"
	"beqz $8,1f\n"
	"nop\n"
	"mfc0 $9,$9\n"
	"nop\n"
	"sw $9,\\offset($8)\n"
	".if \\offset == 12\n"
	"addiu $9,$0,1\n"
	"sw $9,16($8)\n"
	"lui $8,%hi(arcade_slowdown_cycle_row)\n"
	"sw $0,%lo(arcade_slowdown_cycle_row)($8)\n"
	".endif\n"
	"1: lq $9,16($sp)\n"
	"lq $8,0($sp)\n"
	".endm\n"
	".macro slowdown_phase entry,retail,offset\n"
	".globl \\entry\n"
	"\\entry:\n"
	"addiu $sp,$sp,-32\n"
	"slowdown_mark \\offset\n"
	"j \\retail\n"
	"addiu $sp,$sp,32\n"
	".endm\n"
	"slowdown_phase arcade_slowdown_sim_start,0x00138cd0,0\n"
	"slowdown_phase arcade_slowdown_draw_start,0x00116c20,4\n"
	".globl arcade_slowdown_submit\n"
	"arcade_slowdown_submit:\n"
	"addiu $sp,$sp,-48\n"
	"sq $ra,32($sp)\n"
	"slowdown_mark 8\n"
	"jal 0x001117d0\n"
	"nop\n"
	"slowdown_mark 12\n"
	"lq $ra,32($sp)\n"
	"jr $ra\n"
	"addiu $sp,$sp,48\n"
	".purgem slowdown_phase\n"
	".purgem slowdown_mark\n"
	".set pop\n"
);
#endif
