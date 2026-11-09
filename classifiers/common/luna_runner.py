"""Genuine v2 payload/parser with original benchmark engine; dry by default."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))
import argparse,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[next(i for i,p in enumerate(Path(__file__).resolve().parents) if (p/'export-manifest.json').is_file())];sys.path[:0]=[str(ROOT/'classifiers/common'),str(ROOT/'classifiers/common')]
import importlib
v2=importlib.import_module('classifiers.luna-decisions.refinement_v3')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
 if a.execute and os.environ.get('TYRE_OWNER_AUTHORIZED_CLOUD')!='1':raise SystemExit('Fresh owner cloud-send/spending approval required')
 if a.execute and not (ROOT/'infra/experiment-request-ledger.json').is_file():raise SystemExit('Fresh operator-owned ledger/limit receipt required; no production budget reuse/reset')
 cfg=json.loads(a.config.read_text());v2.install()
 result=v2.rb.run(cfg,a.out,execute=a.execute,selection='all',max_calls=50,max_tokens=30000000,retries=0,timeout=90,project_max_calls=200)
 print(json.dumps({k:result.get(k) for k in ['complete','attempted','success','error','missing','halt']}))
