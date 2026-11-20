TEST_DIR := $(abspath $(dir $(firstword $(MAKEFILE_LIST)))/..)
VPATH := $(TEST_DIR)/ee $(TEST_DIR) $(TEST_DIR)/../src

EE_BIN = ee-memory-smoke.elf
EE_OBJS = ee_memory_smoke.o test_memory.o cv1k_memory.o
EE_LIBS = -ldebug -lc
EE_WARNFLAGS = -Wall -Wextra -Werror
EE_DBGINFOFLAGS =
EE_LDFLAGS = -Wl,--strip-debug

all: $(EE_BIN)

test_memory.o: EE_CFLAGS += -Dmain=memory_selftest

include $(PS2SDK)/samples/Makefile.pref
include $(PS2SDK)/samples/Makefile.eeglobal
