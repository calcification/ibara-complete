import tempfile,zipfile,sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pathlib import Path
from src.analyze_vram_trace import estimate
from src.check_kuro_roms import inspect
r=estimate(Path('tests/sample_trace.csv'),4)
assert r['resident_tiles']==15, r
assert r['overflow_first_frame']==1, r
assert r['max_touched_tiles_per_frame']==8, r
with tempfile.TemporaryDirectory() as d:
    z=Path(d)/'empty.zip'
    with zipfile.ZipFile(z,'w') as f:f.writestr('nonsense.bin',b'abc')
    j=inspect(z)
    assert not j['archive_matches_all']
    assert len(j['chips'])==4 and all(c['status']=='missing' for c in j['chips'])
print('PASS: trace estimator / overflow / ROM verifier rejection')
