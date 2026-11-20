/* Injected hook image: everything contiguous from CAVE_BASE (passed with --defsym by build_ee_hooks.py).
 * .hookhdr first so debug headers sit at a predictable address (the cave base). */
OUTPUT_ARCH(mips)
ENTRY(__cave_start)
SECTIONS
{
	. = CAVE_BASE;
	__cave_start = .;
	.hookhdr : { KEEP(*(.hookhdr)) }
	. = ALIGN(16);
	.text : { *(.text .text.*) }
	. = ALIGN(16);
	.rodata : { *(.rodata .rodata.* .rodata1) }
	. = ALIGN(16);
	__data_start = .;
	.data : { *(.data .data.* .sdata .sdata.*) }
	. = ALIGN(16);
	.bss : { *(.bss .bss.* .sbss .sbss.* COMMON) }
	. = ALIGN(16);
	__cave_end = .;
	/DISCARD/ : { *(.comment) *(.note*) *(.MIPS.abiflags) *(.reginfo) *(.pdr) *(.gnu.attributes) *(.mdebug*) }
}
