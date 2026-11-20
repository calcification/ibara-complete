# B03 — Black Label button texture-only prototype (PCSX2)

**Status:** NOT RUN. Requires `pip install -r requirements-assets.txt` (Pillow and NumPy).

1. Build: `python3 scripts/build_test_images.py "Ibara (Japan).iso" --mode asset --out outputs`.
2. Inspect locally created `outputs/Phase4_Button_Prototype.png`. It is a reconstruction from your **own** retail ISO; do not publish the texture wholesale.
3. Launch `outputs/Ibara Complete ASSET ONLY.iso` in PCSX2. It should behave like unmodified retail and continue to display the five original menu buttons. **The new BLACK LABEL plate should NOT be visible** until a separate drawing-code hook exists.
4. Visit Arcade, Arrange, Gallery, Option and Exit. Record any changed art, weird palettes, corruption, shimmering, hangs. No real hardware until PCSX2 comparison is acceptable.
5. Save before/after offscreen photos or screenshots privately; report exact PCSX2 config and result template.

A successful result proves only that modifying the unused indexed TIM2 texture region did not visibly break the retail menu. It does not create a selectable sixth option.
