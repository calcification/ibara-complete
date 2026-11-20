/* Return from the BLACK LABEL build to the launcher (baked builds only).
 *
 * The baked copy is started from the sixth Mode Select entry with LoadExecPS2. Its own Mode Select Exit
 * (accept dispatcher 0x001CA7E4) normally returns to its title; here the Exit sound call at 0x001CA7F0
 * is hooked so that, after the sound request, the kernel reloads the launcher's retail executable, the
 * same handoff the sixth entry uses in the other direction (docs/PAYLOAD_HANDOFF.md).
 */
#include "ibara_ps2.h"

static const char launcher_path[] = "cdrom0:\\SLPM_663.01;1";

void bl_return_to_launcher(void)
{
	register u32 v1 __asm__("v1") = 6; /* EE kernel syscall: LoadExecPS2(path, argc, argv) */
	register const char *a0 __asm__("a0") = launcher_path;
	register u32 a1 __asm__("a1") = 0;
	register u32 a2 __asm__("a2") = 0;
	__asm__ volatile("syscall" : : "r"(v1), "r"(a0), "r"(a1), "r"(a2) : "memory");
	for (;;)
		;
}
