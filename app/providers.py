"""Optional parent-owned remote module; no cloud calls during discovery."""
import importlib.util,json,subprocess,sys,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LOCAL={
 'local-resnet18-final':('ResNet18 / saved final head','scripts/predict_classifier.py','artifacts/classifier/baseline_head.joblib'),
 'local-mobilenet-final':('MobileNet V3 / saved final head','scripts/predict_custom.py','artifacts/custom-improvements/head.joblib'),
 'local-clip-final':('CLIP 224 / saved final head','app/local_worker.py','artifacts/custom-v2/head.joblib')}
class Registry:
 def __init__(self):
  self.remote=None;self.remote_error=None
  path=ROOT/'infra/live_providers.py'
  if path.is_file():
   try:
    spec=importlib.util.spec_from_file_location('tyre_live_providers',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    self.remote=module
   except Exception as exc:self.remote_error=type(exc).__name__
 def methods(self):
  methods=[{'id':key,'label':v[0],'family':'custom-local','status':'available' if (ROOT/v[2]).is_file() else 'unavailable','reason':'Saved full-data model; diagnostic only, NOT historical CV replay. Mandatory review.','paid':False} for key,v in LOCAL.items()]
  if self.remote:
   for entry in self.remote.methods():
    row=dict(entry)
    if row.get('id') in LOCAL:continue
    row['paid']=True;methods.append(row)
  else:
   for key,label,family in [('remote-luna','Luna Responses / Decisions','luna'),('remote-claude','Claude Sonnet','claude'),('remote-aml','Azure ML asynchronous batch','azure-ml')]:
    methods.append({'id':key,'label':label,'family':family,'status':'unavailable','reason':'Parent live adapter not installed / restart required.' if not self.remote_error else 'Live adapter failed to load: '+self.remote_error,'paid':True})
  return methods
 def provenance(self,method_id):
  if method_id in LOCAL:
   _,script,head=LOCAL[method_id]
   return {'provider':'local','method_id':method_id,'model_version_sha256':hashlib.sha256((ROOT/head).read_bytes()).hexdigest(),
    'model_artifact':head,'adapter_sha256':hashlib.sha256((ROOT/script).read_bytes()).hexdigest(),
    'api':'saved-head-subprocess','rubric_version':'mandatory-review-local/1',
    'qualification':'Full-data engineering head; not historical grouped-CV replay'}
  entry=next(m for m in self.methods() if m['id']==method_id)
  return {'provider':'parent-adapter','method_id':method_id,'configured_method':entry,
   'adapter_sha256':hashlib.sha256((ROOT/'infra/live_providers.py').read_bytes()).hexdigest(),
   'model_version':'See exact model/API/version in returned prediction provenance; unavailable values are unknown',
   'rubric_version':'Parent adapter-bound rubric; adapter source hash retained'}
 def infer(self,method_id,path,context):
  t0=time.perf_counter()
  if method_id in LOCAL:
   proc=subprocess.run([sys.executable,str(ROOT/LOCAL[method_id][1]),str(path)],cwd=ROOT,capture_output=True,text=True,timeout=180)
   if proc.returncode:raise RuntimeError('Saved model inference failed; inspect local model installation.')
   value=json.loads(proc.stdout)
   binary=value.get('diagnostic_binary_prediction',value.get('binary_prediction'))
   return dict(value,status='complete',prediction='review',needs_review=True,diagnostic_binary_prediction=binary,tread_visibility='unassessed',tread_depth_mm=None,roadworthiness_certified=False,latency_seconds=time.perf_counter()-t0,latency_scope='Actual local single request: subprocess startup, saved model load, preprocessing and inference; excludes upload and queue.',api_fee_usd=0,local_compute_cost_usd=None,evaluation='Saved full-data engineering inference, not out-of-fold benchmark replay.')
  if not context.get('paid_consent'):raise PermissionError('Explicit paid consent required')
  if not self.remote:raise RuntimeError('Remote adapter unavailable')
  return self.remote.infer(method_id,path.read_bytes())
 def poll(self,provider_job_id):
  if not self.remote:raise RuntimeError('Remote adapter unavailable')
  return self.remote.poll(provider_job_id)
