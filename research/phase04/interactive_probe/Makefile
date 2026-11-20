VPATH := $(dir $(firstword $(MAKEFILE_LIST)))

EE_BIN = interactive-probe.elf
EE_OBJS = controller_probe.o
EE_LIBS = -lpad -ldebug -lgraph -lc
EE_WARNFLAGS = -Wall -Wextra -Werror
EE_DBGINFOFLAGS =
EE_LDFLAGS = -Wl,--strip-debug

all: $(EE_BIN)

include $(PS2SDK)/samples/Makefile.pref
include $(PS2SDK)/samples/Makefile.eeglobal
