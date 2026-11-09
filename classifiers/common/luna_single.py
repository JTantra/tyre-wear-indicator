"""One approved genuine new-image request, ledger-first; never historical rows."""
import hashlib,json,os,time
from pathlib import Path
from classifiers.common.approval import require
from classifiers.common.preprocessing import canonical_image
from classifiers.common.paths import ROOT,method_module

def predict(method,image,config,execute,approval):
 if not execute:raise PermissionError('Fresh-image Luna inference requires --execute and fresh approval; --benchmark is offline')
 row=require(approval,'luna-inference')
 if config is None:raise ValueError('Explicit private config required; example placeholders cannot execute')
 cfg=json.loads(Path(config).read_text());v=cfg['variants'][0]
 api='responses' if method=='luna-responses' else 'decisions'
 if len(cfg['variants'])!=1 or v['api']!=api or 'YOUR-' in v['endpoint'] or v['deployment'].startswith('EXACT-'):raise ValueError('One genuinely configured method required')
 from classifiers.common.provider_runner import endpoint_url,sanitise
 from classifiers.common.cost_accounting import validate_rate
 from classifiers.common.project_ledger import ProjectLedger
 from classifiers.common.cloud_policy_v2 import guard
 import requests
 url=endpoint_url(v['endpoint'],api);validate_rate(v.get('rate_card'),v)
 raw=Path(image).read_bytes()
 if not 0<len(raw)<=5*1024*1024:raise ValueError('Image maximum5 MB')
 data,_=canonical_image(raw)
 mod=method_module(method,'rubric' if api=='responses' else 'refinement_v3')
 body=mod.vision_payload(data,v['deployment']) if api=='responses' else mod.decisions_payload(data,v['deployment'])
 if api=='responses':body['max_output_tokens']=v.get('max_output_tokens',1500)
 auth=os.environ.get(v.get('bearer_token_env',''))
 if not auth:raise PermissionError('Configured bearer-token environment is absent; credentials never committed')
 with ProjectLedger(ROOT) as ledger:
  event=dict(experiment='explicit-new-image-luna-v2',source_sha256=hashlib.sha256(raw).hexdigest(),**guard(ledger,1))
  aid=ledger.reserve(event,v['deployment'],rpm=row['rpm'],tpm=row['tpm'])
  if aid is None:raise RuntimeError('Fresh bounded inference budget exhausted')
  try:
   response=requests.post(url,json=body,headers={'Authorization':'Bearer '+auth},timeout=90)
   response.raise_for_status();reply=response.json()
   usage=reply.get('usage',{});tokens=usage.get('total_tokens')
   if type(tokens) is not int or tokens<0:raise ValueError('Usage unknown; operator reconciliation required')
   parsed=mod.parse(reply) if api=='responses' else mod.parse_v2('decisions',reply,True)
   ledger.response(aid,status=response.status_code,actual_tokens=tokens)
  except Exception:
   ledger.response(aid,status=None,halt_reason='transport_or_usage_unknown',actual_tokens=None);raise RuntimeError('Provider failed; no retry. Inspect private ledger')
 return dict(status='complete',prediction='review',diagnostic_prediction=parsed['prediction'],needs_review=True,evaluation='Genuine approved fresh-image API request; NOT benchmark replay')
