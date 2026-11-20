"""Verify test records and documentation for PCSX2-first and legacy phases."""
from pathlib import Path
import csv
R=Path(__file__).resolve().parents[1]
with (R/'TEST_MATRIX.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
assert len(rows)>=29,(len(rows),'expected at least 29 entries')
assert len(set(x['id'] for x in rows))==len(rows)
for r in rows:
 for name in r['instructions_or_file'].split(';'):
  assert (R/name.strip()).is_file(),(r['id'],name)
 assert r['test'] and r['command'] and r['pass_condition'],r
 assert r['status'] in ('READY','OPTIONAL','OPTIONAL_DEFERRED','PENDING','PASS','BLOCKED','NOT_IMPLEMENTED'),r
assert set(f'P{i:02d}' for i in range(8)).issubset({r['id'] for r in rows})
assert (R/'pnach/SLPM-66301_420C7FAB.pnach').exists()
print('PASS:',len(rows),'PCSX2-first and legacy test records and referenced files are present')
