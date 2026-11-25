/* Test-only Arrange CONFIG alternatives. Keep Arcade's live settings separate. */
#include "ibara_ps2.h"

u32 arrange_stock = 2u; /* Retail Arrange starts with two spare lives. */
#ifdef ARRANGE_COPY_STOCK
static const char stock_label[] = "COPY STOCK";
#else
#define stock_label ((const char *)0x00302110u)
#endif

const char *const arrange_stock_labels[] = {
	(const char *)0x00301CC0u, (const char *)0x00301CD0u, (const char *)0x00301CE0u,
	stock_label, (const char *)0x00301C50u,
};

const char *const arrange_stock_help[] = {
	(const char *)0x00302690u, (const char *)0x00302300u,
	(const char *)0x003026B0u, (const char *)0x003026C8u,
	(const char *)0x003026E0u, (const char *)0x00302300u,
	(const char *)0x00302330u, (const char *)0x00302300u,
	(const char *)0x00302700u, (const char *)0x00301F10u,
};

void arrange_stock_choose(void)
{
#ifdef ARRANGE_COPY_STOCK
	const u32 arcade_stock = EE_RAM(u8, 0x00338C00u);
	arrange_stock = arcade_stock < 6u ? arcade_stock : 2u;
#else
	arrange_stock = arrange_stock == 5u ? 0u : arrange_stock + 1u;
#endif
	GAME_CALL2(0x001370E0u, 95, 36);
}

__asm__(
	".set push\n.set noreorder\n.set noat\n"
	".globl arrange_stock_value\n"
	"arrange_stock_value:\n"
	"	beq $17,$2,1f\n" /* native BULLET DESIGN value path */
	"	li $1,3\n"
	"	bne $17,$1,2f\n"
	"	nop\n"
	"	lui $1,%hi(arrange_stock)\n"
	"	lw $4,%lo(arrange_stock)($1)\n"
	"	sll $4,$4,2\n"
	"	lui $1,0x2b\n"
	"	addiu $1,$1,-28016\n" /* retail PLAYER STOCK values, 0x002A9290 */
	"	addu $1,$1,$4\n"
	"	lw $4,0($1)\n"
	"2:	j 0x001cce88\n"
	"	nop\n"
	"1:	j 0x001cce70\n"
	"	nop\n"
	".globl arrange_stock_accept\n"
	"arrange_stock_accept:\n"
	"	bne $3,$2,3f\n"
	"	nop\n"
	"	jal arrange_stock_choose\n"
	"	nop\n"
	"	j 0x001ccdb0\n"
	"	nop\n"
	"3:	li $2,4\n"
	"	beq $3,$2,4f\n"
	"	nop\n"
	"	j 0x001ccdb0\n"
	"	nop\n"
	"4:	j 0x001cd0a4\n"
	"	nop\n"
	".globl arrange_stock_wrap\n"
	"arrange_stock_wrap:\n"
	"	j 0x001cd044\n"
	"	sw $2,-26732($gp)\n"
	".globl arrange_stock_start\n"
	"arrange_stock_start:\n"
	"	bnez $3,5f\n"
	"	nop\n"
	"	j 0x0012d8f0\n" /* Arcade still reads its own stock byte */
	"	nop\n"
	"5:	lui $1,%hi(arrange_stock)\n"
	"	lw $1,%lo(arrange_stock)($1)\n"
	"	j 0x0012d8f8\n"
	"	sb $1,0x25a($16)\n"
	".set pop\n"
);
