/* Preserve the retail 128-bit callee-saved registers across the C traces. */
	.set noreorder
	.text
.macro SAVE
	addiu $sp,$sp,-0x120
	sq $ra,0x00($sp)
	sq $s0,0x10($sp)
	sq $s1,0x20($sp)
	sq $s2,0x30($sp)
	sq $s3,0x40($sp)
	sq $s4,0x50($sp)
	sq $s5,0x60($sp)
	sq $s6,0x70($sp)
	sq $s7,0x80($sp)
	sq $fp,0x90($sp)
	sq $gp,0xA0($sp)
.endm

.macro RESTORE
	lq $gp,0xA0($sp)
	lq $fp,0x90($sp)
	lq $s7,0x80($sp)
	lq $s6,0x70($sp)
	lq $s5,0x60($sp)
	lq $s4,0x50($sp)
	lq $s3,0x40($sp)
	lq $s2,0x30($sp)
	lq $s1,0x20($sp)
	lq $s0,0x10($sp)
	lq $ra,0x00($sp)
.endm

	.globl replay_late_rng_entry
replay_late_rng_entry:
	SAVE
	sq $a0,0xB0($sp)
	sq $a1,0xC0($sp)
	/* RNG saved its caller at the top of its own frame. */
	jal replay_late_random
	ld $a0,0x120($sp)
	lq $a1,0xC0($sp)
	lq $a0,0xB0($sp)
	RESTORE
	j 0x00160310
	addiu $sp,$sp,0x120

	.globl replay_late_damage_entry
replay_late_damage_entry:
	SAVE
	sq $a0,0xB0($sp)
	sq $a1,0xC0($sp)
	sq $a2,0xD0($sp)
	sq $a3,0xE0($sp)
	jal replay_late_damage_before
	move $a0,$a1
	sw $v0,0xF0($sp)
	lq $a0,0xB0($sp)
	lq $a1,0xC0($sp)
	lq $a2,0xD0($sp)
	jal 0x001278B0
	lq $a3,0xE0($sp)
	sq $v0,0x100($sp)
	sq $v1,0x110($sp)
	lq $a0,0xC0($sp)
	ld $a1,0x00($sp)
	lq $a2,0xE0($sp)
	lw $a3,0xF0($sp)
	jal replay_late_damage_after
	move $t0,$v0
	lq $v0,0x100($sp)
	lq $v1,0x110($sp)
	RESTORE
	jr $ra
	addiu $sp,$sp,0x120

	/* The original jal delay slot has already stored the +10 award. */
	.globl replay_late_retail_graze_entry
replay_late_retail_graze_entry:
	SAVE
	sq $a0,0xB0($sp)
	sq $a1,0xC0($sp)
	move $a2,$a0
	move $a0,$ra
	move $a1,$s0
	jal replay_late_retail_graze
	move $a3,$v0
	lq $a1,0xC0($sp)
	lq $a0,0xB0($sp)
	RESTORE
	j 0x001372B0
	addiu $sp,$sp,0x120

#ifdef RP_POD_CONTACT
	.globl replay_contact_entry
replay_contact_entry:
	SAVE
	jal replay_contact_sample
	nop
	RESTORE
	j 0x0012B2D0
	addiu $sp,$sp,0x120

	.globl replay_contact_hit_entry
replay_contact_hit_entry:
	SAVE
	sq $a0,0xB0($sp)
	sq $a1,0xC0($sp)
	sq $a2,0xD0($sp)
	jal replay_contact_hit
	move $a1,$s3
	lq $a0,0xB0($sp)
	lq $a1,0xC0($sp)
	lq $a2,0xD0($sp)
	RESTORE
	j 0x0013BE10
	addiu $sp,$sp,0x120
#endif
