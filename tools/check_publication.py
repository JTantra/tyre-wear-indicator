"""Fail-closed offline publication check; diagnostics never print values."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))
import ast, hashlib, json, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[next(i for i,p in enumerate(Path(__file__).resolve().parents) if (p/'export-manifest.json').is_file())]
METHODS=['resnet18','mobilenet','clip','luna-responses','luna-decisions','gpt41-finetuned','azure-automl']
APPEND_METHODS=['dinov3','siglip2']
SECTIONS=['Status','Model and checkpoint provenance','Inputs and transforms','Training, validation and test','Metrics and coverage','Prompt or questions','Cost and runtime','Reproduce and expected artifacts','Limitations and rights']
RULES={
 'uuid_identity_or_private_filename':r'(?i)\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b',
 'image_base64_payload':r'data:image/[^,\s]+;base64,[A-Za-z0-9+/=]{40,}',
 'jwt_or_capability':r'\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}',
 'private_key_material':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
 'known_token_format':r'\b(?:hf_[A-Za-z0-9]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{24,}|AKIA[A-Z0-9]{16})\b',
 'literal_secret_assignment':r"""(?i)(?:password|api[_-]?key|client[_-]?secret|accountkey|signing[_-]?key|access[_-]?token|cookie|verifier)\s*[=:]\s*["'][A-Za-z0-9+/=_-]{16,}["']""",
 'private_deployment_identifier':r'(?:aoai-'+'tyre|rg-'+'tyre-wear-indicator|mlw-'+'tyre-batch|/subscriptions/[0-9a-f])',
 'sas_or_capability_url':r'(?i)(?:[?&](?:sig|access_token|token)=[A-Za-z0-9%+/=_-]{16,})',
 'production_readback_payload':r'"(?:principalId|tenantId|roleDefinitionId|request_ids|token_metadata|original_reason|raw_response|accessToken|password_verifier)"\s*:',
}
ALLOWED_BINARY={'docs/assets/twi-six-methods-costs.png'}
def digest(data):return hashlib.sha256(data).hexdigest()
OWNED_NUMERIC_HEADS={'classifiers/resnet18/weights/head.json': {'sha256': '887a7f40d8b1fa0a204681ce9a5033acb1616496213f80fac3ce0ed4679748ec', 'bytes': 38046}, 'classifiers/mobilenet/weights/head.json': {'sha256': '9714bc2539909ed8cc78b1c3719d6c21d56bd834076a940166463b869bfa3b89', 'bytes': 73684}, 'classifiers/clip/weights/head.json': {'sha256': 'b753a861108e77028f06dedd69e6f800a9e0215c6f3c8b02cec2917717b330a5', 'bytes': 40341}}
NEXT_NUMERIC_HEADS={'classifiers/siglip2/weights/head.json': {'sha256': 'f9d8e99da2e1649876f56f7b4b277a3841d921337640e6bba987021ae4ea1aea', 'bytes': 59045}}
def content_rules(rel,data):
 if rel in NEXT_NUMERIC_HEADS:
  spec=NEXT_NUMERIC_HEADS[rel];hits=[]
  if len(data)!=spec['bytes'] or digest(data)!=spec['sha256']:hits.append('unapproved_owned_head_content')
  try:
   from classifiers.common.numeric_linear_head import validate
   validate(json.loads(data))
  except Exception:hits.append('invalid_numeric_head_schema')
  return hits
 hits=[]
 if rel in OWNED_NUMERIC_HEADS:
  spec=OWNED_NUMERIC_HEADS[rel]
  if len(data)!=spec['bytes'] or digest(data)!=spec['sha256']:hits.append('unapproved_owned_head_content')
  try:
   from classifiers.common.numeric_head import validate
   validate(json.loads(data))
  except Exception:hits.append('invalid_numeric_head_schema')
  return hits
 if Path(rel).suffix.lower() in {'.jpg','.jpeg','.webp','.joblib','.pkl','.pickle','.npz','.npy','.pth','.pt','.bin','.safetensors','.db','.jsonl','.zip'}:hits.append('private_or_large_artifact_path')
 if '/weights/' in rel and not (rel.endswith(('README.md','pretrained.json','fetch.py')) or '/upstream/' in rel):hits.append('unapproved_weights_path')
 if len(data)>5*1024*1024:hits.append('oversized_file')
 if rel in ALLOWED_BINARY:
  if digest(data) != 'c83b73e196b0ccb555ef98ef47bac1c7737bd45103606a77667c0427e05c4c59':hits.append('unapproved_infographic_content')
  if not data.startswith(bytes([137,80,78,71,13,10,26,10])):hits.append('invalid_infographic_png')
  return hits
 try:text=data.decode('utf-8')
 except UnicodeDecodeError:return hits+['unapproved_binary']
 if '\x00' in text:hits.append('binary_nul')
 for rule,pattern in RULES.items():
  if re.search(pattern,text):hits.append(rule)
 if rel.endswith('.svg') and re.search(r'<image\b|data:image',text):hits.append('embedded_image_svg')
 return hits

def metric(rows):
 if len({r['image_index'] for r in rows})!=len(rows):raise ValueError('duplicate')
 accepted=[r for r in rows if r['prediction'] in ['bad','good']];bad=[r for r in rows if r['truth']=='bad']
 return dict(n=len(rows),correct=sum(r['truth']==r['prediction'] for r in rows),accepted=len(accepted),reviews=sum(r['prediction']=='review' for r in rows),errors=sum(r['prediction'] not in ['bad','good','review'] for r in rows),bad_n=len(bad),bad_false_good=sum(r['prediction']=='good' for r in bad),coverage=len(accepted)/len(rows),accepted_accuracy=sum(r['truth']==r['prediction'] for r in accepted)/len(accepted) if accepted else None,confusion={a:{b:sum(r['truth']==a and r['prediction']==b for r in rows) for b in ['bad','good','review','error']} for a in ['bad','good']})
def numeric_checks(root):
 rows=json.loads((root/'classifiers/common/results/per-image.json').read_text());summ=json.loads((root/'classifiers/common/results/method-summary.json').read_text());part=json.loads((root/'classifiers/common/results/partitions.json').read_text());ft=json.loads((root/'classifiers/common/results/gpt-training.json').read_text())
 assert len(rows)==128 and len(summ)==7
 expected=[(12,4,2,1),(14,4,3,1),(18,7,2,2),(19,8,1,0),(11,3,6,3),(None,9,None,0),(None,8,None,0)]
 for m,exp in zip(summ,expected):
  rr=[r for r in rows if r['method']==m['method']];same=[r for r in rr if r['fold']==0]
  assert m['shared9']==metric(same) and len(same)==9
  assert m['all22']==(metric(rr) if len(rr)==22 else None)
  assert ((m['all22'] or {}).get('correct'),m['shared9']['correct'],(m['all22'] or {}).get('bad_false_good'),m['shared9']['bad_false_good'])==exp
  assert m['operational_automation_coverage']==0
 assert len(part['rows'])==22 and len({r['image_index'] for r in part['rows']})==22
 assert sum(r['label']=='bad' for r in part['rows'])==13 and sum(r['label']=='good' for r in part['rows'])==9
 for f,(train,test) in enumerate(part['fold_train_test']):
  tr=[r for r in part['rows'] if r['outer_fold']!=f];te=[r for r in part['rows'] if r['outer_fold']==f]
  assert len(tr)==train and len(te)==test and not {r['group'] for r in tr}&{r['group'] for r in te}
 assert ft['actual_training_examples']==13 and ft['actual_training_counts']=={'good':5,'bad':6,'review':2}
 assert len(ft['actual_training_indices'])==13 and not set(ft['actual_training_indices'])&set(ft['evaluation_indices'])
 assert ft['actual_hyperparameters']==dict(n_epochs=1,batch_size=1,learning_rate_multiplier=2)
 cloud=json.loads((root/'classifiers/common/results/cloud-rounds-per-case.json').read_text());assert len(cloud)==150
 assert len({(r['variant'],r['index']) for r in cloud})==150
 for key in ['vision-rubric-v2','decisions-rubric-v2']:
  rr=[r for r in cloud if r['variant']==key];assert len(rr)==25 and sum(r['population']=='unique_binary_scoring' for r in rr)==22
 cost=json.loads((root/'docs/assets/verified-azure-costs.json').read_text())
 from decimal import Decimal as D
 for m in cost['methods'][:3]:assert D(m['rough_active_compute_per_image_usd'])==D(m['observed_seconds'])*D('.000060')
 for m in cost['methods'][3:5]:
  u=m['usage_totals'];assert m['submitted_images_cost_denominator']==25
  for outkey,inp,out in [('retail_token_per_submitted_image_usd_low','.11','.55'),('retail_token_per_submitted_image_usd_high','.22','.825')]:assert D(m[outkey])==(D(u['input_tokens'])*D(inp)+D(u['output_tokens'])*D(out))/D(1000000)/D(25)
 g=cost['methods'][5];assert D(g['training_one_off_usd'])==D(g['trained_tokens'])/D(1000)*D('.0275')
 assert D(g['api_per_image_usd'])==(D(9864)*D('2.2')+D(54)*D('8.8'))/D(1000000)/D(9)
 return dict(prediction_rows=len(rows),methods=len(summ),documented_methods=len(METHODS),cloud_cases=len(cloud),binary_photos=22)

def next_numeric_checks(root):
 """Independent anonymous arithmetic; frozen seven-method totals remain immutable."""
 folder=root/'docs/foundation-next-2026-11-10'
 summary=json.loads((folder/'comparison.json').read_text());plan=json.loads((folder/'plan.json').read_text());rows=json.loads((folder/'per-image.json').read_text())
 assert summary['executed_models']==['clip','siglip2'] and summary['unrun']['dinov3']['metrics'] is None
 assert summary['unrun']['dinov3']['http_status']==401
 assert plan['head_grid']==[dict(head=h,C=c) for h in ['logistic','linear_svm'] for c in [.01,.1,1.]]
 assert plan['fold_train_test']==[[13,9],[15,7],[16,6]] and plan['freeze_receipt']['stage']=='before first backbone execution'
 assert set(rows)==set(summary['methods'])=={'clip_224','siglip2_224','nested_architecture'}
 for key,rs in rows.items():
  assert len(rs)==22 and {r['case'] for r in rs}==set(range(1,23))
  assert all(set(r)=={'case','truth','prediction','decision_margin'} for r in rs)
  assert sum(r['truth']=='bad' for r in rs)==13 and sum(r['truth']=='good' for r in rs)==9
  result=summary['methods'][key]
  c=[[sum(r['truth']==a and r['prediction']==b for r in rs) for b in ['bad','good','review']] for a in ['bad','good','review']]
  assert result['confusion']==c and result['correct']==sum(r['truth']==r['prediction'] for r in rs)
  assert result['bad_to_good']==c[0][1] and result['n']==22 and result['coverage']==1.
  assert result['accuracy_all']==result['correct']/22 and result['balanced_accuracy']==(c[0][0]/13+c[1][1]/9)/2
  common=result['shared_fold0'];cc=common['confusion']
  assert common['n']==9 and sum(cc[0])==5 and sum(cc[1])==4
  assert common['correct']==cc[0][0]+cc[1][1] and common['balanced_accuracy']==(cc[0][0]/5+cc[1][1]/4)/2
  assert common['bad_to_good']==cc[0][1]
  review=summary['review_diagnostics'][key]
  assert review['photo_count']==2 and len(review['fold_head_diagnostics'])==3 and all(len(f)==2 for f in review['fold_head_diagnostics'])
 assert summary['parity']['clip_features']['exact'] and summary['parity']['clip_features']['max_absolute_difference']==0.
 assert summary['reproduction']['exact_features_and_predictions_and_trials_and_metrics']
 sig=json.loads((root/'classifiers/siglip2/results/summary.json').read_text())
 assert sig['all22']==summary['methods']['siglip2_224'] and sig['common9']==sig['all22']['shared_fold0']
 assert json.loads((root/'classifiers/siglip2/results/per-image.json').read_text())==rows['siglip2_224']
 assert digest((root/'classifiers/siglip2/weights/head.json').read_bytes())==sig['head_sha256']
 din=json.loads((root/'classifiers/dinov3/results/summary.json').read_text())
 assert din['status']=='access_blocked' and din['all22'] is None and din['common9'] is None and din['head_sha256'] is None
 assert json.loads((root/'classifiers/dinov3/results/per-image.json').read_text())==[]
 return dict(appended_documented_methods=2,appended_executed_encoders=2,appended_oof_rows=sum(len(v) for v in rows.values()))

def check(root=ROOT):
 errors=[]
 def err(rel,rule):errors.append(dict(path=rel,rule=rule))
 try:manifest=json.loads((root/'export-manifest.json').read_text());expected={r['export_path']:r for r in manifest['files']}
 except Exception:return [dict(path='export-manifest.json',rule='missing_or_invalid_manifest')],{}
 if len(expected)!=len(manifest['files']):err('export-manifest.json','duplicate_manifest_path')
 for rule in content_rules('export-manifest.json',(root/'export-manifest.json').read_bytes()):err('export-manifest.json',rule)
 for p in sorted(root.rglob('*')):
  if not p.is_file():continue
  rel=str(p.relative_to(root));parts=p.relative_to(root).parts
  if parts[0] in ['.git','.cache','.venv'] or '__pycache__' in parts:continue
  if parts[0]=='dashboard' and 'runtime' in parts:continue
  if rel=='export-manifest.json':continue
  if p.is_symlink():err(rel,'symlink_forbidden');continue
  if rel not in expected:err(rel,'not_allowlisted');continue
  data=p.read_bytes()
  if digest(data)!=expected[rel]['export_sha256']:err(rel,'integrity_mismatch')
  for rule in content_rules(rel,data):err(rel,rule)
  if p.suffix=='.py':
   try:ast.parse(data.decode())
   except Exception:err(rel,'python_syntax')
  if p.suffix=='.md':
   text=data.decode()
   # Inline/file links only; pinned upstream vendor cards may have upstream-relative targets.
   for target in re.findall(r'\]\(([^\s)]+)(?:\s+"[^"]*")?\)',text):
    if target.startswith(('http:','https:','mailto:','#')):continue
    t=target.split('#')[0]
    resolved=(p.parent/t).resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.exists():err(rel,'broken_relative_markdown_link')
 for rel in expected:
  if not (root/rel).is_file():err(rel,'missing_allowlisted_file')
 for mid in METHODS+APPEND_METHODS:
  rel='classifiers/'+mid+'/README.md'
  try:s=(root/rel).read_text()
  except OSError:err(rel,'missing_method_readme');continue
  for h in SECTIONS:
   if '\n## '+h+'\n' not in s:err(rel,'missing_method_section_'+h.replace(' ','_'))
 try:
  counts=numeric_checks(root)
  counts.update(next_numeric_checks(root))
 except Exception:err('results','numeric_contract');counts={}
 return errors,counts
def staged_check():
 """Read exact index blobs, not working-tree promises or a Git status approximation."""
 import subprocess,tempfile
 with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as directory:
  target=Path(directory)
  files=subprocess.check_output(['git','ls-files','--stage','-z'],cwd=ROOT).split(bytes([0]))
  for line in files:
   if not line:continue
   meta,rel=line.split(bytes([9]),1);mode,oid,stage=meta.decode().split();rel=rel.decode()
   if stage!='0' or mode!='100644':return [dict(path=rel,rule='nonregular_or_unmerged_index')],{}
   dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True)
   dest.write_bytes(subprocess.check_output(['git','cat-file','blob',oid],cwd=ROOT))
  return check(target)
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--staged',action='store_true',help='Audit exact prospective index blobs including all owned head bytes');a=p.parse_args()
 errors,counts=staged_check() if a.staged else check()
 for e in errors:print(e['path']+' :: '+e['rule'])
 if not errors:print(json.dumps(dict(status='PASS',scope='exact-git-index' if a.staged else 'allowlisted-working-tree',**counts),sort_keys=True))
 raise SystemExit(1 if errors else 0)
