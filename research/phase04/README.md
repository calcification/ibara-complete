# Ibara Complete — Phase 4: Retail mode selector and asset-only Black Label button

**Date:** November 19–20, 2026  
**Starting ISO:** Original Japanese retail PS2 Ibara (`SLPM_663.01`)  
**Purpose:** Work that does not depend on the Phase 3 secondary-ELF bootstrap being tested.  
**Current status:** Static menu path and asset pipeline verified. No menu hook or functioning Kuro mode yet.

## 1. The actual top-level five-way selector is now located

The earlier Phase 1 work found the inner Arcade and Arrange menu dispatchers. Phase 4 located the *higher-level* menu using direct MIPS disassembly of the original executable and comparison with the retail texture artwork.

- **Frontend function:** begins at EE `0x001C9400` (called from `0x00113634`).
- **Top-level input / drawing:** starts near `0x001CA42C`.
- **Accept-button dispatch:** starts at `0x001CA798`.
- **Selection cursor:** `-0x686C($gp)` (actual absolute address depends on `$gp` at runtime).

| Index | Retail label | Dispatch point | Result inferred from the original instruction path |
|---:|---|---|---|
| 0 | ARCADE MODE | `0x001CA800` | Sets frontend state `2` (Arcade submenu) |
| 1 | ARRANGE MODE | `0x001CA824` | Sets frontend state `9` (Arrange submenu) |
| 2 | GALLERY | `0x001CA848` | Sets frontend return value `2` (Gallery request to caller) |
| 3 | OPTION | `0x001CA860` | Sets frontend state `13` (Options) |
| 4 | EXIT | `0x001CA7E4` | Sets frontend return value `1` (Exit request) |

The `0x001C9400` frontend routine returns to the larger game state machine at `0x00113634`; returned values distinguish a Gallery request from exiting. **These are statically determined paths, not yet runtime breakpoint confirmations.**

## 2. What must change for six selections

Four distinct MIPS `slti ...,5` instructions enforce the current menu bounds:

| EE address | Original instruction word | Hypothetical `...,6` word | Purpose |
|---|---|---|---|
| `0x001CA44C` | `0x28410005` | `0x28410006` | Downward cursor bounds |
| `0x001CA494` | `0x29020005` | `0x29020006` | Animation iteration |
| `0x001CA56C` | `0x28880005` | `0x28880006` | Item highlight/render loop |
| `0x001CA6DC` | `0x2A020005` | `0x2A020006` | Remaining draw-loop bound |

Also required: upward wrap currently returns to index `4` at `0x001CA720`; accept dispatch has explicit cases only for `0..4`, and the five menu anchors are explicitly initialized, not dynamically generated.

**Do not apply only these four changes.** Doing so would expose an incomplete sixth entry and could dereference invalid graphics descriptors. They are machine-checked planning data, not a finished patch.

Existing item Y-like seed coordinates: `[0xD8, 0xB8, 0x98, 0x78, 0x58]`, a 32-unit step. A sixth item could logically use `0x38`, pending layout review. The three scratch arrays start at `0x00500620`, `0x00500640` and `0x00500660`; their next candidate item words are `0x00500634`, `0x00500654`, `0x00500674`. The addresses fit before the next 32-byte array boundaries but that fact alone does not prove every location is safe at runtime.

### Important refinement about the graphics pointer table

The top-level draw table begins at `0x002A90B0`; entries are structured as five **pairs** of pointers to 16-byte graphics descriptors. After the fifth pair, **two full 32-bit words at `0x002A90D8` and `0x002A90DC` are both zero**. Another data table begins at `0x002A90E0`.

Therefore, an additional pointer pair **might fit in place** without relocating the original table. However, the new 16-byte texture descriptor(s) still need an independently verified storage location, and the rendering pipeline must be patched to use them. Do not mistake the blank pointers for a guaranteed complete sixth menu implementation.

## 3. Real retail artwork: the missing button fits

The original `IBARAR.PDM` resource **#946**, at PDM byte offset `0x2D31000`, is a 256×256 8-bit indexed TIM2 texture (256-entry RGBA palette). It contains five ornate metallic mode buttons. The area `(x=112..223, y=96..143)` is exactly **112×48 pixels, fully transparent**—the same dimensions as one existing menu button. Resource #945 contains related labels/descriptions.

The accompanying **asset-only** prototype script:

1. Reads the user's own original ISO and validates its original boot ELF hash, `IBARAR.TBL` format, resource ID and TIM2 size.
2. Reuses the artwork of the `EXIT` button for its plate, removes the original four-letter label, and renders a placeholder `BLACK LABEL` using a system font. It is a **stylistic prototype**, not final game artwork.
3. Quantizes the new pixels back into the original game's unchanged indexed CLUT.
4. Writes the new 112×48 index region **without resizing** the resource, altering the table, or shifting any resource offsets.
5. Optionally writes a new ISO copy; never edits the source ISO in place.

The new button currently exists **only in the texture's unused atlas slot**. The unchanged retail menu does **not** draw or select it.

## 4. Actual offline test results

We generated an asset-only ISO copy and compared **all 3,932,848,128 bytes** of the copy against the original retail ISO.

- Changed bytes: **5,376** (`112 × 48` texture index bytes).
- Changed bytes outside the reserved atlas rectangle: **0**.
- Source ISO remains unchanged.
- ISO9660 file table, file lengths, original file extents, retail `SLPM_663.01`, `ALLIMAGE.DAT`, and `IBARAR.TBL`: byte-identical.
- Only the intended bytes inside `IBARAR.PDM` changed. The PDM's CRC32 will therefore change by design.
- No runtime graphics, menu, or console boot test was performed.

`Ibara_Complete_Phase4_Full_Diff_Audit.json` contains the full-copy validation metadata. The 3.7 GB ISO image is **not** bundled.

## 5. Reproducing this work (Windows/macOS/Linux)

Extract the user's own `Ibara (Japan).iso` from their 7z using 7-Zip or another extractor. Put these three scripts next to each other:

- `ibara_complete_audit.py` (read-only ISO/ELF support)
- `ibara_complete_menu_map.py` (new read-only selector analysis)
- `ibara_complete_button_prototype.py` (new asset-only prototype)

To reproduce the detailed menu map and debugger breakpoint list (Python standard library only):

```bash
python ibara_complete_menu_map.py "Ibara (Japan).iso" --out menu_map.json --breakpoints PCSX2_BREAKPOINTS.txt
```

To generate an *asset-only preview* from your ISO, first install Pillow and NumPy; OpenCV is optional:

```bash
python -m pip install pillow numpy
python ibara_complete_button_prototype.py "Ibara (Japan).iso" --preview button_preview.png --report button_report.json
```

To make a **separate ISO copy** with only the otherwise-invisible new button:

```bash
python ibara_complete_button_prototype.py "Ibara (Japan).iso" --apply-to "Ibara Complete ASSET ONLY.iso"
```

This will write a full-size ISO (3.93 billion bytes); it should still boot the *unchanged* retail game, but that behavior has not been confirmed by PCSX2/PS2. The asset-only ISO is not the same as the Phase 3 ELF bootstrap test, and **it does not enable Black Label**.

## 6. Recommended next implementation work

- **Menu hook design:** introduce a new third logical selection (`Arcade, Arrange, Black Label, Gallery, Option, Exit`) while preserving the behavior of the five existing entries, and allocate 16-byte graphic descriptors for the added atlas button. An alternative is a temporary developer-only shortcut that selects Kuro without expanding the five-entry UI.
- **Asset visual polish:** replace placeholder button lettering with lettering reconstructed from the game's font/graphics. The raw texture slot and repacking constraints are now known.
- **Self-contained launcher:** after the Phase 3 boot smoke test, build a trampoline or separate ELF loader at the new selection path. Validate that Original/Arrange/gallery/options/exit still return safely and saves are isolated.
- **Kuro engine:** independently benchmark ported recompiled game logic, memory and rendering demands before promising arcade-perfect PS2 performance. The separate `ibara360` project and arcade ROM data remain relevant; this retail ISO does not contain Kuro's arcade program.

**License/distribution:** this package includes code, findings, and addresses only, not Cave's PS2 executable, ISO, arcade ROMs, or extracted TIM2 pixel art. The original user's own ISO is required to regenerate all resources.
