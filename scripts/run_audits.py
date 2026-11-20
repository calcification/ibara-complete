#!/usr/bin/env python3
"""Validate clean retail Ibara against phases 1-10; no game files are modified.
Usage: python scripts/run_audits.py 'Ibara (Japan).iso' [--out validation-output] [--full]
       python scripts/run_audits.py --selftest
"""
import argparse,hashlib,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ELF_SHA='263d3079dee66af82815219351553075340a4d9f42aceaa7bb8ef2bfb812ffac'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',nargs='?',type=Path)
    p.add_argument('--out',type=Path,default=Path('validation-output'))
    p.add_argument('--full',action='store_true')
    p.add_argument('--selftest',action='store_true')
    p.add_argument('--no-native',action='store_true')
    a=p.parse_args()
    if not a.selftest and not a.source:p.error('Provide original ISO/ELF or --selftest')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    phase=lambda x:ROOT/f'research/phase{x:02d}'
    records=[];py=sys.executable
    def run(name,cmd,work=None,env=None):
        print('RUN',name,flush=True)
        try:
            v=subprocess.run([str(c) for c in cmd],cwd=work or ROOT,env=env,
                             capture_output=True,text=True,errors='replace',timeout=450)
            log=v.stdout+v.stderr;rc=v.returncode
        except Exception as exc:rc=1;log=repr(exc)
        (out/(name+'.log')).write_text(log,encoding='utf-8')
        status='PASS' if rc==0 else 'FAIL';records.append({'id':name,'status':status,'log':name+'.log'})
        print(status,name,flush=True)
        if rc:print(log[-1200:],file=sys.stderr)
    run('P07_pnach_unit',[py,ROOT/'tests/test_pnach.py'],ROOT)
    run('S07_phase05_python',[py,phase(5)/'tests/test_tools.py'],phase(5))
    run('S07_phase05_trace',[py,phase(5)/'src/analyze_vram_trace.py',phase(5)/'tests/sample_trace.csv','--pool-mib','8','--output',out/'phase05_trace.json'],phase(5))
    run('S07_phase05_budget',[py,phase(5)/'src/memory_budget.py'],phase(5))
    if not a.no_native:
        cc=shutil.which('cc') or shutil.which('clang') or shutil.which('gcc')
        if cc:
            with tempfile.TemporaryDirectory(prefix='ibara-native-') as td:
                exe=Path(td)/('native.exe' if os.name=='nt' else 'native')
                run('S06_phase05_compile',[cc,'-std=c11','-O2','-Wall','-Wextra','-Werror',phase(5)/'src/cv1k_memory.c',phase(5)/'tests/test_memory.c','-o',exe],phase(5))
                if exe.is_file():run('S06_phase05_execute',[exe],phase(5))
        else:
            print('SKIP: native Phase 5 requires a local C compiler')
            records.append({'id':'S06_phase05_native','status':'SKIP','reason':'No C compiler'})
    if not a.selftest:
        source=a.source.resolve()
        if not source.is_file():p.error(f'Missing input {source}')
        with source.open('rb') as f:header=f.read(4)
        iso=header!=b'\x7fELF'
        with tempfile.TemporaryDirectory(prefix='ibara-retail-') as td:
            if iso:
                with source.open('rb') as f:
                    f.seek(1919173*2048);elf=f.read(2329648)
                binary=Path(td)/'SLPM_663.01';binary.write_bytes(elf)
            else:binary=source;elf=source.read_bytes()
            digest=hashlib.sha256(elf).hexdigest()
            if digest!=ELF_SHA:p.error('Wrong retail revision / modified 240p executable: '+digest)
            run('P07_pnach_source',[py,ROOT/'tests/test_pnach.py',binary],ROOT)
            env=dict(os.environ,IBARA_ORIGINAL_ELF=str(binary))
            run('S01_phase01',[py,phase(1)/'ibara_complete_audit.py',source,'--json',out/'phase01.json'],phase(1),env)
            if iso:
                cmd=[py,phase(2)/'ibara_complete_phase2_audit.py',source,'--json',out/'phase02.json','--csv',out/'phase02_resources.csv']
                if a.full:cmd.append('--scan-gap')
                run('S02_phase02',cmd,phase(2),env)
                if a.full:
                    for mode in ('probe','inject'):
                        run('S04_phase03_dry_'+mode,[py,phase(3)/'ibara_complete_bootstrap.py',source,'--mode',mode,'--dry-run','--report',out/('phase03_'+mode+'_dry.json')],phase(3),env)
            run('S05_phase04',[py,phase(4)/'ibara_complete_menu_map.py',source,'--out',out/'phase04_menu.json','--breakpoints',out/'phase04_breakpoints.txt'],phase(4),env)
            pairs=[(6,'audit_arrange_dispatch.py','test_audit.py'),(7,'audit_rank_scoring.py','test_audit_rank_scoring.py'),(8,'audit_pickups.py','test_audit_pickups.py'),(9,'audit_cancellation.py','test_audit_cancellation.py'),(10,'audit_rose_merging.py','test_audit_rose_merging.py')]
            for n,script,test in pairs:
                cmd=[py,phase(n)/script,binary,'--json',out/f'phase{n:02d}.json','--csv',out/f'phase{n:02d}_table.csv']
                if n==8:cmd+=['--medal-csv',out/'phase08_medals.csv']
                run(f'S{n+2:02d}_phase{n:02d}_audit',cmd,phase(n),env)
                if n in (6,10):tc=[py,'-m','unittest','-v',test]
                else:tc=[py,phase(n)/test,binary]
                run(f'S{n+2:02d}_phase{n:02d}_unit',tc,phase(n),env)
    (out/'SUMMARY.json').write_text(json.dumps({'note':'Offline static/synthetic only; PCSX2/real hardware NOT tested','source':str(a.source) if a.source else None,'results':records},indent=2)+'\n')
    bad=[r for r in records if r['status']=='FAIL']
    print('SUMMARY:',len(records)-len(bad),'pass/skip,',len(bad),'fail;',out)
    sys.exit(bool(bad))
if __name__=='__main__':main()
