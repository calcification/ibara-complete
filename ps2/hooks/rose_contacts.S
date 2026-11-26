/* Diagnostic only. The native damage path carries live registers beyond the
 * standard EE ABI. These shims preserve every register they use. */
.set push
.set noreorder
.set noat

/* Header: HIT1, count, dropped, pending record, pending native stack, part.
 * All 24,000 records fit below 0x01FF0000, under the retail stack. */
.macro save
	addiu $29,$29,-80
	sq $8,0($29)
	sq $9,16($29)
	sq $10,32($29)
	sq $11,48($29)
	sq $12,64($29)
.endm

.macro restore
	lq $8,0($29)
	lq $9,16($29)
	lq $10,32($29)
	lq $11,48($29)
	lq $12,64($29)
	addiu $29,$29,80
.endm

.text
.globl rose_contact_begin
rose_contact_begin:
	save
	lw $8,80($29)                    /* native caller */
	lui $9,0x0013
	addiu $9,$9,-19072               /* 0x0012B580 */
	beq $8,$9,1f
	move $12,$20                     /* first caller's shot */
	addiu $9,$9,892                  /* 0x0012B8FC */
	bne $8,$9,8f
	move $12,$18                     /* second caller's shot */
1:
	lui $9,0x0034
	lbu $8,-29028($9)                /* stage byte 0x00338E9C */
	addiu $9,$0,7
	bne $8,$9,8f
	nop
	lw $8,4($5)                      /* resolved part type */
	addiu $9,$0,74
	bne $8,$9,1f
	addiu $9,$0,79
#ifdef BL_CONTACT_ALL74 /* research/phase37: every type-74 part, not only the cores */
	b 2f
	nop
#endif
	lw $8,8($5)
	beq $8,$0,2f
	addiu $9,$0,2
	bne $8,$9,8f
	nop
	b 2f
	nop
1:
	bne $8,$9,8f
	nop
2:
	lh $11,60($5)
	blez $11,8f
	lui $10,0x01F9
	lw $9,12($10)
	bne $9,$0,8f                    /* leave an outer native call in place */
	nop
	lui $9,0x3154
	addiu $9,$9,18760                /* HIT1 */
	sw $9,0($10)
	lw $9,4($10)
	sltiu $8,$9,24000
	bne $8,$0,3f
	lw $8,8($10)
	addiu $8,$8,1
	b 8f
	sw $8,8($10)
3:
	addiu $8,$9,1
	sw $8,4($10)
	sll $9,$9,4
	addu $9,$9,$10
	addiu $9,$9,32
	sh $11,8($9)                    /* HP before and after */
	sh $11,10($9)
	lui $8,0x0034
	lw $8,-29024($8)                /* stage tick 0x00338EA0 */
	sw $8,0($9)
	lw $8,4($5)
	sb $8,4($9)
	lw $8,8($5)
	sb $8,5($9)
	sb $3,6($9)                     /* hit flash, original delay slot */
	lbu $8,4($12)
	sb $8,7($9)
	sw $9,12($10)
	addiu $8,$29,80
	sw $8,16($10)
	sw $5,20($10)
8:
	restore
	bne $2,$0,9f                     /* branch displaced at 0x00127AF0 */
	nop
	j 0x00127970
	nop
9:
	j 0x00127994
	nop

.globl rose_contact_end
rose_contact_end:
	save
	lui $10,0x01F9
	lw $9,12($10)
	beq $9,$0,1f
	addiu $8,$29,80
	lw $11,16($10)
	bne $8,$11,1f
	nop
	lw $8,20($10)
	lhu $11,60($8)
	sh $11,10($9)
	sw $0,12($10)
1:
	restore
	ld $31,0($29)
	jr $31
	addiu $29,$29,16
.set pop
