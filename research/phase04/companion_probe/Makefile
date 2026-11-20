VPATH := $(dir $(firstword $(MAKEFILE_LIST)))

EE_BIN = companion-probe.elf
EE_OBJS = probe.o
EE_LIBS = -ldebug -lgraph -lc
EE_WARNFLAGS = -Wall -Wextra -Werror
EE_DBGINFOFLAGS =
EE_LDFLAGS = -Wl,--strip-debug

all: $(EE_BIN)

include $(PS2SDK)/samples/Makefile.pref
include $(PS2SDK)/samples/Makefile.eeglobal
