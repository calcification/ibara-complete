#!/usr/bin/env python3
"""Log one stage in Black Label (MAME) and in the PS2 BLACK LABEL build (PCSX2), then compare.

    python3 tools/stage_compare/run_stage.py --stage 2 --out runs/stage2 \\
        --retail-iso 'Ibara (Japan).iso' --pcsx2-dir ~/pcsx2/build/bin --mame mame --bl-roms ~/roms

Both games: invincible player 1 (Bond / straight A), shot held from the start, rank locked (default 0x800000),
optional shot-level lock, optional --noshot (stop shooting when the logged stage starts; the boss then never
dies, so use it for attack timelines only). Logs are written to --out as bl_*.txt and ps2_*.txt, plus
compare_spawns.txt and compare_bullets.txt. Use --skip-bl / --skip-ps2 to re-run one side.

Requirements (Linux): PCSX2 Qt (v1.7.4000 tested) already configured with a Japanese BIOS, keyboard pad mapping
Return = Start, Up = Up, x = Circle, z = Cross, F1 = save state, and CRC-prefixed cheats off; Xvfb, xdotool;
MAME 0.264 with the ibarablk set; the MIPS cross compiler (scripts/build_ee_hooks.py). Everything stays local.
The PS2 run is wall-clock timed (--seconds, default 60 + 240 per stage): if the capture ends before the stage
does, raise it.
"""
from __future__ import annotations

import argparse
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "research" / "phase14"))


def sh(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


class Xpcsx2:
    """Headless PCSX2 on an Xvfb display, driven with xdotool."""

    def __init__(self, pcsx2_dir: Path, display=":50"):
        self.dir, self.display = pcsx2_dir, display
        self.env = dict(os.environ, DISPLAY=display, QT_QPA_PLATFORM="xcb", XDG_RUNTIME_DIR=str(pcsx2_dir / "run"))

    def start_x(self):
        subprocess.run(["pkill", "-9", "-f", "pcsx2-qt"])
        subprocess.run(["pkill", "-9", "-f", f"Xvfb {self.display}"])
        time.sleep(1)
        n = self.display.lstrip(":")
        for stale in (Path(f"/tmp/.X{n}-lock"), Path(f"/tmp/.X11-unix/X{n}")):
            if stale.exists():
                stale.unlink()
        subprocess.Popen(["Xvfb", self.display, "-screen", "0", "1280x960x24", "-nolisten", "tcp"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            if subprocess.run(["xdotool", "getdisplaygeometry"], env=self.env, capture_output=True).returncode == 0:
                return
            time.sleep(0.2)
        raise RuntimeError("Xvfb did not start")

    def boot(self, iso: Path, log: Path):
        (self.dir / "run").mkdir(exist_ok=True)
        for f in (self.dir / "sstates").glob("*.p2s"):
            f.unlink()
        for attempt in range(6):  # PCSX2 1.7.4000 sometimes dies at startup: relaunch until the ELF runs
            subprocess.run(["pkill", "-9", "-f", "pcsx2-qt"])
            time.sleep(1)
            with open(log, "w") as lf:
                proc = subprocess.Popen(["./pcsx2-qt", "-nogui", "-fastboot", "--", str(iso)], cwd=self.dir,
                                        env=self.env, stdout=lf, stderr=subprocess.STDOUT)
            for _ in range(20):
                time.sleep(1)
                if proc.poll() is not None:
                    break
                if b"ELF (cdrom0" in log.read_bytes():
                    print(f"  PCSX2 booted (attempt {attempt + 1})")
                    return
        raise RuntimeError("PCSX2 failed to boot")

    def _focus(self):
        w = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", "Ibara"], env=self.env,
                           capture_output=True, text=True).stdout.split()
        if w:
            subprocess.run(["xdotool", "windowfocus", "--sync", w[0]], env=self.env, capture_output=True)

    def key(self, k, hold=0.2, after=0.0):
        self._focus()
        subprocess.run(["xdotool", "keydown", k], env=self.env)
        time.sleep(hold)
        subprocess.run(["xdotool", "keyup", k], env=self.env)
        time.sleep(after)

    def down(self, k):
        self._focus()
        subprocess.run(["xdotool", "keydown", k], env=self.env)

    def stop(self):
        subprocess.run(["pkill", "-9", "-f", "pcsx2-qt"])
        subprocess.run(["pkill", "-9", "-f", f"Xvfb {self.display}"])


def build_logger_iso(args, work: Path) -> Path:
    elf, iso = work / "KURO_LOG.ELF", work / "logger.iso"
    defines = ["BL_SPAWN_LOG", f"BL_LOG_STAGE={args.stage + 1}", f"BL_BOSS_TYPE={args.boss_type}u"]
    if args.rank is not None:
        defines.append(f"BL_SPAWN_RANK=0x{args.rank:08X}u")
    if args.shot_level is not None:
        defines.append(f"BL_LOCK_SHOT={args.shot_level}")
    if args.noshot:
        defines.append("BL_NOSHOT")
    defines += args.define
    cmd = [sys.executable, str(ROOT / "scripts/build_ee_hooks.py"), "--elf", str(args.retail_iso)]
    for d in defines:
        cmd += ["--define", d]
    sh(cmd + ["--bake-elf", "bl_mode", str(elf)], stdout=subprocess.DEVNULL)
    sh([sys.executable, str(ROOT / "research/phase04/build_menu_probe.py"), str(args.retail_iso),
        "--payload-elf", str(elf), "--label", "BL LOG", "--output", str(iso)], stdout=subprocess.DEVNULL)
    return iso


def extract_ps2(p2s: Path, out: Path):
    from p2s_tools import load_ee
    r = load_ee(p2s)
    n = struct.unpack_from("<I", r, 0x1F20000)[0]
    with open(out / "ps2_spawns.txt", "w") as f:
        for i in range(n):
            fr, slot, hp, t, sub, sc, x, y = struct.unpack_from("<IHHIIIhh", r, 0x1F20010 + 24 * i)
            f.write(f"{fr} {slot} {t} {sub:08X} {hp} {sc} {x} {y}\n")
    m = struct.unpack_from("<I", r, 0x1F40000)[0]
    with open(out / "ps2_bullets.txt", "w") as f:
        for i in range(m):
            fr, t, slot, _p, x, y, dx, dy = struct.unpack_from("<IHBBhhhh", r, 0x1F40010 + 16 * i)
            f.write(f"{fr} {slot} {t} {x} {y} {dx / 256:.3f} {dy / 256:.3f}\n")
    c = min(struct.unpack_from("<I", r, 0x1F60000)[0], 8000)
    with open(out / "ps2_core.txt", "w") as f:
        for i in range(c):
            fr, slot, hp, sub, x, y, mode, step = struct.unpack_from("<IHHIhhBB", r, 0x1F60010 + 20 * i)
            f.write(f"{fr} {slot & 0xFF} {hp} {sub:08X} {x} {y} {mode} {step}\n")
    ns = min(struct.unpack_from("<I", r, 0x1FD0000)[0], 30000)
    if ns:  # BL_SHOT_LOG: frame slot type +8 +C
        with open(out / "ps2_shots.txt", "w") as f:
            for i in range(ns):
                a, b = struct.unpack_from("<II", r, 0x1FD0010 + 8 * i)
                f.write(f"{a >> 8} {a & 0xFF} {b >> 16 & 0xFF} {b >> 8 & 0xFF} {b & 0xFF}\n")
    t = min(struct.unpack_from("<I", r, 0x1FC0000)[0], 512)
    with open(out / "ps2_tables.txt", "w") as f:
        for i in range(t):
            ty, tb = struct.unpack_from("<II", r, 0x1FC0010 + 8 * i)
            f.write(f"{ty} {tb:08X}\n")
    print(f"  PS2: {n} spawns, {m} bullets, {c} boss samples; scene counter now {r[0x338E9C]}")
    if n == 0:
        print("  WARNING: nothing logged - the capture ended before the stage started (raise --seconds)")


def run_ps2(args, out: Path):
    with tempfile.TemporaryDirectory() as tmp:
        print("PS2: building the logger ISO ...")
        iso = build_logger_iso(args, Path(tmp))
        x = Xpcsx2(args.pcsx2_dir)
        try:
            x.start_x()
            x.boot(iso, out / "pcsx2.log")
            # title -> Start, Mode Select: Up to the sixth row (BL LOG), Circle; in the BL game: Start, Start,
            # Circle x3 = Arcade, Normal, default ship
            time.sleep(24)
            for k, wait in (("Return", 3), ("Up", 1), ("x", 30), ("Return", 6), ("Return", 3), ("x", 5), ("x", 4),
                            ("x", 3)):
                x.key(k, after=wait)
            x.down("z")  # hold shot; with --noshot the logger build still shoots: see README
            secs = args.seconds or 60 + 240 * args.stage
            print(f"  playing for {secs} s ...")
            time.sleep(secs)
            x.key("F1", hold=0.15, after=5)
            states = sorted((args.pcsx2_dir / "sstates").glob("*.p2s"), key=lambda p: p.stat().st_mtime)
            if not states:
                raise RuntimeError("no savestate written (F1)")
            shutil.copy(states[-1], out / "ps2.p2s")
        finally:
            x.stop()
    extract_ps2(out / "ps2.p2s", out)


def run_bl(args, out: Path):
    print("BL: running MAME ...")
    env = dict(os.environ, OUTDIR=str(out), STAGE=str(args.stage + 1), BOSSTYPE=str(args.boss_type), MAXFRAMES=str(9000 * args.stage + 3000))
    if args.rank is not None:
        env["RANKLOCK"] = str(args.rank)
    if args.shot_level is not None:
        env["SHOTLOCK"] = str(args.shot_level)
    if args.noshot:
        env["NOSHOT"] = "1"
    tmp = out / "bl_tmp"
    tmp.mkdir(exist_ok=True)
    env["OUTDIR"] = str(tmp)
    sh([args.mame, "ibarablk", "-rompath", str(args.bl_roms), "-video", "none", "-sound", "none", "-nothrottle",
        "-autoboot_script", str(ROOT / "tools/stage_compare/bl_stage_log.lua"), "-skip_gameinfo"], env=env,
       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for name in ("spawns", "bullets", "core", "tables", "shots"):
        if not (tmp / f"{name}.txt").exists():
            continue
        shutil.move(tmp / f"{name}.txt", out / f"bl_{name}.txt")
    tmp.rmdir()
    print(f"  BL: {sum(1 for _ in open(out / 'bl_spawns.txt'))} spawns, "
          f"{sum(1 for _ in open(out / 'bl_bullets.txt'))} bullets")


def compare(args, out: Path):
    import contextlib
    import io
    import compare_bullets
    import compare_spawns
    anchor = args.anchor_type
    if anchor is None:  # first type spawned in the BL log
        anchor = int(open(out / "bl_spawns.txt").readline().split()[3])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        compare_spawns.main([str(out / "bl_spawns.txt"), str(out / "ps2_spawns.txt"), "--stage", str(args.stage + 1),
                             "--anchor-type", str(anchor)])
    (out / "compare_spawns.txt").write_text(buf.getvalue())
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        compare_bullets.main(str(out / "bl_spawns.txt"), str(out / "bl_bullets.txt"), str(out / "ps2_spawns.txt"),
                             str(out / "ps2_bullets.txt"), anchor=anchor)
    (out / "compare_bullets.txt").write_text(buf.getvalue())
    print(f"Wrote {out / 'compare_spawns.txt'} and {out / 'compare_bullets.txt'} (aligned at type {anchor})")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", type=int, required=True, choices=range(1, 7), help="stage 1..6")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--retail-iso", type=Path)
    ap.add_argument("--pcsx2-dir", type=Path, help="directory holding a configured pcsx2-qt")
    ap.add_argument("--mame", default="mame")
    ap.add_argument("--bl-roms", type=Path, help="rompath containing ibarablk")
    ap.add_argument("--rank", type=lambda s: int(s, 0), default=0x800000, help="stored rank to lock; -1 = free")
    ap.add_argument("--shot-level", type=int)
    ap.add_argument("--boss-type", type=int, default=5, help="enemy type sampled into *_core.txt (stage 1: 5, 2: 45)")
    ap.add_argument("--noshot", action="store_true", help="untouched boss: refill --boss-type parts' HP every frame in both games")
    ap.add_argument("--seconds", type=int, help="PS2 capture length (wall clock)")
    ap.add_argument("--define", action="append", default=[],
                    help="extra logger define, e.g. BL_CORE_EVERY / BL_CORE_HIT (MAME side: set EVERY=1 / HIT=1)")
    ap.add_argument("--anchor-type", type=int, help="enemy type used to align the logs (default: BL's first)")
    ap.add_argument("--skip-bl", action="store_true")
    ap.add_argument("--skip-ps2", action="store_true")
    args = ap.parse_args(argv)
    if args.rank == -1:
        args.rank = None
    args.out.mkdir(parents=True, exist_ok=True)
    if not args.skip_bl:
        if not args.bl_roms:
            ap.error("--bl-roms is required (or --skip-bl)")
        run_bl(args, args.out)
    if not args.skip_ps2:
        if not (args.retail_iso and args.pcsx2_dir):
            ap.error("--retail-iso and --pcsx2-dir are required (or --skip-ps2)")
        run_ps2(args, args.out)
    compare(args, args.out)


if __name__ == "__main__":
    main()
