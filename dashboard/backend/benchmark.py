"""Read-only dashboard projection of real benchmark and derived routing evidence."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))
import json,os,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[next(i for i,p in enumerate(Path(__file__).resolve().parents) if (p/'export-manifest.json').is_file())]
def read(path,default=None):
 try:return json.loads(Path(path).read_text())
 except (OSError,ValueError):return default

def summary():
 path=Path(os.environ.get('DASHBOARD_BENCHMARK_PATH',str(ROOT/'FINAL_BENCHMARK.json')));data=read(path,{})
 nested=data.get('summary',data);methods=nested.get('methods',[])
 if isinstance(methods,dict):methods=[dict(v,method=k) for k,v in methods.items()]
 extra=read(ROOT/'infra/final-pilot-v4/dashboard-extension.json',{})
 known={m['method'] for m in methods};methods=list(methods)+[m for m in extra.get('methods',[]) if m['method'] not in known]
 limitations=data.get('limitations',nested.get('limitations',[]))
 if not isinstance(limitations,list):limitations=[str(limitations)] if limitations else []
 limitations=limitations+extra.get('limitations',[])
 return {'source':path.name,'methods':methods,'method_count':len(methods),'limitations':limitations,'warning':'Development archive, not an untouched held-out or prospective test. GPT-4.1 rows use9 excluded photos; original methods use22. Diagnostic good is not safety clearance.','population':{'unique_binary':22,'bad':13,'good':9,'review_only':2,'duplicate_excluded_index':14,'flagged_label_index':11},'additional_population':{'gpt41_excluded_binary':9,'bad':5,'good':4}}

def budget():
 # No lock acquisition or mutation: readers validate a snapshot, and each
 # provider separately obtains the exclusive lease before a paid request.
 path=ROOT/'dashboard/backend/private_live_providers.py'
 try:
  spec=importlib.util.spec_from_file_location('dashboard_budget_view',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.budget_snapshot()
 except (OSError,ValueError,AttributeError,ImportError):return {'lifetime_cap':200,'used':None,'remaining':None,'read_only':True,'snapshot_not_authorization':True,'live_snapshot':False,'additional_approved_usd':None,'monetary_limit_removed':True,'exact_invoice_usd':None,'ledger_blocked':True,'note':'Current ledger unavailable. Providers fail closed; display never authorizes spending.'}

def per_images():
 rows=read(ROOT/'classifiers/common/results/per-image.json',[])
 return [dict(variant=r['method'],index=r['image_index'],truth=r['truth'],prediction=r['prediction'],fold=r['fold'],population='frozen-development-archive',status='historical',reason='Archived benchmark evidence, NOT fresh image inference') for r in rows]
