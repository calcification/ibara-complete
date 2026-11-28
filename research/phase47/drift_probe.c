/* Source-only instrumentation for the release recorder and REPLAY menu. */
#include "ibara_ps2.h"

#define UPDATES 1200u
#define RNG_CALLS 8u
#define ROWS ((volatile struct trace_row (*)[UPDATES])0x01E00000u)

struct trace_row {
	u32 marker, tick, seed, score, x, y, input;
	u32 script, scroll, slot_flags, slot_type;
	u32 calls, made, checks, ready, allocs, allocated;
	u32 gate_calls, gate_ready, gate_status;
	u32 rng_count, rng_hash, rng_callers[RNG_CALLS];
};
_Static_assert(sizeof(struct trace_row) == 120u, "trace row layout");
_Static_assert(2u * UPDATES * sizeof(struct trace_row) < 0x80000u, "keep clear of memory-card workspace");

static volatile struct trace_row *current;
static u32 playing, holding;
volatile u32 drift_gate_recorded, drift_gate_target;
volatile u32 drift_gate_holds, drift_gate_blocks;

#define GATE_COMMAND 0x001EB03Eu
#define GATE_STATUS 0x00448700u
#define GATE_EMPTY 0x0800u
#define GATE_MAX_HOLD 120u

void drift_sample(u32 playback, u32 update, const u16 *input, u32 count)
{
	const u32 slot = 0x0045A840u + 3u * 0xB4u;
	u32 hash = 0;
	current = 0;
	if (update >= UPDATES || EE_RAM(u8, 0x00338E9Cu) != 2u)
		return;
	playing = playback;
	current = &ROWS[playback][update];
	current->gate_calls = current->gate_ready = current->gate_status = 0;
	current->calls = current->made = current->checks = current->ready = 0;
	current->allocs = current->allocated = current->rng_count = current->rng_hash = 0;
	for (u32 i = 0; i < count; i++)
		hash = hash * 16777619u ^ input[i];
	current->marker = update + 1u;
	current->tick = EE_RAM(u32, 0x00338EA0u);
	current->seed = EE_RAM(u32, 0x00337D08u);
	current->score = EE_RAM(u32, PS2_PLAYER_BASE + PS2_PLAYER_SCORE);
	current->x = EE_RAM(u32, PS2_PLAYER_BASE + PS2_PLAYER_X);
	current->y = EE_RAM(u32, PS2_PLAYER_BASE + PS2_PLAYER_Y);
	current->input = hash;
	current->script = EE_RAM(u32, 0x00338E00u);
	current->scroll = EE_RAM(u32, 0x00338DD0u);
	current->slot_flags = EE_RAM(u32, slot);
	current->slot_type = EE_RAM(u32, slot + 4u);
}

void drift_stop(void)
{
	current = 0;
}

/* Script command FF27 tries again until the texture queue is empty.
 * The control leaves the loader alone and aligns this decision only. */
u32 drift_gate(void)
{
	const u16 status = EE_RAM(u16, GATE_STATUS);
	const u32 ready = GAME_CALL0(0x00114820u);
	if (EE_RAM(u32, 0x00338E00u) != GATE_COMMAND + 4u)
		return ready;
	/* The draw path can also call the stage interpreter. Keep its
	 * cursor parked until the held replay update is allowed to run. */
	if (holding)
		return 0;
	if (!current || current->script != GATE_COMMAND)
		return ready;
	current->gate_calls++;
	current->gate_ready += ready != 0;
	current->gate_status = status;
	if (!playing && ready)
		drift_gate_recorded = current->marker;
	if (playing && ready && drift_gate_target && current->marker < drift_gate_target) {
		drift_gate_blocks++;
		return 0;
	}
	return ready;
}

u32 drift_gate_may_update(u32 update)
{
	holding = 0;
	if (update == drift_gate_target && EE_RAM(u32, 0x00338E00u) == GATE_COMMAND &&
	    EE_RAM(u16, GATE_STATUS) != GATE_EMPTY && drift_gate_holds < GATE_MAX_HOLD) {
		drift_stop();
		holding = 1;
		drift_gate_holds++;
		return 0;
	}
	return 1;
}

u32 drift_create(void)
{
	const u32 result = GAME_CALL0(0x00163350u);
	if (current) {
		current->calls++;
		current->made += result != 0;
	}
	return result;
}

u32 drift_resources(u32 kind, u32 flags)
{
	const u32 result = GAME_CALL2(0x00135D70u, kind, flags);
	if (current) {
		current->checks++;
		current->ready += result != 0;
	}
	return result;
}

u32 drift_slots(u32 count)
{
	const u32 result = ((u32 (*)(u32))0x0012D280u)(count);
	if (current) {
		current->allocs++;
		current->allocated += result != 0;
	}
	return result;
}

void drift_random(u32 return_address)
{
	if (!current)
		return;
	const u32 index = current->rng_count++;
	if (index < RNG_CALLS)
		current->rng_callers[index] = return_address - 8u;
	current->rng_hash = current->rng_hash * 16777619u ^ return_address;
}

/* At the RNG routine's division call, the seed has advanced and the
 * RNG's original caller is at the top of its own stack frame. */
__asm__(
	".set push\n.set noreorder\n"
	".globl drift_rng_entry\n"
	"drift_rng_entry:\n"
	"	addiu $sp,$sp,-0xE0\n"
	"	sq $ra,0x00($sp)\n"
	"	sq $s0,0x10($sp)\n"
	"	sq $s1,0x20($sp)\n"
	"	sq $s2,0x30($sp)\n"
	"	sq $s3,0x40($sp)\n"
	"	sq $s4,0x50($sp)\n"
	"	sq $s5,0x60($sp)\n"
	"	sq $s6,0x70($sp)\n"
	"	sq $s7,0x80($sp)\n"
	"	sq $fp,0x90($sp)\n"
	"	sq $gp,0xA0($sp)\n"
	"	sq $a0,0xB0($sp)\n"
	"	sq $a1,0xC0($sp)\n"
	"	jal drift_random\n"
	"	ld $a0,0xE0($sp)\n"
	"	lq $a1,0xC0($sp)\n"
	"	lq $a0,0xB0($sp)\n"
	"	lq $gp,0xA0($sp)\n"
	"	lq $fp,0x90($sp)\n"
	"	lq $s7,0x80($sp)\n"
	"	lq $s6,0x70($sp)\n"
	"	lq $s5,0x60($sp)\n"
	"	lq $s4,0x50($sp)\n"
	"	lq $s3,0x40($sp)\n"
	"	lq $s2,0x30($sp)\n"
	"	lq $s1,0x20($sp)\n"
	"	lq $s0,0x10($sp)\n"
	"	lq $ra,0x00($sp)\n"
	"	j 0x00160310\n"
	"	addiu $sp,$sp,0xE0\n"
	".set pop\n"
);
