# PCSX2 session helpers (headless, Xvfb :50)

Used for every PCSX2 check in phases 19-21. Set `WORK` to a directory holding `ext/pcsx2/build/bin/pcsx2-qt`
(a configured PCSX2 build; PINE was not serving in it), `runs/` (screenshots, logs) and `runs/t1.png` (a reference
screenshot of the retail Mode Select header, used by `tomenu.sh`; take one with `ctl.sh shot t1` the first time and
never overwrite it).

    export WORK=/path/to/work
    ./session.sh game.iso            # fresh Xvfb + PCSX2, waits for the ELF
    ./tomenu.sh                      # Start until Mode Select
    ./ctl.sh key Down; ./ctl.sh key Down; ./ctl.sh key x   # KURO row, Circle
    ./ctl.sh down z; ./ctl.sh up z   # hold / release Cross (shot)
    ./ctl.sh shot name               # runs/name.png
    ./ctl.sh key F1                  # savestate -> ext/pcsx2/build/bin/sstates/*.p2s (read with scripts/p2s_tools.py)

Pad keys: Cross = Z (shot), Circle = X (bomb / menu confirm), Square = A, Triangle = S, Start = Return, arrows.
KURO game from Mode Select: Down, Down, X (KURO), X (GAME START), X (NORMAL); the select screen opens when stage 1
runs.
