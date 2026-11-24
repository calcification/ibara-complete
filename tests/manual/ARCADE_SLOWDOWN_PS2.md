# Original PS2 checklist for the Arcade slowdown build

The last original PS2 pass was K41, using the K40 disc on November 23, 2026.
It covered the menus, Noir, co-op, Yoko and Tate, and save isolation.
This checklist focuses on the changes in the Arcade slowdown build.
[K41 hardware results](../results/2026-11-20_RUNTIME.md#k41--original-ps2-hardware-pass-2026-11-23)

## Build the test ISO

Download and unzip the [tested branch snapshot](https://github.com/calcification/ibara-complete/archive/cd10f9de6fc5545961cc33c8c580727778aaec5e.zip).
In Terminal, go to the unzipped folder. If both input files are in Downloads, run:

```sh
python3 patcher/apply_kuro_patch.py "$HOME/Downloads/Ibara (Japan).iso" \
  "$HOME/Downloads/Ibara-Arcade-Slowdown.iso" --bl-rom "$HOME/Downloads/ibarablk.zip"
```

Boot the new ISO with your usual PS2 loader. Use controller 1 for the shoulder-button chord.
The menu enables a manual half-speed test. You can do the whole check in Stage 1.

## Run these first

1. **Default Off.** Open **Arcade Mode → Config**. **Slowdown** should be just above **Exit** and
   show **Off**. Move down to **Exit** and confirm with Circle. In **Arcade → Practice → Stage 1**,
   wait until you can control the ship. Press **L2 + R2** together. Scrolling and ship movement
   should continue at normal speed.
2. **On and half speed.** Return to Arcade Config and press Circle on **Slowdown** to select **On**.
   Start the same practice stage. Gameplay should begin at normal speed. Press and hold **L2 + R2**
   for about a second. Scrolling, the ship, and enemies should move at roughly half speed and stay
   there when you release both buttons. Press both again to return to normal speed.
3. **Controls and mode changes.** In half speed, try a quick shot tap, bomb once with stock available,
   and pause and resume with Start. Each action should register once and gameplay should resume
   at half speed. Back in the menus, check that **Noir → Config** has its usual **Exit** row and
   no **Slowdown** entry. Return to Arcade and check that the setting still reads **On**.
   Turn it **Off**, enter play, and confirm the chord leaves the speed at normal.

## If you have another minute

- With Arcade's setting **On**, try the chord in **Arrange Practice**. Gameplay should stay at
  Arrange's normal speed. Try a single chord in **Arcade → Game Start** after takeoff to check
  the same half-speed toggle outside Practice.
- Cold boot and check that Arcade Config shows **Off** again.

For a quick report, send the PS2 model, loader, Yoko or Tate, and **Pass / Fail / Not run** for
each numbered test. For a failure, include the first menu or stage where it happened and the
buttons you pressed. The ship-select music decoder is a patcher tool in this snapshot. The
hardware checklist covers features shipped on the disc.
