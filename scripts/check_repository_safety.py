"""Reject accidentally bundled game data. Use alongside .gitignore and git ls-files."""
from pathlib import Path
R=Path(__file__).resolve().parents[1]
BAD={'.iso','.7z','.rar','.chd','.cue','.img','.cso','.zso','.nrg','.bin','.rom','.xex','.png','.jpg','.jpeg','.webp'}
exceptions={R/'tests/fixtures/KURO_PROBE.ELF',R/'research/phase05/results/cv1k_memory_mips3.o'}
fs=[p for p in R.rglob('*') if p.is_file() and not any(x in {'.git','__pycache__','outputs','validation-output'} for x in p.relative_to(R).parts)]
for p in fs:
 assert p.suffix.lower() not in BAD,p
 if p in exceptions:continue
 assert p.suffix.lower() not in {'.elf','.o','.exe','.dll','.so'},p
 assert p.stat().st_size<2_000_000,(p,p.stat().st_size)
 with p.open('rb') as f:head=f.read(4)
 assert head!=b'\x7fELF' and head[:2]!=b'MZ',f'Unexpected executable without extension: {p}'
assert (R/'tests/fixtures/KURO_PROBE.ELF').stat().st_size==160
print('PASS:',len(fs),'files, no copied commercial game data or large binaries')
