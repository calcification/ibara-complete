/* C00: code-injection smoke test. Proves, in PCSX2, that (1) the code cave survives, (2) a retail per-frame
 * jal site can be redirected through stub.S and (3) the retail routine still runs (game plays normally).
 *
 * Observable result (PCSX2 debugger, memory view at the cave base): the 'IBCX' magic, a frame counter that
 * advances once per game logic frame while in play, and a copy of the P1 score word.
 */
#include "ibara_ps2.h"

struct h00_hdr {
	u32 magic;        /* 'IBCX' little-endian: 0x58434249 */
	u32 version;
	u32 frames;       /* increments after every call of the hooked retail routine */
	u32 p1_score;     /* mirror of P1 score, to prove we read game state */
};

__attribute__((section(".hookhdr"), used)) struct h00_hdr h00 = { 0x58434249u, 1u, 0u, 0u };

void h00_frame(void)
{
	h00.frames++;
	h00.p1_score = EE_RAM(u32, PS2_PLAYER_BASE + PS2_PLAYER_SCORE);
}
