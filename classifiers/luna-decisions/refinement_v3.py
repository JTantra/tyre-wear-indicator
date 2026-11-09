"""Development-only rubric and train-other-fold routing; never modifies v1."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))
import json,sys,math,hashlib,itertools,csv,statistics
from pathlib import Path
R=Path(__file__).resolve().parents[next(i for i,p in enumerate(Path(__file__).resolve().parents) if (p/'export-manifest.json').is_file())];sys.path.insert(0,str(R/'classifiers/common'))
from classifiers.common import provider_runner as rb
from classifiers.common.benchmark_contract import clean_image_data_url
from importlib import import_module
vision_payload=import_module('classifiers.luna-responses.rubric').vision_payload
O=R/'infra/cloud-refinement-v3'
from classifiers.common.luna_rubric import RUBRIC
GRID={'good':[0,.4,.5,.6,.65,.7,.8,.9,1], 'visibility':[0,.25,.5,.65,.8], 'damage':[.5,.8,1]}
CALIBRATION_PLAN={'grid':GRID,'objective':'minimize train bad->good (zero whenever feasible), then maximize full-denominator balanced accuracy; tie-break coverage, then lower good/visibility and higher damage threshold','preserve_model_review':True,'bad_evidence_bypasses_good_visibility_gate':True,'train_only':'existing outer_fold != heldout; group disjoint; unique binary rows only','confidence':'probabilities are NOT calibrated likelihoods; no confidence calibration claim','evaluation':'all archive explored; development-only OOF routing, not prospective validation; only three good groups'}
OLD_PARSE=rb.parse_response

def decisions_payload(data,deployment,multi=True):
 return {'model':deployment,'input':[{'role':'user','content':[{'type':'input_text','text':'Inspect visible wear and damage, then judge visual condition using the question rubric.'},{'type':'input_image','image_url':clean_image_data_url(data)}]}], 'questions':[
 {'type':'predicate','name':'tread_visible','instructions':'Is enough tread face clear to see groove/raised relief or wear? Partial/oblique views suffice if clear. Sidewall/rim alone and fully obscuring mud do not. No exact depth measurement is required.'},
 {'type':'predicate','name':'clear_damage','instructions':'Is cracking, exposed cords, torn rubber or severe visible tyre damage clearly present? Do not confuse tread grooves, mud or shadows with damage.'},
 {'type':'choice','name':'condition','instructions':RUBRIC,'choices':[{'value':'good','description':'Enough clear tread relief/grooves, no clear flattened wear or damage; visual screen only.'},{'value':'bad','description':'Clear flattened/bald/shallow-looking tread wear or visible damage, even if view is partial.'},{'value':'review','description':'Sidewall only without damage, obscured detail or genuinely conflicting visual evidence.'}]}]}


def extract_decisions(body):
 answers=body.get('answers');assert isinstance(answers,list)
 by={a['name']:a for a in answers};assert len(by)==len(answers)
 c=by['condition'];assert c['type']=='choice' and c['choice'] in ('good','bad','review')
 ps={p['value']:p['probability'] for p in c['probabilities']};assert set(ps)=={'good','bad','review'}
 assert all(type(p) in (int,float) and math.isfinite(p) and 0<=p<=1 for p in ps.values()) and abs(sum(ps.values())-1)<1e-4
 row={'returned_choice':c['choice'],'argmax':max(('good','bad','review'),key=lambda k:ps[k]),'forced_binary':'good' if ps['good']>ps['bad'] else 'bad','prob_good':ps['good'],'prob_bad':ps['bad'],'prob_review':ps['review'],'binary_prob_good_diagnostic':ps['good']/(ps['good']+ps['bad']) if ps['good']+ps['bad'] else None,'reported_confidence_uncalibrated':c.get('confidence')}
 for k in ('tread_visible','clear_damage'):
  a=by.get(k);p=a.get('probability') if a else None
  if a:assert a['type']=='predicate' and type(p) in (int,float) and math.isfinite(p) and 0<=p<=1
  row[k]=p
 return row

def route(row,g,v,d):
 pred=row['returned_choice']
 if pred!='good':return pred
 if row['prob_good']<g:return 'review'
 if row['tread_visible'] is not None and row['tread_visible']<v:return 'review'
 if row['clear_damage'] is not None and row['clear_damage']>=d:return 'review'
 return 'good'

def metrics(rows,key='prediction'):
 binary=[r for r in rows if r['population']=='unique_binary_scoring'];accepted=[r for r in binary if r[key]!='review'];bad=[r for r in binary if r['truth']=='bad'];good=[r for r in binary if r['truth']=='good'];reviews=[r for r in rows if r['truth']=='review']
 confusion={t:{p:sum(r['truth']==t and r[key]==p for r in binary) for p in ('good','bad','review')} for t in ('good','bad')}
 correct=sum(r['truth']==r[key] for r in binary);unsafe=sum(r[key]=='good' for r in bad)
 return {'binary_n':len(binary),'correct_binary':correct,'accuracy_binary':correct/len(binary) if binary else None,'binary_coverage':len(accepted)/len(binary) if binary else None,'accepted_binary_n':len(accepted),'accepted_accuracy':correct/len(accepted) if accepted else None,'unsafe_good_of_bad':unsafe,'bad_n':len(bad),'unsafe_rate_all_bad':unsafe/len(bad) if bad else None,'balanced_accuracy':(sum(r[key]=='good' for r in good)/len(good)+sum(r[key]=='bad' for r in bad)/len(bad))/2 if good and bad else None,'review_rejected':sum(r[key]=='review' for r in reviews),'source_review_n':len(reviews),'confusion':confusion}

def fit_policy(train):
 candidates=[]
 for g,v,d in itertools.product(GRID['good'],GRID['visibility'],GRID['damage']):
  rs=[dict(r,prediction=route(r,g,v,d)) for r in train];m=metrics(rs)
  rank=(-m['unsafe_good_of_bad'],m['balanced_accuracy'],m['binary_coverage'],-g,-v,d)
  candidates.append((rank,(g,v,d),m))
 _,params,m=max(candidates,key=lambda x:x[0]);return params,m

def grouped_oof(rows):
 binary=[r for r in rows if r['population']=='unique_binary_scoring'];result=[];audit=[]
 for fold in sorted({r['outer_fold'] for r in binary}):
  train=[r for r in binary if r['outer_fold']!=fold];test=[r for r in binary if r['outer_fold']==fold]
  tg={r['group'] for r in train};hg={r['group'] for r in test};assert not tg&hg
  params,m=fit_policy(train)
  audit.append({'heldout_fold':fold,'train_indices':[r['index'] for r in train],'heldout_indices':[r['index'] for r in test],'train_groups':sorted(tg),'heldout_groups':sorted(hg),'parameters':dict(zip(('good','visibility','damage'),params)),'train_metrics':m})
  result.extend(dict(r,prediction=route(r,*params),routing_fold=fold) for r in test)
 assert len(result)==22
 return result,audit

def parse_v2(api,body,multi):
 if api=='decisions':
  try:
   row=extract_decisions(body)
   return {'prediction':row['returned_choice'],'reason':'v2_direct_three_choice_no_confidence_gate'}
  except (AssertionError,KeyError,TypeError,ValueError):return {'prediction':'review','reason':'v2_invalid_decisions_schema'}
 try:
  assert body['status']=='completed'
  text=''.join(c['text'] for i in body['output'] if i.get('type')=='message' for c in i['content'] if c.get('type')=='output_text')
  r=json.loads(text);pred=r['visual_condition']
  assert pred in ('good','bad','review') and r['visibility'] in ('adequate','inadequate','uncertain') and r['groove_relief'] in ('distinct_raised_relief','flattened_or_shallow','obscured_or_uncertain') and r['visible_damage'] in ('yes','no','uncertain') and type(r['needs_review']) is bool and isinstance(r['evidence'],str) and r['tread_depth_mm'] is None and r['twi_verified'] is None
  clear_bad=pred=='bad' and (r['groove_relief']=='flattened_or_shallow' or r['visible_damage']=='yes')
  if clear_bad:return {'prediction':'bad','reason':'v2_clear_bad_evidence'}
  if r['needs_review'] or r['visibility']!='adequate' or r['groove_relief']=='obscured_or_uncertain' or (pred=='good' and r['visible_damage']!='no'):return {'prediction':'review','reason':'v2_inadequate_or_conflicting'}
  return {'prediction':pred,'reason':'v2_model_choice'}
 except (AssertionError,KeyError,TypeError,ValueError):return {'prediction':'review','reason':'v2_invalid_responses_schema'}

def install():
 from importlib import import_module
 vision_payload=import_module('classifiers.luna-responses.rubric').vision_payload
 rb.decisions_payload=decisions_payload;rb.vision_payload=vision_payload;rb.parse_response=parse_v2

def write_rows(name,rows):
 O.mkdir(exist_ok=True)
 (O/(name+'.json')).write_text(json.dumps(rows,indent=2)+'\n')
 fields=list(dict.fromkeys(k for r in rows for k in r))
 with (O/(name+'.csv')).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows)

def offline():
 O.mkdir(exist_ok=True);(O/'calibration-plan.json').write_text(json.dumps(CALIBRATION_PLAN,indent=2)+'\n')
 per=json.loads((R/'infra/cloud-completion-v2/per-image.json').read_text());split={r['index']:r for r in json.loads((R/'artifacts/classifier/splits.json').read_text())['rows']}
 events=json.loads((R/'infra/cloud-completion-v2/raw-sanitized-events.json').read_text());replies={r['case_key']:r for r in events if r['event']=='attempt_response' and r['status']==200}
 allrows=[];allmetrics=[];all_oof=[];audits=[]
 for variant in ('decisions-single-v1','decisions-multi-v1'):
  rows=[]
  for r in per:
   if r['variant']!=variant:continue
   key=rb.canonical_hash([variant,r['sha256'],r['index']]);raw=replies[key]['raw_response'];a=extract_decisions(raw)
   s=split.get(r['index'],{})
   row=dict(r,**a,original_gated=r['prediction'],group=s.get('group'),outer_fold=s.get('outer_fold'),flagged_label=r['index']==11)
   assert OLD_PARSE('decisions',raw,'multi' in variant)['prediction']==r['prediction'];rows.append(row)
  assert len(rows)==25
  for policy,key in [('original-gated','original_gated'),('raw-argmax-three-choice','argmax'),('returned-three-choice','returned_choice'),('forced-binary-diagnostic','forced_binary')]:
   allmetrics.append(dict(method=variant+'-'+policy,family='decisions',evaluation='existing actual saved outputs; offline development diagnostic' if policy!='original-gated' else 'preserved original frozen routing',**metrics(rows,key)))
  oof,audit=grouped_oof(rows);all_oof.extend(oof);audits.append({'variant':variant,'folds':audit})
  allmetrics.append(dict(method=variant+'-grouped-oof-routing',family='decisions',evaluation='train-other-fold threshold selection; tiny development-only OOF; model reviews preserved',**metrics(oof)))
  allrows.extend(rows)
 write_rows('decisions-offline-probabilities',allrows);write_rows('decisions-offline-methods',allmetrics);write_rows('decisions-oof-routing',all_oof)
 (O/'calibration-fold-audit.json').write_text(json.dumps(audits,indent=2)+'\n')
 print(json.dumps(allmetrics,indent=2))
if __name__=='__main__':offline()
