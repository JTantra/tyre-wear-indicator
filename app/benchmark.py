"""Read-only dashboard projection of real benchmark and derived routing evidence."""
import json,os,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
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
 path=ROOT/'infra/live_providers.py'
 try:
  spec=importlib.util.spec_from_file_location('dashboard_budget_view',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.budget_snapshot()
 except (OSError,ValueError,AttributeError,ImportError):return {'lifetime_cap':200,'used':None,'remaining':None,'read_only':True,'snapshot_not_authorization':True,'live_snapshot':False,'additional_approved_usd':None,'monetary_limit_removed':True,'exact_invoice_usd':None,'ledger_blocked':True,'note':'Current ledger unavailable. Providers fail closed; display never authorizes spending.'}

def per_images():
 rows=read(os.environ.get('DASHBOARD_PER_IMAGE_PATH',str(ROOT/'infra/cloud-refinement-v3/per-image.json')),[])
 if isinstance(rows,dict):rows=rows.get('rows',rows.get('per_image',[]))
 allowed=['variant','index','sha256','truth','population','status','prediction','reason','latency_seconds_success','flagged_label']
 result=[{k:r.get(k) for k in allowed} for r in rows]
 for folder,prefix in [('classifier','custom-resnet18-'),('custom-v2','custom-v2-'),('custom-improvements','custom-refined-')]:
  for name,values in read(ROOT/'artifacts'/folder/'predictions.json',{}).items():
   for r in values:result.append({'variant':prefix+name,'index':r['index'],'sha256':r.get('sha256'),'truth':r.get('truth'),'population':'grouped_oof_diagnostic','status':'historical','prediction':r.get('prediction'),'reason':'Historical grouped OOF diagnostic; not saved-model replay','fold':r.get('fold'),'flagged_label':r['index']==11})
 O=ROOT/'infra/cloud-refinement-v3'
 for r in read(O/'decisions-offline-probabilities.json',[]):
  for suffix,key in [('original-gated','original_gated'),('raw-argmax-three-choice','argmax'),('returned-three-choice','returned_choice'),('forced-binary-diagnostic','forced_binary')]:
   result.append({**{k:r.get(k) for k in ('index','sha256','truth','population','flagged_label')},'variant':r['variant']+'-'+suffix,'status':'historical-derived','prediction':r[key],'reason':'Offline routing of existing API reply; not another model call or independent photograph'})
 for r in read(O/'decisions-oof-routing.json',[]):
  result.append({**{k:r.get(k) for k in ('index','sha256','truth','population','flagged_label')},'variant':r['variant']+'-grouped-oof-routing','status':'historical-derived','prediction':r['prediction'],'reason':'Threshold selected on other groups only; development diagnostic, not a deployed classifier'})
 for r in read(O/'decisions-v2-offline-evidence.json',[]):
  for suffix,key in [('legacy-gates-diagnostic','legacy_gated_diagnostic'),('forced-binary-diagnostic','forced_binary')]:
   result.append({**{k:r.get(k) for k in ('index','sha256','truth','population','flagged_label')},'variant':r['variant']+'-'+suffix,'status':'historical-derived','prediction':r[key],'reason':'Offline routing of existing API reply; not another model call or independent photograph'})
 for r in read(O/'decisions-v2-oof-routing.json',[]):
  result.append({**{k:r.get(k) for k in ('index','sha256','truth','population','flagged_label')},'variant':r['variant']+'-grouped-oof-routing','status':'historical-derived','prediction':r['prediction'],'reason':'Threshold selected on other groups only; development diagnostic, not a deployed classifier'})
 return result+read(ROOT/'infra/final-pilot-v4/dashboard-extension.json',{}).get('rows',[])
