import sys, subprocess
sys.path.insert(0, '/home/user/ibara-complete/tools'); import mc_read
from pathlib import Path
base = mc_read.Card(Path(sys.argv[1]).read_bytes()); c = mc_read.Card(Path(sys.argv[2]).read_bytes())
files = {f: (s, cl) for f, s, cl, _ in c.walk()}
bfiles = {f: (s, cl) for f, s, cl, _ in base.walk()}
ok = subprocess.run([sys.executable, 'tools/mc_read.py', sys.argv[2], '--check'], capture_output=True, text=True).stdout.strip()
print(' fs:', ok)
for f in ('BISLPM-66301/BISLPM-66301', 'BISLPM-66301/icon.sys', 'BISLPM-66301/ibara.ico'):
    print(' game', f.split('/')[1], 'same' if c.read(files[f][1], files[f][0]) == base.read(bfiles[f][1], bfiles[f][0]) else 'CHANGED')
def pat(seed, n):
    x = seed; out = bytearray(n)
    for i in range(n):
        x = (x * 1103515245 + 12345) & 0xffffffff; out[i] = (x >> 16) & 0xff
    return bytes(out)
for f in ('REPLAY1.DAT', 'REPLAY1.DAT.TMP'):
    k = 'BISLPM-66301KURO/' + f
    if k in files:
        d = c.read(files[k][1], files[k][0])
        what = 'pattern 1' if d == pat(1, 300000) else 'pattern 2' if d == pat(2, 300000) else 'PARTIAL/OTHER (%d bytes)' % len(d)
        print(' ', f, what)
print(' files:', sorted(f for f in files if f.startswith('BISLPM-66301KURO')))
