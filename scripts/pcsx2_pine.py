#!/usr/bin/env python3
"""Minimal PINE client for PCSX2 (Settings -> Advanced -> Enable PINE; default slot 28011).

Reads/writes emulated EE memory and saves/loads savestates while the game runs, so PCSX2 tests can be
scripted and logged instead of watched by hand. Standard library only.

    python3 scripts/pcsx2_pine.py status
    python3 scripts/pcsx2_pine.py read32 000C0000 000C0008 0044C600
    python3 scripts/pcsx2_pine.py watch 000C0008 0044C600 --seconds 10
    python3 scripts/pcsx2_pine.py savestate 1

Transport: Unix socket $XDG_RUNTIME_DIR/pcsx2.sock (or /tmp/pcsx2.sock) on Linux/macOS when the slot is the
default 28011 (otherwise pcsx2.sock.<slot>); TCP 127.0.0.1:<slot> on Windows.
Wire format: u32 little-endian total size, then opcode/payload; reply = u32 size, u8 result (0 = OK), data.
"""
from __future__ import annotations

import argparse
import os
import socket
import struct
import sys
import time

READ8, READ16, READ32, READ64 = 0, 1, 2, 3
WRITE8, WRITE16, WRITE32, WRITE64 = 4, 5, 6, 7
VERSION, SAVE_STATE, LOAD_STATE, TITLE, GAME_ID, UUID, GAME_VERSION, STATUS = 8, 9, 10, 11, 12, 13, 14, 15
STATUS_NAMES = {0: "running", 1: "paused", 2: "shutdown"}


class Pine:
    def __init__(self, slot: int = 28011, path: str | None = None, timeout: float = 5.0):
        if os.name == "nt":
            self.sock = socket.create_connection(("127.0.0.1", slot), timeout=timeout)
        else:
            if path is None:
                # PCSX2 PINE.cpp: macOS uses $TMPDIR, other Unix $XDG_RUNTIME_DIR, else /tmp
                var = "TMPDIR" if sys.platform == "darwin" else "XDG_RUNTIME_DIR"
                base = os.environ.get(var) or "/tmp"
                path = os.path.join(base, "pcsx2.sock" if slot == 28011 else f"pcsx2.sock.{slot}")
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.settimeout(timeout)
            self.sock.connect(path)

    def close(self):
        self.sock.close()

    def _recv(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("PINE socket closed")
            buf += chunk
        return buf

    def call(self, opcode: int, payload: bytes = b"") -> bytes:
        msg = struct.pack("<IB", 5 + len(payload), opcode) + payload
        self.sock.sendall(msg)
        size, = struct.unpack("<I", self._recv(4))
        body = self._recv(size - 4)
        if body[0] != 0:
            raise RuntimeError(f"PINE opcode {opcode} failed")
        return body[1:]

    def read(self, addr: int, width: int = 32) -> int:
        op, fmt = {8: (READ8, "<B"), 16: (READ16, "<H"), 32: (READ32, "<I"), 64: (READ64, "<Q")}[width]
        return struct.unpack(fmt, self.call(op, struct.pack("<I", addr)))[0]

    def write(self, addr: int, value: int, width: int = 32):
        op, fmt = {8: (WRITE8, "<B"), 16: (WRITE16, "<H"), 32: (WRITE32, "<I"), 64: (WRITE64, "<Q")}[width]
        self.call(op, struct.pack("<I", addr) + struct.pack(fmt, value))

    def _string(self, opcode: int) -> str:
        data = self.call(opcode)
        n, = struct.unpack_from("<I", data)
        return data[4:4 + n].rstrip(b"\0").decode(errors="replace")

    def version(self) -> str:
        return self._string(VERSION)

    def game_id(self) -> str:
        return self._string(GAME_ID)

    def title(self) -> str:
        return self._string(TITLE)

    def status(self) -> str:
        return STATUS_NAMES.get(struct.unpack("<I", self.call(STATUS))[0], "?")

    def save_state(self, slot: int):
        self.call(SAVE_STATE, struct.pack("<B", slot))

    def load_state(self, slot: int):
        self.call(LOAD_STATE, struct.pack("<B", slot))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slot", type=int, default=28011)
    ap.add_argument("--socket", help="explicit Unix socket path")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    r = sub.add_parser("read32")
    r.add_argument("addrs", nargs="+")
    w = sub.add_parser("watch")
    w.add_argument("addrs", nargs="+")
    w.add_argument("--seconds", type=float, default=10.0)
    w.add_argument("--interval", type=float, default=1.0)
    s = sub.add_parser("savestate")
    s.add_argument("slot", type=int)
    l = sub.add_parser("loadstate")
    l.add_argument("slot", type=int)
    args = ap.parse_args(argv)

    p = Pine(args.slot, args.socket)
    try:
        if args.cmd == "status":
            print(f"version={p.version()} status={p.status()} id={p.game_id()} title={p.title()}")
        elif args.cmd == "read32":
            for a in args.addrs:
                print(f"{int(a, 16):08X} {p.read(int(a, 16)):08X}")
        elif args.cmd == "watch":
            t0 = time.time()
            while time.time() - t0 < args.seconds:
                print(f"{time.time() - t0:6.1f}s " + " ".join(f"{int(a, 16):08X}={p.read(int(a, 16)):08X}" for a in args.addrs),
                      flush=True)
                time.sleep(args.interval)
        elif args.cmd == "savestate":
            p.save_state(args.slot)
        elif args.cmd == "loadstate":
            p.load_state(args.slot)
    finally:
        p.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
