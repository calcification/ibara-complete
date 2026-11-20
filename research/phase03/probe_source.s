# Ibara Complete Phase 3 boot probe (MIPS III, PS2 EE R5900-compatible subset)
# Source of the 32-byte program inside KURO_PROBE.ELF, for auditing only.
# This code assumes the PS2 firmware has already established a usable GS video signal.
.set noreorder
.text
.globl _start
_start:
    lui   $t0, 0x1200        # PS2 GS privileged registers base
    addiu $t1, $zero, 0x20  # PMODE SLBG (use background)
    sd    $t1, 0($t0)        # GS PMODE
    lui   $t1, 0x00ff
    ori   $t1, $t1, 0x00ff   # BGCOLOR R=FF G=00 B=FF
    sd    $t1, 0xe0($t0)     # GS BGCOLOR
forever:
    b     forever
    nop
