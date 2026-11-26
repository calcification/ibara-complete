/* Test-only, Stage 2 pod projectile census. */
#include "ibara_ps2.h"

#define POD_AUDIT 0x01F5E000u
#define POD_MAGIC 0x31444F50u /* POD1 */
#define POD_BASE 0x0044C8A0u
#define SHOT_BASE 0x0044D6C0u
#define STAGE 0x00338E9Cu
#define TICK 0x00338EA0u

struct pod_audit {
	u32 magic, weapon, seed, applied_weapon, applied_seed;
	u32 exposure, attempts, successful, sampled, occupied, mismatch;
	s32 x, y;
	u32 ship;
};

static volatile struct pod_audit *const audit = (volatile struct pod_audit *)POD_AUDIT;

static void equip(u32 weapon)
{
	const u32 p1 = PS2_PLAYER_BASE;
	unsigned i;
	EE_RAM(u8, p1 + 0x270) = weapon;
	for (i = 0; i < 3; ++i) {
		const u32 pod = POD_BASE + 0x30u * i;
		EE_RAM(u8, p1 + 0x26D + i) = 2 * weapon;
		EE_RAM(u32, pod + 4) = 2 * weapon;
		EE_RAM(u32, pod + 16) = 2 * weapon;
		EE_RAM(u32, pod + 8) = EE_RAM(u32, pod + 12) = 0;
		EE_RAM(u8, pod + 42) = EE_RAM(u8, pod + 43) = 0;
	}
	audit->applied_weapon = weapon;
}

#ifdef BL_POD_AUDIT_LIFETIME
#define POD_TRACE 0x01F80000u

struct pod_trace_row {
	u8 slot[48]; /* zero is free, active kind plus one, 255 for other occupied flags */
	u16 target[3], desired[3], angle[3];
};
_Static_assert(sizeof(struct pod_trace_row) == 66, "pod trace row layout");

static void trace_slots(u32 tick)
{
	volatile struct pod_trace_row *row = (volatile struct pod_trace_row *)POD_TRACE + tick - 2500u;
	unsigned i;

	for (i = 0; i < 48; i++) {
		const u32 shot = SHOT_BASE + 0x34u * i;
		const u32 flags = EE_RAM(u32, shot);
		const u32 kind = EE_RAM(u32, shot + 4);
		row->slot[i] = flags == 0 ? 0 : flags >> 30 == 3 && kind < 254 ? kind + 1 : 255;
	}
	for (i = 0; i < 3; i++) {
		const u32 pod = POD_BASE + 48u * i;
		row->target[i] = EE_RAM(u16, pod + 40);
		row->desired[i] = EE_RAM(u16, pod + 38) & 511u;
		row->angle[i] = EE_RAM(u16, pod + 36) & 511u;
	}
}
#endif

static void sample(u32 tick)
{
	static u8 alive[48];
	const u32 shot_kind = audit->applied_weapon == 6 ? 2u : audit->applied_weapon == 3 ? 4u : 7u;
	const u32 p1 = PS2_PLAYER_BASE;
	unsigned i;

	if (tick >= 2500u) {
#ifdef BL_POD_AUDIT_LIFETIME
		trace_slots(tick);
#endif
		audit->exposure++;
		if (EE_RAM(u8, p1 + PS2_PLAYER_POD_COUNT) != 3 ||
		    EE_RAM(u8, p1 + 0x270) != audit->applied_weapon)
			audit->mismatch++;
		for (i = 0; i < 3; ++i)
			if (EE_RAM(u32, POD_BASE + 0x30u * i + 4) != 2 * audit->applied_weapon)
				audit->mismatch++;
		if (tick == 2500u) {
			audit->x = EE_RAM(s32, p1 + PS2_PLAYER_X);
			audit->y = EE_RAM(s32, p1 + PS2_PLAYER_Y);
			audit->ship = EE_RAM(u32, p1 + 4);
		}
	}
	for (i = 0; i < 48; ++i) {
		const u32 shot = SHOT_BASE + 0x34u * i;
		const u8 on = (EE_RAM(u32, shot) >> 30) == 3u && EE_RAM(u32, shot + 4) == shot_kind;
		if (on && tick >= 2500u) {
			audit->occupied++;
			if (!alive[i])
				audit->sampled++;
		}
		alive[i] = on;
	}
}

_Static_assert(__builtin_offsetof(struct pod_audit, attempts) == 24, "assembly attempts offset");
_Static_assert(__builtin_offsetof(struct pod_audit, successful) == 28, "assembly successes offset");

#ifdef BL_POD_AIM_TRACE
#define AIM_CONTROL (POD_AUDIT + 0x100u)
#define AIM_FIRST 2400u
#define AIM_FRAMES 800u

struct aim_row {
	s32 x, y;
	u16 held, angle[3], desired[3], target[3];
};
_Static_assert(sizeof(struct aim_row) == 28, "homing trace record");
static volatile struct aim_row *const aim_rows =
	(volatile struct aim_row *)(AIM_CONTROL + 4u);

static u16 aim_buttons(u32 tick)
{
	static const u8 directions[] = {0, 1, 5, 4, 6, 2, 10, 8, 9, 0};
	unsigned index = (tick - AIM_FIRST) / 20u;

	return PS2_PAD_SHOT | (index < sizeof(directions) ? directions[index] : 0);
}

static void aim_sample(u32 tick, u32 player)
{
	volatile struct aim_row *row = &aim_rows[tick - AIM_FIRST];
	unsigned i;

	row->x = EE_RAM(s32, player + PS2_PLAYER_X);
	row->y = EE_RAM(s32, player + PS2_PLAYER_Y);
	row->held = EE_RAM(u16, player + PS2_PLAYER_HELD);
	for (i = 0; i < 3; i++) {
		const u32 pod = POD_BASE + 48u * i;
		row->angle[i] = EE_RAM(u16, pod + 36) & 511u;
		row->desired[i] = EE_RAM(u16, pod + 38) & 511u;
		row->target[i] = EE_RAM(u16, pod + 40);
	}
}
#endif

void bl_pod_audit_players(void)
{
	static u8 was_shooting;
	const u32 p1 = PS2_PLAYER_BASE;
	const u32 tick = EE_RAM(u32, TICK);
	const u8 playing = EE_RAM(u8, STAGE) == 3 && EE_RAM(u32, p1 + PS2_PLAYER_FLAGS) != 0;
	if (playing) {
		if (audit->magic != POD_MAGIC) {
			*audit = (struct pod_audit){0};
			audit->magic = POD_MAGIC;
		}
		if (tick == 1200u && (audit->weapon == 3 || audit->weapon == 4 || audit->weapon == 6))
			equip(audit->weapon);
		if (tick == 2000u && audit->seed) {
			audit->applied_seed = audit->seed;
			EE_RAM(u32, 0x00337D08u) = audit->applied_seed;
		}
#if defined(BL_POD_AUDIT_EMPTY) || defined(BL_POD_AIM_TRACE)
		if (tick >= 1200u && tick < 3500u
#ifndef BL_POD_AUDIT_EMPTY
		    && (EE_RAM(u32, AIM_CONTROL) & 1u)
#endif
		    ) {
			unsigned i;
			for (i = 0; i < 192; ++i)
				EE_RAM(u32, 0x0045A840u + 0xB4u * i) = 0;
		}
#endif
#ifdef BL_POD_AIM_TRACE
		{
			const u16 held = aim_buttons(tick);
			const u16 previous = was_shooting ? aim_buttons(tick - 1u) : 0;
			EE_RAM(u16, p1 + PS2_PLAYER_HELD) = held;
			EE_RAM(u16, p1 + PS2_PLAYER_PRESSED) = held & ~previous;
			EE_RAM(u16, p1 + 0x250u) = held & previous;
			EE_RAM(u16, p1 + 0x252u) = previous & ~held;
		}
#else
		EE_RAM(u16, p1 + PS2_PLAYER_HELD) = PS2_PAD_SHOT;
		EE_RAM(u16, p1 + PS2_PLAYER_PRESSED) = was_shooting ? 0 : PS2_PAD_SHOT;
		EE_RAM(u16, p1 + 0x250u) = was_shooting ? PS2_PAD_SHOT : 0;
		EE_RAM(u16, p1 + 0x252u) = 0;
#endif
		EE_RAM(u8, p1 + PS2_PLAYER_INVINCIBLE) = 240;
		EE_RAM(u8, p1 + PS2_PLAYER_LIVES + 1) = 2;
		EE_RAM(u32, PS2_RANK_INV) = 0x800000u;
	}
	was_shooting = playing;
	GAME_CALL0(0x0013AB30u);
	if (playing && tick >= 2499u && tick < 3500u)
		sample(tick);
#ifdef BL_POD_AIM_TRACE
	if (playing && audit->applied_weapon == 3 && tick >= AIM_FIRST && tick < AIM_FIRST + AIM_FRAMES)
		aim_sample(tick, p1);
#endif
}

__asm__(
	".text\n.set push\n.set noreorder\n.set noat\n"
	".globl bl_pod_audit_allocation\n"
	"bl_pod_audit_allocation:\n"
	"  addiu $29,$29,-64\n"
	"  sd $31,48($29)\n"
	"  jal 0x0012D050\n"
	"  nop\n"
	"  sq $8,0($29)\n"
	"  sq $9,16($29)\n"
	"  sq $10,32($29)\n"
	"  lui $8,0x34\n"
	"  lbu $9,-29028($8)\n"
	"  li $10,3\n"
	"  bne $9,$10,2f\n"
	"  lw $9,-29024($8)\n"
	"  addiu $9,$9,-2500\n"
	"  sltiu $9,$9,1000\n"
	"  beq $9,$0,2f\n"
	"  lui $8,0x01F6\n"
	"  lw $9,-8168($8)\n" /* POD_AUDIT + offsetof(attempts) */
	"  addiu $9,$9,1\n"
	"  sw $9,-8168($8)\n"
	"  lw $9,-8164($8)\n"
	"  addu $9,$9,$2\n" /* native return is 1 for success, 0 for no room */
	"  sw $9,-8164($8)\n"
	"2:\n"
	"  lq $8,0($29)\n"
	"  lq $9,16($29)\n"
	"  lq $10,32($29)\n"
	"  ld $31,48($29)\n"
	"  jr $31\n"
	"  addiu $29,$29,64\n"
	".set pop\n");

/* A/B only. In the no-target branch, reproduce the arcade's stationary
 * homing formation. Keep native handling for moving players and other weapons. */
#ifdef BL_POD_AUDIT_FALLBACK
__asm__(
	".text\n.set push\n.set noreorder\n.set noat\n"
	".globl bl_pod_audit_fallback\n"
	"bl_pod_audit_fallback:\n"
	"  lhu $1,40($16)\n" /* the native target id is >= 192 on a miss */
	"  sltiu $1,$1,192\n"
	"  bne $1,$0,1f\n"
	"  nop\n"
	"  lbu $1,0x270($19)\n"
	"  li $3,3\n"
	"  bne $1,$3,2f\n"
#ifdef BL_POD_AIM_TRACE
	"  lui $1,0x01F6\n"
	"  lw $1,-7936($1)\n" /* AIM_CONTROL */
	"  andi $1,$1,2\n"
	"  beq $1,$0,2f\n"
	"  sltiu $1,$17,2\n"
	"  beq $1,$0,3f\n"
	"  sll $1,$17,6\n"
#else
	"  lh $1,0x24c($19)\n"
	"  andi $1,$1,15\n"
	"  bne $1,$0,2f\n"
	"  sltiu $1,$17,2\n"
	"  beq $1,$0,2f\n"
	"  sll $1,$17,6\n"
#endif
	"  li $3,288\n"
	"  subu $3,$3,$1\n"
#ifdef BL_POD_AIM_TRACE
	"  b 2f\n"
	"  sh $3,38($16)\n"
	"3: lhu $1,0x24c($19)\n"
	"  andi $1,$1,15\n"
	"  sll $1,$1,1\n"
	"  lui $3,%hi(bl_aim_center)\n"
	"  addu $3,$3,$1\n"
	"  lh $3,%lo(bl_aim_center)($3)\n"
#endif
	"  sh $3,38($16)\n"
	"2:\n"
	"1: j 0x001343B4\n"
	"  nop\n"
#ifdef BL_POD_AIM_TRACE
	".pushsection .rodata\n"
	".align 1\n"
	"bl_aim_center: .half 0,256,0,0,128,192,64,0,384,320,448,0,0,0,0,0\n"
	".popsection\n"
#endif
	".set pop\n");
#endif
