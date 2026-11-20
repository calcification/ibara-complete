# Publishing a dedicated GitHub repository

Recommended destination: `calcification/ibara-complete` (a new repo separate from `calcification/cave-ps2-240p`).

This project was prepared as a complete local Git repository. Your connected GitHub integration exposes file and branch editing but **not creation of a new repository**, so a new remote repo must first be created by its owner. Publishing from a local computer:

1. Visit https://github.com/new and create a **public** repo named `ibara-complete` under `calcification`, with **no README, .gitignore or license initialization** (they already exist here).
2. Extract the Git-ready ZIP (including its `.git` directory), open a terminal in the extracted `ibara-complete` directory.
3. Run:

```bash
git remote add origin https://github.com/calcification/ibara-complete.git
git branch -M main
git push -u origin main
```

Alternatively, with GitHub CLI authenticated:

```bash
gh repo create calcification/ibara-complete --public --source . --remote origin --push
```

### No terminal required (GitHub Desktop on Windows or macOS)

1. Unzip the **Git-ready** archive. Keep the hidden `.git` directory inside the `ibara-complete` folder.
2. Open [GitHub Desktop](https://desktop.github.com/) and choose **File → Add local repository**, selecting that folder.
3. Choose **Publish repository**; use name `ibara-complete`, owner `calcification`, visibility **Public**.
4. Confirm the new repository page has `docs/HANDOFF.md`, `docs/TESTING.md`, `TEST_MATRIX.csv`, and the `research/` directory.

The ChatGPT GitHub connection here did not expose a **create repository** action, so these steps need to be completed on your account before the dedicated GitHub link will work.

No ISO, retail ELF or ROM is committed. Before any publication, verify `git ls-files` contains only source, structured metadata, docs, small synthetic test ELF/object and no copyrighted data. Do not upload generated 3.66 GiB test images or local `outputs/`.

If you've extracted the **source-only** ZIP without `.git`, do `git init -b main && git add . && git commit -m "Initial Ibara Complete research handoff"` before the `git remote add` / `git push` commands.

## Handoff to another model

Provide the repository URL, the exact requested next goal, and `docs/HANDOFF.md`. A good independent-research prompt is:

> Review `docs/HANDOFF.md`, `docs/ERRATA.md`, `docs/STATUS.md`, and `docs/TESTING.md` first. Independently verify the cited EE MIPS routines against the user's clean original `SLPM_663.01` using the repo auditors and Ghidra. Do not assume Phase 6–7 address examples or static interpretations are correct. Keep Original/Arrange intact. My immediate goal is [specific task]. No functional Kuro port currently exists. Report instruction evidence, uncertainties, and exact runnable tests.
