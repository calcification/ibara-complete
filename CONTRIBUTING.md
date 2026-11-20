# Contributor rules

1. Do not commit commercially distributed Ibara data or extracted graphics/sounds: retail ISO, PS2 ELF, arcade Kuro ROMs, PS2 textures, gameplay captures containing unlicensed repackaging, or derivative assembled game binaries. Synthetic `KURO_PROBE.ELF` is allowed.
2. For any candidate MIPS patch: show ELF SHA-256, EE virtual address, file/ISO offset mapping, **original 4-byte opcode**, proposed new opcode, preservation/regression test, and conditional status. Write through a new output file only.
3. Distinguish verified instructions from semantics inferred from comments. Branch delay slots, signed 16-bit immediates, MIPS instruction alignment and PS2 EE ABI require explicit review.
4. Independent gameplay measurements must identify PCSX2/BIOS version, renderer, game revision, ISO checksum and capture conditions. On-console claims require separate evidence.
5. Respect old phase errata and add new errata rather than silently rewriting history.
6. Do not modify Arcade/Arrange functionality when prototyping a third mode without a byte-level proof of isolation and regression tests.
7. External `ibara360` source is a reference, not proven permissively licensed input. Seek authorization if code reuse is proposed.
