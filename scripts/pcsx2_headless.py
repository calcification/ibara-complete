#!/usr/bin/env python3
"""Run Ibara headless in PCSX2 (Linux, Xvfb) with one PNACH profile, scripted input and PINE memory logging.

Built for automated C00/K01-style checks in a container; also usable on a Linux desktop. Requires a Qt
PCSX2 binary (tested with v1.7.4000 built from source), the user's own BIOS and clean ISO, Xvfb and xdotool.
PCSX2 runs in portable mode next to its binary; this script owns that data directory's ini/cheats.

    python3 scripts/pcsx2_headless.py --pcsx2 /path/pcsx2-qt --bios BIOS.bin --iso 'Ibara (Japan).iso' \
        --profile pnach/hooks/h00_smoke/SLPM-66301_420C7FAB.pnach --seconds 120 \
        --watch 000C0000 000C0008 000C000C 0044C600 --script "30:tap:Return" --out run.json

Script steps "T:ACTION:KEY" at T seconds of wall time: tap / down / up (xdotool key names).
Older PCSX2 (< ~1.7.5000) only loads cheats named <CRC>*.pnach, so the profile is installed as 420C7FAB.pnach.
Nothing here is committed: BIOS, ISO, savestates and screenshots stay in the data directory.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pcsx2_pine import Pine  # noqa: E402
from p2s_tools import load_ee  # noqa: E402

CRC = "420C7FAB"
INI = """[UI]
SettingsVersion = 1
ConfirmShutdown = false
StartFullscreen = false
HideMouseCursor = false
[Folders]
Bios = bios
Snapshots = snaps
Savestates = sstates
MemoryCards = memcards
Logs = logs
Cheats = cheats
CheatsWS = cheats_ws
CheatsNI = cheats_ni
Cache = cache
[Filenames]
BIOS = {bios}
[EmuCore]
EnableCheats = {cheats}
EnablePINE = true
PINESlot = 28011
EnableFastBoot = true
EnableWideScreenPatches = false
EnableNoInterlacingPatches = false
[EmuCore/GS]
Renderer = {renderer}
[SPU2/Output]
OutputModule = nullout
[MemoryCards]
Slot1_Enable = true
Slot1_Filename = Mcd001.ps2
Slot2_Enable = false
[Logging]
EnableSystemConsole = true
EnableFileLogging = true
[InputSources]
SDL = false
[Pad1]
Type = DualShock2
Up = Keyboard/Up
Down = Keyboard/Down
Left = Keyboard/Left
Right = Keyboard/Right
Cross = Keyboard/Z
Circle = Keyboard/X
Square = Keyboard/A
Triangle = Keyboard/S
L1 = Keyboard/Q
R1 = Keyboard/W
L2 = Keyboard/E
R2 = Keyboard/R
Start = Keyboard/Return
Select = Keyboard/BackSpace
[Pad2]
Type = None
[Hotkeys]
SaveStateToSlot = Keyboard/F1
Screenshot = Keyboard/F8
"""


def setup(data: Path, bios: Path, profile: Path | None, renderer: int):
    for d in ("inis", "bios", "cheats", "cheats_ws", "cheats_ni", "sstates", "memcards", "snaps", "logs", "cache"):
        (data / d).mkdir(parents=True, exist_ok=True)
    (data / "portable.ini").touch()
    dst = data / "bios" / bios.name
    if not dst.exists():
        shutil.copy2(bios, dst)
    for old in (data / "cheats").glob("*.pnach"):
        old.unlink()
    if profile:
        shutil.copy2(profile, data / "cheats" / f"{CRC}.pnach")
    (data / "inis" / "PCSX2.ini").write_text(
        INI.format(bios=bios.name, cheats="true" if profile else "false", renderer=renderer))


def xdo(display: str, *args: str):
    """Send input to the game window. Without a window manager nothing holds focus, so focus the
    largest visible window first (the render window, titled with the game's name)."""
    env = {**os.environ, "DISPLAY": display}
    if args and args[0] in ("key", "keydown", "keyup"):
        ids = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", "."], env=env,
                             capture_output=True, text=True).stdout.split()
        best, area = None, 0
        for w in ids:
            g = subprocess.run(["xdotool", "getwindowgeometry", w], env=env, capture_output=True, text=True).stdout
            if "Geometry:" in g:
                wd, ht = g.split("Geometry:")[1].strip().split("x")
                if int(wd) * int(ht) > area:
                    best, area = w, int(wd) * int(ht)
        if best:
            subprocess.run(["xdotool", "windowfocus", "--sync", best], env=env, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if args and args[0] == "key":  # hold ~7 frames: the game polls the pad once per frame
        args = ("keydown", args[1], "sleep", "0.12", "keyup", args[1])
    subprocess.run(["xdotool", *args], env=env, check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def snapshot(args, data: Path, snapdir: Path, now: float) -> dict:
    """F1 = save to the current slot; wait for the file to change, keep a copy, read the watched words."""
    before = {p: p.stat().st_mtime for p in (data / "sstates").glob("*.p2s")}
    xdo(args.display, "key", "F1")
    sample = {"t": round(now, 1), "via": "savestate"}
    for _ in range(40):
        time.sleep(0.25)
        new = [p for p in (data / "sstates").glob("*.p2s") if before.get(p) != p.stat().st_mtime]
        if new:
            time.sleep(0.5)  # let the writer finish
            dst = snapdir / f"t{int(now):04d}.p2s"
            shutil.copy2(new[0], dst)
            sample["state"] = dst.name
            try:
                ram = load_ee(dst)
                for a in args.watch:
                    v = int.from_bytes(ram[int(a, 16):int(a, 16) + 4], "little")
                    sample[a.upper()] = f"{v:08X}"
            except (ValueError, SystemExit) as e:
                sample["error"] = str(e)
            break
    else:
        sample["error"] = "no savestate written"
    if shutil.which("import"):
        subprocess.run(["import", "-window", "root", str(snapdir / f"t{int(now):04d}.png")],
                       env={**os.environ, "DISPLAY": args.display}, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return sample


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pcsx2", type=Path, required=True)
    ap.add_argument("--bios", type=Path, required=True)
    ap.add_argument("--iso", type=Path, required=True)
    ap.add_argument("--profile", type=Path, help="single-group PNACH to install (omit = cheats off)")
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--watch", nargs="*", default=[])
    ap.add_argument("--script", nargs="*", default=[], help="T:tap|down|up:KEY")
    ap.add_argument("--savestate-at", nargs="*", default=[], help="T:SLOT (PINE only)")
    ap.add_argument("--snapshot-every", type=float, default=0,
                    help="seconds between F1 savestates read offline (works without PINE, e.g. v1.7.4000 Qt)")
    ap.add_argument("--snapdir", type=Path, help="where to keep snapshot .p2s/.png (default: next to --out)")
    ap.add_argument("--renderer", type=int, default=13, help="13 software, 11 null, 12 OpenGL")
    ap.add_argument("--display", default=":99")
    ap.add_argument("--out", type=Path, default=Path("pcsx2_run.json"))
    args = ap.parse_args(argv)

    data = args.pcsx2.resolve().parent
    setup(data, args.bios.resolve(), args.profile, args.renderer)
    xvfb = None
    if not os.environ.get("DISPLAY") or args.display != os.environ.get("DISPLAY"):
        # pick a display with no stale lock, then wait until it answers (a dead X server makes Qt segfault)
        n = int(args.display.lstrip(":"))
        while Path(f"/tmp/.X{n}-lock").exists() or Path(f"/tmp/.X11-unix/X{n}").exists():
            n += 1
        args.display = f":{n}"
        xvfb = subprocess.Popen(["Xvfb", args.display, "-screen", "0", "1280x960x24", "-nolisten", "tcp"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            if subprocess.run(["xdotool", "getdisplaygeometry"], env={**os.environ, "DISPLAY": args.display},
                              capture_output=True).returncode == 0:
                break
            time.sleep(0.2)
    env = {**os.environ, "DISPLAY": args.display, "QT_QPA_PLATFORM": "xcb", "XDG_RUNTIME_DIR": str(data / "run")}
    (data / "run").mkdir(exist_ok=True)
    os.chmod(data / "run", 0o700)
    sock = data / "run" / "pcsx2.sock"
    if sock.exists():
        sock.unlink()
    log = open(data / "logs" / "stdout.txt", "w")
    for attempt in range(3):  # v1.7.4000 occasionally segfaults during Qt start-up; relaunch
        proc = subprocess.Popen([str(args.pcsx2), "-nogui", "-fastboot", "--", str(args.iso.resolve())],
                                env=env, stdout=log, stderr=subprocess.STDOUT, cwd=data)
        time.sleep(4)
        if proc.poll() is None:
            break
        log.write(f"\n[harness] start-up exit {proc.returncode}, relaunching\n")
    steps = sorted((float(t), a, k) for t, a, k in (s.split(":", 2) for s in args.script))
    states = sorted((float(t), int(s)) for t, s in (x.split(":") for x in args.savestate_at))
    result = {"profile": str(args.profile) if args.profile else None, "samples": [], "events": []}
    snapdir = args.snapdir or args.out.parent / (args.out.stem + "_snaps")
    snapdir.mkdir(parents=True, exist_ok=True)
    next_snap = args.snapshot_every or float("inf")
    t0 = time.time() - 4  # include the start-up wait
    pine = None
    try:
        while time.time() - t0 < args.seconds and proc.poll() is None:
            now = time.time() - t0
            while steps and steps[0][0] <= now:
                _, action, key = steps.pop(0)
                xdo(args.display, {"tap": "key", "down": "keydown", "up": "keyup"}[action], key)
                result["events"].append({"t": round(now, 1), "input": f"{action}:{key}"})
            if pine is None and sock.exists():
                try:
                    pine = Pine(path=str(sock))
                    result["events"].append({"t": round(now, 1), "pine": "connected"})
                except OSError:
                    pine = None
            if pine is not None:
                try:
                    if "game" not in result:
                        result["game"] = {"id": pine.game_id(), "title": pine.title(), "version": pine.version()}
                    while states and states[0][0] <= now:
                        _, slot = states.pop(0)
                        pine.save_state(slot)
                        result["events"].append({"t": round(now, 1), "savestate": slot})
                    vals = {a.upper(): f"{pine.read(int(a, 16)):08X}" for a in args.watch}
                    result["samples"].append({"t": round(now, 1), "status": pine.status(), **vals})
                except (OSError, RuntimeError) as e:
                    result["events"].append({"t": round(now, 1), "pine_error": str(e)})
            if pine is None and now >= next_snap:
                next_snap += args.snapshot_every
                result["samples"].append(snapshot(args, data, snapdir, now))
            time.sleep(args.interval)
        result["exit_code"] = proc.poll()
    finally:
        if pine:
            pine.close()
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        if xvfb:
            xvfb.terminate()
        log.close()
    args.out.write_text(json.dumps(result, indent=1) + "\n")
    print(f"wrote {args.out}: {len(result['samples'])} samples, game={result.get('game')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
