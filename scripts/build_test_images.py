#!/usr/bin/env python3
"""Build ONE test ISO from the unmodified retail ISO; never overwrites source.
Modes: probe (standalone magenta homebrew ELF), inject (normal retail boot + dormant ELF),
asset (five-entry menu unchanged, dormant extra texture).
"""
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('iso',type=Path)
 p.add_argument('--mode',choices=['probe','inject','asset'],required=True)
 p.add_argument('--out',type=Path,default=Path('outputs'))
 p.add_argument('--dry-run',action='store_true')
 a=p.parse_args()
 src=a.iso.resolve();out=a.out.resolve()
 if not src.is_file():p.error('Retail source image not found')
 if a.dry_run and a.mode=='asset':p.error('asset-only requires output; for a preview use Phase4 --preview')
 out.mkdir(parents=True,exist_ok=True)
 if a.mode in ('probe','inject'):
  filename='Ibara Complete BOOT PROBE.iso' if a.mode=='probe' else 'Ibara Complete RETAIL BOOT.iso'
  cmd=[sys.executable,str(ROOT/'research/phase03/ibara_complete_bootstrap.py'),str(src),'--mode',a.mode,'--report',str(out/f'Phase3_{a.mode}_report.json')]
  cmd+=['--dry-run'] if a.dry_run else ['--output',str(out/filename)]
  cwd=ROOT/'research/phase03'
 else:
  cmd=[sys.executable,str(ROOT/'research/phase04/ibara_complete_button_prototype.py'),str(src),
   '--preview',str(out/'Phase4_Button_Prototype.png'),'--report',str(out/'Phase4_asset_report.json'),
   '--apply-to',str(out/'Ibara Complete ASSET ONLY.iso')]
  cwd=ROOT/'research/phase04'
 print('RUNNING',' '.join(cmd),flush=True)
 sys.exit(subprocess.call(cmd,cwd=cwd))
if __name__=='__main__':main()
