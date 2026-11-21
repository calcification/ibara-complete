/* Entry stubs for hooks placed on a retail `jal ORIGINAL` call site.
 *
 * The retail game is built with the PS2 SDK's EE compiler, which may keep 64/128-bit values in callee-saved
 * registers. Our C is built o32 (-march=r5900 -mabi=32), whose prologues save s-registers with 32-bit sw,
 * so calling it directly could truncate the game's registers. Each stub therefore:
 *   1. saves ra, s0-s7, fp (s8) and gp with 128-bit sq,
 *   2. calls the ORIGINAL routine with a0-a3 untouched (behaviour of the retail call is preserved),
 *   3. saves its v0/v1, calls the C hook, restores everything and returns the original's v0/v1.
 * gp is never used by our code (-G0) but is restored anyway.
 */
	.set	noreorder
	.set	noat
	.text

#define FRAME 0xC0

.macro HOOK_AFTER name, original, chook
	.globl	\name
	.type	\name, @function
	.align	4
\name:
	addiu	$sp, $sp, -FRAME
	sq	$ra, 0x00($sp)
	sq	$s0, 0x10($sp)
	sq	$s1, 0x20($sp)
	sq	$s2, 0x30($sp)
	sq	$s3, 0x40($sp)
	sq	$s4, 0x50($sp)
	sq	$s5, 0x60($sp)
	sq	$s6, 0x70($sp)
	sq	$s7, 0x80($sp)
	sq	$fp, 0x90($sp)
	jal	\original
	sq	$gp, 0xA0($sp)
	sw	$v0, 0xB0($sp)
	jal	\chook
	sw	$v1, 0xB4($sp)
	lw	$v0, 0xB0($sp)
	lw	$v1, 0xB4($sp)
	lq	$gp, 0xA0($sp)
	lq	$fp, 0x90($sp)
	lq	$s7, 0x80($sp)
	lq	$s6, 0x70($sp)
	lq	$s5, 0x60($sp)
	lq	$s4, 0x50($sp)
	lq	$s3, 0x40($sp)
	lq	$s2, 0x30($sp)
	lq	$s1, 0x20($sp)
	lq	$s0, 0x10($sp)
	lq	$ra, 0x00($sp)
	jr	$ra
	addiu	$sp, $sp, FRAME
	.size	\name, . - \name
.endm

/* Minimal variant for a site whose caller restores only ra after the call (e.g. the main loop body 0x0010BC60:
 * `jal 0x0010E480; nop; ld ra; jr ra`) and a C hook that uses no callee-saved registers (checked by
 * tests/test_ee_hooks.py against the listing): saves ra, calls ORIGINAL, then the hook. 36 bytes instead of 128. */
.macro HOOK_AFTER_LEAF name, original, chook
	.globl	\name
	.type	\name, @function
	.align	4
\name:
	addiu	$sp, $sp, -16
	sd	$ra, 0($sp)
	jal	\original
	nop
	jal	\chook
	nop
	ld	$ra, 0($sp)
	jr	$ra
	addiu	$sp, $sp, 16
	.size	\name, . - \name
.endm

/* Stubs are instantiated by the build (hooks.S generated per profile). */
