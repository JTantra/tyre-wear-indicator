"""Fail-closed offline publication check; diagnostics never print values."""
import ast, hashlib, json, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
METHODS=['resnet18','mobilenet','clip','luna-responses','luna-decisions','gpt41-finetuned','azure-automl']
SECTIONS=['Status','Model and checkpoint provenance','Inputs and transforms','Training, validation and test','Metrics and coverage','Prompt or questions','Cost and runtime','Reproduce and expected artifacts','Limitations and rights']
RULES={
 'uuid_identity_or_private_filename':r'(?i)\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b',
 'image_base64_payload':r'data:image/[^,\s]+;base64,[A-Za-z0-9+/=]{40,}',
 'jwt_or_capability':r'\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}',
 'private_key_material':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
 'known_token_format':r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{24,}|AKIA[A-Z0-9]{16})\b',
 'literal_secret_assignment':r"""(?i)(?:password|api[_-]?key|client[_-]?secret|accountkey|signing[_-]?key|access[_-]?token|cookie|verifier)\s*[=:]\s*["'][A-Za-z0-9+/=_-]{16,}["']""",
 'private_deployment_identifier':r'(?:aoai-'+'tyre|rg-'+'tyre-wear-indicator|mlw-'+'tyre-batch|/subscriptions/[0-9a-f])',
 'sas_or_capability_url':r'(?i)(?:[?&](?:sig|access_token|token)=[A-Za-z0-9%+/=_-]{16,})',
 'production_readback_payload':r'"(?:principalId|tenantId|roleDefinitionId|request_ids|token_metadata|original_reason|raw_response|accessToken|password_verifier)"\s*:',
}
ALLOWED_BINARY={'docs/assets/twi-six-methods-costs.png'}
def digest(data):return hashlib.sha256(data).hexdigest()
def content_rules(rel,data):
 hits=[]
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
 rows=json.loads((root/'results/per-image.json').read_text());summ=json.loads((root/'results/method-summary.json').read_text());part=json.loads((root/'results/partitions.json').read_text());ft=json.loads((root/'results/gpt-training.json').read_text())
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
 cloud=json.loads((root/'results/cloud-rounds-per-case.json').read_text());assert len(cloud)==150
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
  if parts[0]=='app' and len(parts)>1 and parts[1].startswith('runtime'):continue
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
 for mid in METHODS:
  rel='methods/'+mid+'/README.md'
  try:s=(root/rel).read_text()
  except OSError:err(rel,'missing_method_readme');continue
  for h in SECTIONS:
   if '\n## '+h+'\n' not in s:err(rel,'missing_method_section_'+h.replace(' ','_'))
 try:counts=numeric_checks(root)
 except Exception:err('results','numeric_contract');counts={}
 return errors,counts
if __name__=='__main__':
 errors,counts=check()
 for e in errors:print(e['path']+' :: '+e['rule'])
 if not errors:print(json.dumps(dict(status='PASS',**counts),sort_keys=True))
 raise SystemExit(1 if errors else 0)
