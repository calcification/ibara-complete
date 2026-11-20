"""Check all 21 test procedures and source files exist."""
from pathlib import Path
import csv
R=Path(__file__).resolve().parents[1]
with (R/'TEST_MATRIX.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
assert len(rows)==21,(len(rows),'expected 21')
assert len(set(x['id'] for x in rows))==21
for r in rows:
 assert (R/r['instructions_or_file']).is_file(),r
 assert r['test'] and r['command'] and r['pass_condition'],r
 assert r['status'] in ('READY','OPTIONAL','PENDING','BLOCKED','NOT_IMPLEMENTED'),r
print('PASS: all 21 test records and their files are present')
