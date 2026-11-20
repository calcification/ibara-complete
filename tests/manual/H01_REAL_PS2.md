# H01 — Real hardware verification (ONLY AFTER PCSX2 tests)

**Status:** BLOCKED. Physical hardware checks must not be substituted for B01–B04.

1. Require a clean PASS on B02 (injected ISO preserves five original menu choices), and a documented PASS/INCONCLUSIVE of B01 with EE PC evidence.
2. With reliable optical/USB/HDD game-loading infrastructure and an appropriate legally owned retail copy, boot the **retail-injected test ISO** first. Use the user's existing PS2 and PVM; keep captures and monitor model details private.
3. Verify menu, Arcade, Arrange, Gallery, Option, Exit, loading and returning, audiovisual integrity. Compare with clean retail reference.
4. Evaluate the direct-boot probe only **if** PCSX2 execution is proven and the user is comfortable with a homebrew experimental image; don't claim it is guaranteed safe. If GS output is missing, use hardware debugger/serial logs where available, not assumptions from a black screen.
5. Record signal format and display sync; this phase does **not** establish 240p correctness. A 240p integration test is blocked until a combined implementation exists.

Never treat physical media or console execution as guaranteed by a structural ISO verifier; these are separate checks.
