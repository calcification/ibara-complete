#!/usr/bin/env python3
"""Talk to the PCB input tap (tools/pcb_tap/firmware/main.py) over USB serial. Needs pyserial.

    python3 tap.py record --port /dev/ttyACM0 --out run1.tap      # Ctrl+C to stop
    python3 tap.py play   --port /dev/ttyACM0 --log run1.tap      # replays the recorded frames

Record from power-on: start `record`, then switch the PCB on, so frame 0 is the board's first vsync.
A .tap file is text: a "# bits:" header naming the bits, then one "frame hexbits" line per frame.
"""
from __future__ import annotations

import argparse
import sys
import time

BITS = ("up", "down", "left", "right", "button1", "button2", "button3", "start", "coin")
LEAD = 120  # frames queued ahead of the tap during replay (the tap holds 256)


def open_port(name):
    try:
        import serial
    except ImportError:
        raise SystemExit("pip install pyserial")
    port = serial.Serial(name, 115200, timeout=0.05)
    port.write(b"S\n")
    time.sleep(0.2)
    port.reset_input_buffer()
    return port


def read_tap(path):
    frames = []
    for line in open(path):
        if line.startswith("#") or not line.strip():
            continue
        _f, bits = line.split()
        frames.append(int(bits, 16))
    return frames


def record(args):
    port = open_port(args.port)
    port.write(b"R\n")
    n = 0
    with open(args.out, "w") as out:
        out.write("# bits: " + " ".join(BITS) + "\n")
        out.write(f"# recorded {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        print("recording; switch the PCB on now. Ctrl+C stops.")
        try:
            while True:
                line = port.readline().decode(errors="replace").strip()
                if not line or line == "REC":
                    continue
                frame, bits = line.split()
                if int(frame) != n:
                    print(f"warning: frame {frame} after {n - 1} (serial dropped lines?)", file=sys.stderr)
                    n = int(frame)
                out.write(f"{frame} {bits}\n")
                n += 1
                if n % 600 == 0:
                    print(f"  {n} frames ({n / 60.024:.0f} s)")
        except KeyboardInterrupt:
            pass
    port.write(b"S\n")
    print(f"{n} frames -> {args.out}")


def play(args):
    frames = read_tap(args.log)
    port = open_port(args.port)
    port.write(b"P\n")
    sent = done = underruns = 0
    print(f"replaying {len(frames)} frames; switch the PCB on now.")
    while done < len(frames):
        while sent < len(frames) and sent - done < LEAD:
            port.write(f"{frames[sent]:03x}\n".encode())
            sent += 1
        line = port.readline().decode(errors="replace").strip()
        if line.startswith("F "):
            done = int(line[2:]) + 1
        elif line.startswith("U "):
            underruns += 1
    port.write(b"S\n")
    print(f"done ({underruns} underruns)" + ("" if not underruns else " - replay is not exact"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--port", required=True)
    r.add_argument("--out", required=True)
    p = sub.add_parser("play")
    p.add_argument("--port", required=True)
    p.add_argument("--log", required=True)
    args = ap.parse_args(argv)
    (record if args.cmd == "record" else play)(args)


if __name__ == "__main__":
    main()
