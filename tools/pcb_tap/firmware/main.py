# PCB input tap firmware (MicroPython, Raspberry Pi Pico / RP2040). See tools/pcb_tap/README.md for wiring.
#
# Once per video frame (the LM1881's vertical sync, falling edge on VSYNC_PIN) the tap either
#   records:  reads the 9 JAMMA input lines (through the 74LVC245) and sends "frame bits" to the PC, or
#   replays:  sets the 9 MOSFET gates (high = line pulled low = pressed) from a queue the PC keeps filled.
# Bits (1 = pressed): 0 up, 1 down, 2 left, 3 right, 4 button 1, 5 button 2, 6 button 3, 7 P1 start, 8 coin 1.
#
# USB serial protocol (lines):
#   PC -> tap  "R"            start recording; the tap answers "REC" and then one "frame hexbits" line per vsync
#   PC -> tap  "P"            start replay; then the PC sends "hexbits" lines, one per frame, at least
#                             LEAD lines ahead; the tap applies one per vsync and answers "F frame" per vsync
#                             ("U frame" when its queue ran empty - that frame was released, not replayed)
#   PC -> tap  "S"            stop: releases every line, answers "STOP frames"
# Frame numbers count vsync pulses since the command (record from power-on: send R before switching the PCB on).
import sys
import select
from machine import Pin, mem32, disable_irq, enable_irq
from array import array
import micropython

micropython.alloc_emergency_exception_buf(100)

SENSE_PINS = (2, 3, 4, 5, 6, 7, 8, 9, 10)          # 74LVC245 B outputs, low = pressed
DRIVE_PINS = (12, 13, 14, 15, 16, 17, 18, 19, 20)   # 2N7000 gates, high = pressed
VSYNC_PIN = 22                                      # LM1881 pin 3 through a 10k/20k divider, active low
LED = Pin(25, Pin.OUT)

SIO_IN, SIO_SET, SIO_CLR = 0xD0000004, 0xD0000014, 0xD0000018
SENSE_MASK = sum(1 << p for p in SENSE_PINS)
DRIVE_MASK = sum(1 << p for p in DRIVE_PINS)

for p in SENSE_PINS:
    Pin(p, Pin.IN)
for p in DRIVE_PINS:
    Pin(p, Pin.OUT, value=0)
vsync = Pin(VSYNC_PIN, Pin.IN)

RING = 256
rec = array("I", [0] * RING)      # recorded words (sense pins, raw)
play = array("I", [0] * RING)     # queued drive words (GPIO set masks)
state = array("i", [0, 0, 0, 0, 0])  # mode (0 idle, 1 rec, 2 play), frame, head (written by IRQ), tail, play fill
MODE, FRAME, HEAD, TAIL, FILL = 0, 1, 2, 3, 4
underruns = array("I", [0])


def on_vsync(_pin):
    mode = state[MODE]
    if mode == 1:
        rec[state[HEAD] % RING] = mem32[SIO_IN] & SENSE_MASK
        state[HEAD] += 1
    elif mode == 2:
        if state[FILL] > 0:
            word = play[state[TAIL] % RING]
            mem32[SIO_CLR] = DRIVE_MASK & ~word
            mem32[SIO_SET] = word
            state[TAIL] += 1
            state[FILL] -= 1
        else:
            mem32[SIO_CLR] = DRIVE_MASK
            underruns[0] += 1
        state[HEAD] += 1
    state[FRAME] += 1


vsync.irq(trigger=Pin.IRQ_FALLING, handler=on_vsync, hard=True)


def sense_bits(raw):
    bits = 0
    for i, p in enumerate(SENSE_PINS):
        if not raw & (1 << p):
            bits |= 1 << i
    return bits


def drive_word(bits):
    word = 0
    for i, p in enumerate(DRIVE_PINS):
        if bits & (1 << i):
            word |= 1 << p
    return word


def release():
    mem32[SIO_CLR] = DRIVE_MASK


poll = select.poll()
poll.register(sys.stdin, select.POLLIN)
sent = 0
fed = 0
line = ""
while True:
    while poll.poll(0):
        ch = sys.stdin.read(1)
        if ch != "\n":
            line += ch
            continue
        cmd, line = line.strip(), ""
        if cmd == "R":
            state[MODE] = 0
            release()
            state[FRAME] = state[HEAD] = state[TAIL] = state[FILL] = 0
            sent = 0
            state[MODE] = 1
            LED.on()
            print("REC")
        elif cmd == "P":
            state[MODE] = 0
            release()
            state[FRAME] = state[HEAD] = state[TAIL] = state[FILL] = 0
            sent = fed = 0
            underruns[0] = 0
            state[MODE] = 2
            LED.on()
            print("PLAY")
        elif cmd == "S":
            state[MODE] = 0
            release()
            LED.off()
            print("STOP", state[FRAME], underruns[0])
        elif state[MODE] == 2 and cmd:
            if state[FILL] < RING:
                play[fed % RING] = drive_word(int(cmd, 16))
                fed += 1
                saved = disable_irq()  # the vsync IRQ decrements FILL
                state[FILL] += 1
                enable_irq(saved)
    if state[MODE] == 1:
        while sent < state[HEAD]:
            print(sent, "%03x" % sense_bits(rec[sent % RING]))
            sent += 1
    elif state[MODE] == 2:
        while sent < state[HEAD]:
            print("F", sent)
            sent += 1
