# Ibara Arcade slowdown hardware test

This test lets you switch between normal speed and half-speed gameplay during a
retail Arcade run. Half speed holds every other gameplay update while the PS2
continues refreshing the display. The test uses a fixed cadence to check the
patch on a console.

## Build the ISO on a Mac

1. Download the branch ZIP using GitHub’s **Code → Download ZIP** and unzip it.
   Keep the clean Japanese **Ibara (Japan).iso** handy. You only need the PS2 ISO
   and Python 3.10 or later.
2. In Terminal, type `cd ` (with a space), drag the unzipped repository folder
   into Terminal, and press Return.
3. If your clean ISO is in Downloads, run the following command. For a different
   location, replace the first quoted path with the path to your clean ISO.

   ```sh
   python3 patcher/apply_slowdown_test.py "$HOME/Downloads/Ibara (Japan).iso" \
     --output "$HOME/Downloads/Ibara-Slowdown-Test.iso"
   ```

4. Load **Ibara-Slowdown-Test.iso** with the same setup you use to run Ibara on
   your PS2.

## Trigger the test

1. Choose **Arcade → Practice → Stage 1**. Start the stage and wait until you can
   move the ship. Arcade Normal works too.
2. On controller 1, press **L2 + R2 together**, then release both buttons.
   Scrolling, ship movement, enemies, and bullets should run at roughly half
   speed.
3. Press and release **L2 + R2** again. Gameplay should return to normal speed
   immediately. You can repeat the toggle during the same run.

The test starts at normal speed each time you boot the ISO. The toggle works
during active Arcade gameplay. For a quick check, compare movement, shooting,
and bombing on each side of the toggle and check that Start still pauses and
resumes. If you report a freeze, include what was happening when you toggled
and how you loaded the ISO.

The patched ISO was cold-booted in PCSX2 2.8.2 with cheats disabled. Stage 1 ran
at one update per refresh at boot, switched to alternating holds with the
first chord, and returned to one update per refresh with the second chord.

## Rebuild the hook from source

The Python patcher uses the checked-in hook words from
`ps2/prebuilt/arcade_slowdown_hw.json`. To regenerate them with the repository’s
MIPS n32 toolchain, use an unused output path.

```sh
python3 research/phase22/build_slowdown.py "Ibara (Japan).iso" \
  --export-hardware --output arcade_slowdown_hw.json
```
