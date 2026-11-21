/* Return from the BLACK LABEL build to the launcher (baked builds only).
 *
 * The baked copy is started from the sixth Mode Select entry with LoadExecPS2. Its own Mode Select Exit
 * (accept dispatcher 0x001CA7E4) normally returns to its title; here the Exit sound call at 0x001CA7F0
 * is hooked so that, after the sound request, the kernel reloads the launcher's retail executable, the
 * same handoff the sixth entry uses in the other direction (docs/PAYLOAD_HANDOFF.md).
 */
#include "ibara_ps2.h"

/* PRACTICE > GAME MODE names this build's own rules (options.c; weak default "ARCADE" in the launcher). */
const char prac_name0[] = "KURO";

static const char launcher_path[] = "cdrom0:\\SLPM_663.01;1";
/* One argument for the launcher: "S=<screen mode><rank gauge>", kept current by video.c at 0x001D42F8 (zero padding in this
 * executable); without the video hook the string stays empty and the launcher ignores it. */
static const char *const launcher_argv[1] = {(const char *)0x001D42F8u};

void bl_return_to_launcher(void)
{
	register u32 v1 __asm__("v1") = 6; /* EE kernel syscall: LoadExecPS2(path, argc, argv) */
	EE_RAM(u8, 0x001D42F8u) = 'S'; /* video.c keeps the digit at +2 current */
	EE_RAM(u8, 0x001D42F9u) = '=';
	EE_RAM(u8, 0x001D42FCu) = 0; /* digits at +2 (screen mode) and +3 (rank gauge) */
	register const char *a0 __asm__("a0") = launcher_path;
	register u32 a1 __asm__("a1") = 1;
	register const char *const *a2 __asm__("a2") = launcher_argv;
	__asm__ volatile("syscall" : : "r"(v1), "r"(a0), "r"(a1), "r"(a2) : "memory");
	for (;;)
		;
}
