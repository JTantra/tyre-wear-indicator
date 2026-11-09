"""Importable genuine Azure vision methods, never cached predictions.
Use importlib.util.spec_from_file_location for this hyphenated directory.
Default auth is Azure CLI for local pilot; credential=ManagedIdentityCredential()
for server-side Azure serving. Public access is NOT automatic cloud-send consent.
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))
import base64,hashlib,json,os,sys,time,subprocess
from pathlib import Path
from decimal import Decimal
import requests
R=Path(os.environ.get('TYRE_PROJECT_ROOT',str(Path(__file__).resolve().parents[next(i for i,p in enumerate(Path(__file__).resolve().parents) if (p/'export-manifest.json').is_file())])));O=Path(__file__).resolve().parent
sys.path[:0]=[str(R/'classifiers/common'),str(R/'classifiers/common')]
from preprocessing import canonical_image
from project_ledger import ProjectLedger,durable_append,retry_deadline
from cloud_policy_v2 import guard
P=json.loads((O/'plan.json').read_text());AUD='https://cognitiveservices.azure.com/';TENANT=os.environ.get('AZURE_TENANT_ID','')
IDS={'gpt41-vision-base':'gpt41-vision-base','gpt41-vision-ft-pilot':'gpt41-vision-ft-pilot'}

def _read(name):
 path=O/name
 return json.loads(path.read_text()) if path.exists() else {}

def methods():
 job=_read('job-readback.json');items=[]
 for mid,deployment in IDS.items():
  rb=_read('deployment-'+deployment+'.json');isft=mid.endswith('ft-pilot');pre=_read('preflight-'+mid+'.json')
  matching=rb.get('properties',{}).get('model',{})
  completed=(not isft or (job.get('status')=='succeeded' and job.get('fine_tuned_model')==matching.get('name')))
  deployed=rb.get('properties',{}).get('provisioningState')=='Succeeded' and completed
  state=('preflight_error' if deployed and pre.get('status')=='error' else 'complete' if deployed and pre.get('status')=='complete' else ('deployed_unverified' if deployed else job.get('status','not_submitted') if isft else 'unavailable'))
  items.append({'id':mid,'provider':'Azure OpenAI','model':matching.get('name',P['training_model_id'] if not isft else None),'version':matching.get('version'),'deployment':deployment if rb else None,'deployment_id':rb.get('id'),'sku':rb.get('sku'),'status':state,'available':state=='complete','fine_tuned':isft,'training_job_id':job.get('id') if isft else None,'api':'/openai/v1/chat/completions','output_schema':P['output_schema'],'confidence':None,'operational_policy':'Human review mandatory; condition-only unvalidated diagnostic, no roadworthiness','endpoint':_read('account-readback.json').get('properties',{}).get('endpoint'),'auth_scope':P['scope'],'token_scope':AUD+'.default','retail_rates_per1M_usd':{'input':2.2,'cached_input':0.55,'output':8.8},'hosting_per_hour_usd':1.7 if isft else None,'price_source':'https://azure.microsoft.com/en-us/pricing/details/azure-openai/','price_qualification':'2026-11-07 firstparty indexed USD rates; dynamic extraction shows placeholders; estimate not invoice.'})
 return items

def payload(data,deployment):
 return {'model':deployment,'messages':[{'role':'system','content':P['prompt']},{'role':'user','content':[{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(data).decode(),'detail':'high'}}]}],'response_format':{'type':'json_schema','json_schema':{'name':'tyre_visual_condition','strict':True,'schema':P['output_schema']}},'max_completion_tokens':64,'temperature':0,'seed':105,'store':False}

def parse(reply):
 usage=reply.get('usage');assert isinstance(usage,dict),'missing_usage'
 for k in ['prompt_tokens','completion_tokens','total_tokens']:assert type(usage.get(k)) is int and usage[k]>=0,'missing_usage'
 assert usage['total_tokens']==usage['prompt_tokens']+usage['completion_tokens'],'invalid_usage'
 choice=reply['choices'][0];assert choice['finish_reason']=='stop' and not choice['message'].get('refusal'),'refused_or_truncated'
 obj=json.loads(choice['message']['content']);assert set(obj)=={'visual_condition'} and obj['visual_condition'] in ['good','bad','review'],'schema_uncertainty'
 return obj['visual_condition'],usage

def retail_cost(usage):
 prompt=usage['prompt_tokens'];cached=(usage.get('prompt_tokens_details') or {}).get('cached_tokens')
 if cached is None:return {'lower_usd':float((Decimal(prompt)*Decimal('.55')+Decimal(usage['completion_tokens'])*Decimal('8.8'))/1000000),'upper_usd':float((Decimal(prompt)*Decimal('2.2')+Decimal(usage['completion_tokens'])*Decimal('8.8'))/1000000),'exact_retail_estimate_usd':None,'reason':'Missing cached-token breakdown; bounds, not zero cache assumption'}
 assert type(cached) is int and 0<=cached<=prompt
 cost=float((Decimal(prompt-cached)*Decimal('2.2')+Decimal(cached)*Decimal('.55')+Decimal(usage['completion_tokens'])*Decimal('8.8'))/1000000)
 return {'lower_usd':cost,'upper_usd':cost,'exact_retail_estimate_usd':cost,'reason':'Actual returned usage × dated firstparty retail rates; not invoice; excludes training/idle hosting'}

def _token(credential=None):
 if credential is None:raw=json.loads(subprocess.check_output(['az','account','get-access-token','--resource',AUD,'-o','json'],text=True))['accessToken']
 else:raw=credential.get_token(AUD+'.default').token
 meta=json.loads(base64.urlsafe_b64decode(raw.split('.')[1]+'==='));assert meta['aud']==AUD and meta['tid']==TENANT and meta['exp']>time.time()+180,'Token binding failed'
 return raw,{k:meta.get(k) for k in ['aud','oid','tid','exp']}

def infer(method_id,imagebytes,*,cloud_send_consent=False,credential=None,_pilot_phase=None,_index=None):
 """One physical paid call, no automatic retry. Validate before reserving.
 Pilot permits own unverified deployment preflight, never an incomplete FT job.
 """
 if not cloud_send_consent:return {'status':'error','needs_review':True,'error':'Explicit cloud-send consent required','usage':None,'cost_usd':None}
 if method_id not in IDS:return {'status':'error','needs_review':True,'error':'Unknown method','usage':None,'cost_usd':None}
 method=next(m for m in methods() if m['id']==method_id)
 if not method['available'] and not (_pilot_phase=='preflight' and method['status']=='deployed_unverified'):
  return {'status':'error','needs_review':True,'error':'Method not genuinely completed and preflight-verified: '+method['status'],'usage':None,'cost_usd':None}
 if type(imagebytes) is not bytes or len(imagebytes)>10_000_000:return {'status':'error','needs_review':True,'error':'Invalid image bytes/size','usage':None,'cost_usd':None}
 data,pr=canonical_image(imagebytes);body=payload(data,IDS[method_id]);raw,meta=_token(credential);ep=method['endpoint'].rstrip('/');key=P['scope']+'/'+IDS[method_id]
 rates=_read('deployment-'+IDS[method_id]+'.json')['properties']['rateLimits'];rpm=next(r['count'] for r in rates if r['key']=='request');tpm=next(r['count'] for r in rates if r['key']=='token')
 with ProjectLedger(R) as ledger:
  own=[r for r in ledger.rows if r['event']=='attempt' and r.get('experiment')=='gpt41-vision-sft-pilot']
  if _pilot_phase and len(own)>=P['pilot_max_inference_attempts']:raise ValueError('One pilot20call budget exhausted')
  event={'experiment':'gpt41-vision-sft-pilot' if _pilot_phase else 'gpt41-vision-live','method':method_id,'source_sha256':pr['source_sha256'],'canonical_sha256':pr['canonical_sha256'],'payload_sha256':hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest(),'phase':_pilot_phase,'index':_index,**guard(ledger,1)}
  aid=ledger.reserve(event,key,rpm=rpm,tpm=tpm)
  if aid is None:raise ValueError('Lifetime200 exhausted')
  start=time.time()
  try:r=requests.post(ep+'/openai/v1/chat/completions',json=body,headers={'Authorization':'Bearer '+raw},timeout=180)
  except requests.RequestException as exc:
   result={'status':'error','needs_review':True,'error':type(exc).__name__,'attempt_id':aid,'usage':None,'cost_usd':None,'halt_reason':'transport_unknown'};ledger.response(aid,status=None,halt_reason='transport_unknown',actual_tokens=None);durable_append(O/'inference-results.jsonl',dict(result,**event));return result
  elapsed=time.time()-start;headers={k:v for k,v in r.headers.items() if k.lower() in ['apim-request-id','x-request-id','x-ms-request-id']}
  try:reply=r.json()
  except ValueError:reply={'body':r.text[:5000]}
  result={'method_id':method_id,'phase':_pilot_phase,'index':_index,'attempt_id':aid,'http_status':r.status_code,'request_ids':headers,'response':reply,'token_metadata':meta,'latency_seconds':elapsed,'latency_scope':'HTTP request only, excludes decode/token acquisition/ledger pacing','source_sha256':pr['source_sha256'],'canonical_sha256':pr['canonical_sha256'],'needs_review':True,'tread_visibility':'unassessed','roadworthiness':None,'confidence':None,'model':reply.get('model'),'usage':reply.get('usage'),'cost_usd':None}
  halt=None;tokens=None
  if not r.ok:halt='authentication_or_authorization' if r.status_code in (401,403) else 'provider_error';result.update(status='error',error=reply.get('error',reply))
  else:
   try:condition,usage=parse(reply);cost=retail_cost(usage);tokens=usage['total_tokens'];result.update(status='complete',visual_condition=condition,usage=usage,cost_usd=cost,automatically_approved=False)
   except (AssertionError,KeyError,ValueError,IndexError,TypeError) as exc:halt='usage_or_schema_unknown';result.update(status='error',error=str(exc))
  ledger.response(aid,status=r.status_code,actual_tokens=tokens,halt_reason=halt,retry_not_before=retry_deadline(r.headers,time.time()))
  if halt:result['halt_reason']=halt
  durable_append(O/'inference-results.jsonl',result)
  return result


def evaluate(method_id,phase):
 manifest=json.loads((R/'artifacts/manifest.json').read_text());by={r['index']:r for r in manifest}
 assert phase in ['preflight','evaluation'];indices=[3] if phase=='preflight' else P['evaluation_indices']
 if phase=='evaluation':assert _read('preflight-'+method_id+'.json').get('status')=='complete'
 prior=[json.loads(x) for x in (O/'inference-results.jsonl').read_text().splitlines()] if (O/'inference-results.jsonl').exists() else []
 for i in indices:
  if any(r.get('method_id')==method_id and r.get('phase')==phase and r.get('index')==i for r in prior):raise ValueError('Already attempted cell; never retry silently')
  row=by[i];src=(R/'data/extracted'/row['file']).read_bytes();assert hashlib.sha256(src).hexdigest()==row['sha256'];result=infer(method_id,src,cloud_send_consent=True,_pilot_phase=phase,_index=i)
  if phase=='preflight':(O/('preflight-'+method_id+'.json')).write_text(json.dumps(result,indent=2)+'\n')
  print(json.dumps({k:result.get(k) for k in ['method_id','index','status','visual_condition','usage','error']}),flush=True)
  if result['status']!='complete':raise RuntimeError('Halt after real failed request')

if __name__=='__main__':evaluate(sys.argv[1],sys.argv[2])
