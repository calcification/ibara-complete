/* Replay experiment (research/phase44; test builds only for now).
 *
 * Inputs are recorded and replayed per game update, not per pad read. The retail loop polls the pad from its
 * vsync wait (0x00113390 -> 0x00112A80), so the number of polls per update depends on timing: the same game
 * polled twice per update in one run and once in another (phase 44). The update itself starts at 0x0012E5CC
 * (`jal 0x00138CD0`, the first call of the update path); replay_update_entry runs there:
 *   RECORD: stores both players' button words (+0x24C held, +0x24E pressed, +0x250, +0x252, +0x254) per update.
 *   PLAY:   writes the stored words back before the update runs.
 * During playback the pad reads return the recorded pad values of the next update (the shot code reads the pad
 * arrays, not only the player words), so the live pad cannot pause or steer the game.
 * A game runs while MAIN_STATE is 5 (a game) outside attract mode; recording starts at its first update (after the
 * loading and ship select screens), where the random seed, the frame counter and the enemy group counter are
 * stored / restored.
 * Checkpoints (score, rank, scene and stage tick, seed) every 10 updates up to 1000, then every 300. */
#include "ibara_ps2.h"

#define SEED     0x00337D08u /* $gp-32744 */
#define FRAMES   0x00338CDCu /* $gp-28692 */
#define GROUP_ID 0x00338E4Cu /* $gp-28324, u16 */
#define SCENE    0x00338E9Cu
#define TICK     0x00338EA0u
#define RANK     0x00338EB4u
#define ATTRACT  0x00338E7Cu
#define MAIN_STATE 0x00338B08u /* 5: a game is running (9: frontend) */
#define CP_MAX 1400u
#ifndef RP_FIRST_MODE
#define RP_FIRST_MODE 0u /* 2: ignore the first game (experiment) */
#endif
#define BTN_WORDS 5u /* +0x24C .. +0x254 */

#define PADBLK 0x00341FA0u /* 2 x 0x50: +0 current, +4 previous, +8 pressed, +0xC repeat, timers */
struct rp_upd { u32 tick, rank, frames; u16 w[2][BTN_WORDS]; u16 raw[2]; u32 blk[40]; };
static u16 rp_raw[2]; /* record: the latest pad values */ /* tick = scene << 24 | stage tick, checked on playback */
#define RP_LOG ((struct rp_upd *)0x01B00000u) /* experiment: RAM unused in a game (0x01650000-0x01ED0000) */
#define RP_LOG_MAX 20000u
struct rp_cp { u32 upd, score, rank, stage_tick, seed, x, y, bombs; };
struct rp_state {
	u32 magic, mode, n_upd, play_upd, overflow, cp_n[2], tick_miss, play_done;
	u32 seed0, frames0, group0[4], first_miss; /* group0: enemy group counter and spawn serial (0x00338E4C-0x00338E53) */
	u32 rank0[4]; /* 0x00338EAC-0x00338EBB: rank state set at game init (0x00338EB8 += rand(2) before the first update) */
	u32 players0[2u * PS2_PLAYER_STRIDE / 4u]; /* both player records at the first update (ship, bomb, timers) */
} rp;
#define RP_CP ((struct rp_cp (*)[CP_MAX])0x01FC0000u) /* experiment */

void xtc_reset(void);
void bl_enemy_reset(void);
static u8 rp_active, rp_started; /* in a game; its first update has run */

static void checkpoint(u32 which, u32 upd)
{
	struct rp_cp *c;
	if ((upd >= 1200u && upd % 300u) || rp.cp_n[which] >= CP_MAX)
		return;
	c = &RP_CP[which][rp.cp_n[which]++];
	c->upd = upd;
	c->score = EE_RAM(u32, PS2_PLAYER_BASE + PS2_PLAYER_SCORE);
	c->rank = EE_RAM(u32, RANK);
	c->stage_tick = (u32)EE_RAM(u8, SCENE) << 24 | (EE_RAM(u32, TICK) & 0xFFFFFFu);
	c->seed = EE_RAM(u32, SEED);
	c->x = EE_RAM(u32, PS2_PLAYER_BASE + PS2_PLAYER_X);
	c->y = EE_RAM(u32, PS2_PLAYER_BASE + PS2_PLAYER_Y);
	c->bombs = EE_RAM(u8, PS2_PLAYER_BASE + PS2_PLAYER_BOMBS);
}

/* Objects the game spawns into a slot keep fields it does not initialise (left over from the previous game), so
 * every inactive slot is cleared at the first update of a recorded or replayed game. */
static void clear_pool(u32 base, u32 stride, u32 count, u32 all)
{
	u32 i, w;
	for (i = 0; i < count; i++, base += stride)
		if (all || !(EE_RAM(u32, base) & 0x80000000u))
			for (w = 0; w < stride; w += 4u)
				EE_RAM(u32, base + w) = 0;
}

#ifdef RP_REGIONS /* experiment: copy these regions from the recording's first update into the playback's */
static const u32 rp_regions[][2] = {RP_REGIONS};
static void regions(u32 restore)
{
	u32 *buf = (u32 *)0x01A80000u, r, a;
	for (r = 0; r < sizeof(rp_regions) / sizeof(rp_regions[0]); r++)
		for (a = rp_regions[r][0]; a < rp_regions[r][1]; a += 4u, buf++) {
			if (restore)
				EE_RAM(u32, a) = *buf;
			else
				*buf = EE_RAM(u32, a);
		}
}
#endif

static void game_start(void)
{
	u32 i;
	rp_started = 1;
	if (rp.mode == 2u)
		return;
	/* no shot, item or bullet exists at a stage's first update, but items can survive RETURN MENU */
	clear_pool(PS2_SHOTS_BASE, PS2_SHOT_STRIDE, 256u, 1u);
	clear_pool(PS2_ITEMS_BASE, 0x58u, 256u, 1u);
	clear_pool(0x0045A840u, 0xB4u, 192u, 0u);
	clear_pool(PS2_BULLETS_BASE, PS2_BULLET_STRIDE, PS2_BULLET_COUNT, 1u);
	/* the graze test alternates sides each update and kept its phase from the previous game (xtc.c) */
	xtc_reset();
	bl_enemy_reset(); /* the boss-cancel kill tracker (last frame's HP per slot) */
	/* the item drop state that the stage's item initialiser 0x00132640 zeroes (Practice's GAME START skips it) */
	EE_RAM(u8, 0x00338E54u) = EE_RAM(u8, 0x00338E55u) = EE_RAM(u8, 0x00338E58u) = 0;
	EE_RAM(u8, 0x00338E59u) = EE_RAM(u8, 0x00338E5Cu) = 0;
	for (i = 0; i < 32u; i++)
		EE_RAM(u8, 0x00495120u + i) = 0;
	if (rp.mode == 0) {
		rp.seed0 = EE_RAM(u32, SEED);
		rp.frames0 = EE_RAM(u32, FRAMES);
		for (i = 0; i < 2u; i++)
			rp.group0[i] = EE_RAM(u32, GROUP_ID + 4u * i);
		for (i = 0; i < 2u * PS2_PLAYER_STRIDE / 4u; i++)
			rp.players0[i] = EE_RAM(u32, PS2_PLAYER_BASE + 4u * i);
		for (i = 0; i < 4u; i++)
			rp.rank0[i] = EE_RAM(u32, 0x00338EACu + 4u * i);
#ifdef RP_REGIONS
		regions(0);
#endif
		rp.n_upd = rp.overflow = rp.cp_n[0] = 0;
	} else {
		EE_RAM(u32, SEED) = rp.seed0;
		EE_RAM(u32, FRAMES) = rp.frames0;
		for (i = 0; i < 2u; i++)
			EE_RAM(u32, GROUP_ID + 4u * i) = rp.group0[i];
		for (i = 0; i < 2u * PS2_PLAYER_STRIDE / 4u; i++)
			EE_RAM(u32, PS2_PLAYER_BASE + 4u * i) = rp.players0[i];
		for (i = 0; i < 4u; i++)
			EE_RAM(u32, 0x00338EACu + 4u * i) = rp.rank0[i];
#ifdef RP_REGIONS
		regions(1);
#endif
		rp.play_upd = rp.play_done = rp.cp_n[1] = rp.tick_miss = 0;
		rp.first_miss = 0xFFFFFFFFu;
	}
}

static void game_end(void)
{
	rp_active = rp_started = 0;
	if (rp.mode == 2u)
		rp.mode = 0;
	else if (rp.mode == 0)
		rp.mode = 1;
	else
		rp.play_done = 1;
}

/* Called for each pad read (both ports): tracks game start / end; masks the live pad during playback. */
u32 replay_pad(u32 port, u32 buttons)
{
	if (rp.magic != 0x33504552u) { /* "REP3" */
		rp.magic = 0x33504552u;
		rp.mode = RP_FIRST_MODE;
		rp.n_upd = rp.overflow = rp.cp_n[0] = rp.cp_n[1] = 0;
	}
	if (port == 0u) {
		const u32 in_game = EE_RAM(u32, MAIN_STATE) == 5u && !EE_RAM(u8, ATTRACT);
		if (rp_active && !in_game)
			game_end();
		if (!rp_active && in_game)
			rp_active = 1;
	}
	if (!rp_started || port > 1u)
		return buttons;
	if (port == 0u)
		EE_RAM(u32, FRAMES) -= 1u; /* 0x00113390 counts vsyncs; during a game it counts updates instead */
	if (rp.mode == 0u)
		rp_raw[port] = (u16)buttons;
	else if (rp.mode == 1u)
		return rp.play_upd < rp.n_upd ? RP_LOG[rp.play_upd].raw[port] : 0u; /* the inputs of the next update */
	return buttons;
}

/* Called at the start of each game update. */
#ifndef RP_SNAP_AT
#define RP_SNAP_AT 925u
#endif
#ifdef RP_SNAP_FULL
static void snap(u32 which, u32 n)
{
	u32 *dst = (u32 *)(0x01660000u + which * 0x00200000u);
	u32 i;
	(void)n;
	for (i = 0; i < 0x00200000u / 4u; i++)
		dst[i] = ((const u32 *)0x00300000u)[i];
}
#define SNAP_N(u) ((u) == RP_SNAP_AT)
#else
#define SNAP_SIZE 0x38000u /* 0x00338000-0x00340000 then 0x00440000-0x00470000 */
static void snap(u32 which, u32 n)
{
	u32 *dst = (u32 *)(0x01660000u + (which * 10u + n) * SNAP_SIZE);
	u32 i;
	for (i = 0; i < 0x8000u / 4u; i++)
		dst[i] = ((const u32 *)0x00338000u)[i];
	for (i = 0; i < 0x30000u / 4u; i++)
		dst[0x8000u / 4u + i] = ((const u32 *)0x00440000u)[i];
}
#define SNAP_N(u) ((u) >= RP_SNAP_AT && (u) < RP_SNAP_AT + 500u && ((u) - RP_SNAP_AT) % 50u == 0u)
#endif

void replay_update(void)
{
	const u32 tick = (u32)EE_RAM(u8, SCENE) << 24 | (EE_RAM(u32, TICK) & 0xFFFFFFu);
	u32 side, i;
	if (!rp_active)
		return;
	if (!rp_started)
		game_start(); /* the first update: after the loading and the ship select screens */
	else
		EE_RAM(u32, FRAMES) += 1u;
	if (rp.mode == 2u)
		return;
	if (rp.mode == 0) {
		if (rp.n_upd >= RP_LOG_MAX) {
			rp.overflow++;
			return;
		}
		RP_LOG[rp.n_upd].tick = tick;
		RP_LOG[rp.n_upd].rank = EE_RAM(u32, RANK); /* Arcade rank creep runs per loop pass (timing) */
		RP_LOG[rp.n_upd].frames = EE_RAM(u32, FRAMES); /* check only */
		RP_LOG[rp.n_upd].raw[0] = rp_raw[0];
		RP_LOG[rp.n_upd].raw[1] = rp_raw[1];
		for (i = 0; i < 40u; i++)
			RP_LOG[rp.n_upd].blk[i] = EE_RAM(u32, PADBLK + 4u * i);
		for (side = 0; side < 2; side++)
			for (i = 0; i < BTN_WORDS; i++)
				RP_LOG[rp.n_upd].w[side][i] =
					EE_RAM(u16, PS2_PLAYER_BASE + side * PS2_PLAYER_STRIDE + PS2_PLAYER_HELD + 2u * i);
		if (SNAP_N(rp.n_upd))
			snap(0, (rp.n_upd - RP_SNAP_AT) / 50u);
		checkpoint(0, rp.n_upd++);
		return;
	}
	if (rp.play_upd < rp.n_upd) {
		if ((RP_LOG[rp.play_upd].tick != tick || RP_LOG[rp.play_upd].frames != EE_RAM(u32, FRAMES)) &&
		    rp.tick_miss++ == 0u)
			rp.first_miss = rp.play_upd;
		EE_RAM(u32, RANK) = RP_LOG[rp.play_upd].rank;
		for (i = 0; i < 40u; i++)
			EE_RAM(u32, PADBLK + 4u * i) = RP_LOG[rp.play_upd].blk[i];
		for (side = 0; side < 2; side++)
			for (i = 0; i < BTN_WORDS; i++)
				EE_RAM(u16, PS2_PLAYER_BASE + side * PS2_PLAYER_STRIDE + PS2_PLAYER_HELD + 2u * i) =
					RP_LOG[rp.play_upd].w[side][i];
	}
	if (SNAP_N(rp.play_upd))
		snap(1, (rp.play_upd - RP_SNAP_AT) / 50u);
	checkpoint(1, rp.play_upd++);
}

/* Replaces `jal 0x0010DDD0` at 0x00112B1C / 0x00112B28 (a0 = port, set in the delay slot): calls the original,
 * then replay_pad(port, buttons), and returns its value. Saves the callee-saved registers with 128-bit sq like
 * ps2/hooks/stub.S (our C may use them with 32-bit saves). */
__asm__(
	".set push\n.set noreorder\n.set noat\n"
	".globl replay_pad_entry\n"
	"replay_pad_entry:\n"
	"	addiu $sp,$sp,-0xC0\n"
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
	"	jal 0x0010DDD0\n"
	"	sw $a0,0xB0($sp)\n"
	"	lw $a0,0xB0($sp)\n"
	"	jal replay_pad\n"
	"	move $a1,$v0\n"
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
	"	jr $ra\n"
	"	addiu $sp,$sp,0xC0\n"
	/* Replaces `jal 0x00138CD0` at 0x0012E5CC: ra (0x0012E5D4) is set by our jal and kept for the tail call.
	 * Saves the callee-saved registers and the argument / result / temporary registers too. */
	".globl replay_update_entry\n"
	"replay_update_entry:\n"
	"	addiu $sp,$sp,-0x150\n"
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
	"	sq $a2,0xD0($sp)\n"
	"	sq $a3,0xE0($sp)\n"
	"	sq $v0,0xF0($sp)\n"
	"	sq $v1,0x100($sp)\n"
	"	sq $t0,0x110($sp)\n"
	"	sq $t1,0x120($sp)\n"
	"	jal replay_update\n"
	"	sq $t2,0x130($sp)\n"
	"	lq $t2,0x130($sp)\n"
	"	lq $t1,0x120($sp)\n"
	"	lq $t0,0x110($sp)\n"
	"	lq $v1,0x100($sp)\n"
	"	lq $v0,0xF0($sp)\n"
	"	lq $a3,0xE0($sp)\n"
	"	lq $a2,0xD0($sp)\n"
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
	"	j 0x00138CD0\n"
	"	addiu $sp,$sp,0x150\n"
	".set pop\n");
