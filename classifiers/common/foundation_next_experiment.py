"""Frozen next-encoder experiment. Explicit private data/output paths; no uploads.
Plan, code/data/weights hashes are written before first backbone inference.
"""
import argparse,json,os,platform,subprocess,sys,time,importlib.metadata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def protected(root):
 from classifiers.common.foundation_next import digest
 result={}
 for directory in ['data','artifacts','scripts','infra/public-server-v4','infra/public-app-v7']:
  for p in (root/directory).rglob('*'):
   if p.is_file() and '__pycache__' not in p.parts:result[str(p.relative_to(root))]=digest(p)
 return result

def run(a):
 import numpy as np,torch
 from classifiers.common.foundation_next import SPECS,digest,canonical,adapt,extract,load_backbone
 from classifiers.common.head_selection import load_rows,evaluate,trials_for,fit_head,HEAD_GRID
 from classifiers.common.numeric_linear_head import export,load,decision
 started=time.perf_counter();torch.set_num_threads(4);torch.manual_seed(2026);torch.use_deterministic_algorithms(True)
 out=a.out.resolve();root=a.data_root.resolve();rows,review,folds=load_rows(root);all_rows=rows+review
 if a.reproduce:
  frozen=json.loads((out/'plan.json').read_text());guard=json.loads((out/'protected-hashes.json').read_text())
 else:
  out.mkdir(parents=True,exist_ok=False);guard=protected(root);save(out/'protected-hashes.json',guard)
 assert len(rows)==22 and sum(r['label']=='bad' for r in rows)==13 and len(review)==2
 assert [(int(sum(folds!=i)),int(sum(folds==i))) for i in range(3)]==[(13,9),(15,7),(16,6)]
 assert len({r['group'] for r in rows})==16 and len({r['group'] for r in rows if r['label']=='good'})==3
 blocked={};folders={};pins={}
 for name in a.methods:
  if name=='clip':folder=a.clip_weights
  else:
   status=json.loads((a.access_dir/(name+'-access.json')).read_text())
   if status['status']!='available':blocked[name]=status;continue
   folder=a.weights/name
  folders[name]=folder;pins[name]={f:dict(sha256=digest(folder/f),bytes=(folder/f).stat().st_size) for f in ['config.json','preprocessor_config.json','README.md',SPECS[name]['checkpoint']]}
 if not folders:
  save(out/'unrun.json',blocked);raise RuntimeError('No accessible requested representations; no scores')
 images=[];records=[];t=time.perf_counter()
 for r in all_rows:
  source=(root/'data/extracted'/r['file']).read_bytes()
  import hashlib
  assert hashlib.sha256(source).hexdigest()==r['sha256']
  image,record=canonical(source);images.append(image);records.append(dict(record,index=r['index']))
 canonical_seconds=time.perf_counter()-t
 old=root/'artifacts/custom-v2'
 oldrecords=json.loads((old/'preprocessing_records.json').read_text())
 assert [(r['index'],r['canonical_sha256']) for r in records]==[(r['index'],r['canonical_sha256']) for r in oldrecords]
 codefiles=['classifiers/common/foundation_next.py','classifiers/common/foundation_next_experiment.py','classifiers/common/numeric_linear_head.py','classifiers/common/head_selection.py','classifiers/common/preprocessing.py']
 plan=dict(schema='foundation-next-v1',requested=a.methods,available=list(folders),blocked=blocked,models={n:SPECS[n] for n in a.methods},pins=pins,source_rows=rows,review_rows=review,canonical=records,folds=folds.tolist(),head_grid=HEAD_GRID,
  versions={n:importlib.metadata.version(n) for n in ['torch','torchvision','transformers','huggingface-hub','tokenizers','safetensors','numpy','scikit-learn','scipy','Pillow','joblib']},python=sys.version,code={p:digest(ROOT/p) for p in codefiles},
  preprocessing='EXIF RGB max1024 JPEG95 subsampling0; canonical decode; full-frame aspect-preserving 224 square mean-color pad, pinned processor resample and mean/std; no enhancements/crops',
  selection='Fixed representations and joint nested architecture selection. Original grouped outer3; train-only StandardScaler; balanced logistic/LinearSVC x C .01/.1/1; grouped inner2, balanced accuracy, first-grid ties. Final separate all22 inner2 selection per representation and joint. No review rows fit or tune.',
  pooling_rationale='DINOv3 official CLS provides fixed global image descriptor; SigLIP2 official image-feature attention pooling; CLIP projected normalized embedding matches baseline. No pooling/resolution search.',
  seed=2026,batch_size=4,torch_threads=4,hardware=dict(platform=platform.platform(),cpu=platform.processor(),logical_cpu=os.cpu_count(),machine=platform.machine(),lscpu=subprocess.check_output(['lscpu'],text=True)),
  qualifications=['Provisional repeated archive, only three good similarity groups, not verified tyre identities.','Fixed-backbone ranking is retrospectively optimistic; joint nested selection is separate.','No validated visibility/OOD gate: all operational outputs require review; no safety certification.','Local API fee zero; compute/electricity/hosting economic cost unknown. No cloud tariff inferred.'])
 if a.reproduce:
  assert frozen==plan,'Frozen identity changed'
 else:
  save(out/'plan.json',plan);save(out/'plan-freeze-receipt.json',dict(utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),plan_sha256=digest(out/'plan.json'),stage='before first backbone execution'))
 print('PLAN_FROZEN',digest(out/'plan.json'),flush=True)
 features={};timings={};parity={}
 for name,folder in folders.items():
  t=time.perf_counter();model=load_backbone(name,folder);cold=time.perf_counter()-t
  t=time.perf_counter();tensors=[adapt(im,folder) for im in images];adapt_seconds=time.perf_counter()-t
  t=time.perf_counter();x=extract(model,tensors,name);first=time.perf_counter()-t
  key=name+'_224';features[key]=x
  if name=='clip':
   oldpins=json.loads((old/'weight_progress.json').read_text())['clip']['files']
   assert all(pins[name][f]['sha256']==oldpins[f]['sha256'] for f in pins[name]),'CLIP checkpoint mismatch'
   cached=np.load(old/'clip_224_features.npz')['features'];maxdiff=float(np.max(np.abs(x-cached)))
   np.testing.assert_allclose(x,cached,rtol=1e-4,atol=1e-5)
   parity['clip_features']=dict(exact=bool(np.array_equal(x,cached)),max_absolute_difference=maxdiff,allclose_rtol=1e-4,allclose_atol=1e-5,checkpoint_and_canonical_hashes_exact=True)
  if a.reproduce:np.testing.assert_array_equal(x,np.load(out/(key+'-features.npz'))['features'])
  else:np.savez_compressed(out/(key+'-features.npz'),features=x)
  extract(model,tensors[:1],name);warm=[]
  for _ in range(3):
   t=time.perf_counter();extract(model,tensors,name);warm.append(time.perf_counter()-t)
  timings[key]=dict(first_local_load_seconds=cold,model_adaptation_seconds=adapt_seconds,first_batch24_seconds=first,warm_batch24_size4_repeat_seconds=warm,warm_batch_amortized_median_seconds_per_photo=float(np.median(warm)/24),feature_dimension=x.shape[1])
  del model
  print('FEATURE_READY',key,x.shape,first,flush=True)
 results,predictions,selections,rpred,search_seconds=evaluate(features,rows,review,folds,list(features))
 if 'clip_224' in features:
  oldpred=json.loads((old/'predictions.json').read_text())['clip_224'];now=predictions['clip_224']
  assert [(r['index'],r['prediction']) for r in now]==[(r['index'],r['prediction']) for r in oldpred],'CLIP baseline prediction mismatch: comparison halted'
  assert results['clip_224']['correct']==18 and results['clip_224']['shared_fold0']['correct']==7,'CLIP baseline metric mismatch'
  parity['clip_predictions']=dict(exact=True,correct=18,n=22,common_correct=7,common_n=9)
 if a.reproduce:
  assert predictions==json.loads((out/'predictions.json').read_text())
  assert selections==json.loads((out/'selections.json').read_text())
  assert results==json.loads((out/'summary.json').read_text())['methods']
 else:
  for n,v in [('predictions.json',predictions),('selections.json',selections),('review-diagnostics.json',rpred)]:save(out/n,v)
 y=np.array([r['label']=='good' for r in rows],dtype=int);final={};smoke={}
 t=time.perf_counter()
 for method in list(features)+['nested_architecture']:
  candidates=list(features) if method=='nested_architecture' else [method]
  trials=trials_for(features,y,rows,np.arange(len(rows)),candidates,inner_n=2);chosen=max(trials,key=lambda t:t['inner_balanced_accuracy'])
  model=fit_head(features[chosen['candidate']][:22],y,chosen);headpath=out/(method+'-head.json')
  if a.reproduce:
   v=load(headpath);np.testing.assert_allclose(decision(v,features[chosen['candidate']]),model.decision_function(features[chosen['candidate']]),rtol=1e-12,atol=1e-12)
  else:v=export(model,headpath)
  np.testing.assert_allclose(decision(v,features[chosen['candidate']]),model.decision_function(features[chosen['candidate']]),rtol=1e-12,atol=1e-12)
  final[method]=dict(selected=chosen,trials=trials,head_sha256=digest(headpath),fit_population=22,not_oof_accuracy=True)
 final_seconds=time.perf_counter()-t
 for name,folder in folders.items():
  key=name+'_224';headpath=out/(key+'-head.json');t=time.perf_counter();backbone=load_backbone(name,folder);reload_seconds=time.perf_counter()-t
  t=time.perf_counter();v=load(headpath);headload=time.perf_counter()-t
  sm=[]
  for i in [0,1,22,23]:
   t=time.perf_counter();im,rec=canonical((root/'data/extracted'/all_rows[i]['file']).read_bytes());tensor=adapt(im,folder);prep=time.perf_counter()-t
   t=time.perf_counter();x=extract(backbone,[tensor],name);ft=time.perf_counter()-t
   np.testing.assert_allclose(x[0],features[key][i],rtol=1e-4,atol=1e-5)
   t=time.perf_counter();margin=float(decision(v,x)[0]);ht=time.perf_counter()-t
   cachedmargin=float(decision(v,features[key][i:i+1])[0]);assert (margin>0)==(cachedmargin>0)
   sm.append(dict(index=all_rows[i]['index'],truth=all_rows[i]['label'],forced_binary_prediction='good' if margin>0 else 'bad',decision_margin=margin,canonical_and_adaptation_seconds=prep,warm_single_feature_seconds=ft,head_seconds=ht,operational_prediction='review'))
  head_times=[]
  for _ in range(10):
   t=time.perf_counter();decision(v,features[key]);head_times.append(time.perf_counter()-t)
  timings[key].update(cached_backbone_reload_seconds=reload_seconds,numeric_head_reload_seconds=headload,head24_repeat10_seconds=head_times)
  smoke[key]=dict(engineering_only_not_oof=True,real_originals_and_reloaded_checkpoint_and_numeric_head=True,feature_and_prediction_parity=True,rows=sm)
  del backbone
 assert all(digest(root/p)==h for p,h in guard.items()),'Protected original bytes changed'
 summary=dict(schema='foundation-next-v1',status='completed_available_candidates',requested_models=a.methods,executed_models=list(folders),unrun=blocked,binary_photos=22,bad_photos=13,good_photos=9,review_photos=2,groups=16,good_groups=3,methods=results,parity=parity,plan_sha256=digest(out/'plan.json'),final_fits=final,timing=dict(canonical24_seconds=canonical_seconds,per_candidate=timings,nested_search_seconds=search_seconds,final_all22_search_and_fit_seconds=final_seconds,total_experiment_seconds=time.perf_counter()-started,acquisition_excluded=True),protected_originals_unchanged=True,protected_file_count=len(guard),forced_binary_coverage=1.,operational_automation_coverage=0.,api_fee_per_image=0.,local_economic_cost=None,qualifications=plan['qualifications'])
 if a.reproduce:save(out/'reproduction.json',dict(exact_features_and_predictions_and_trials_and_metrics=True,heads_refit_and_numeric_reload_parity=True,protected_originals_unchanged=True,seconds=time.perf_counter()-started))
 else:
  save(out/'summary.json',summary);save(out/'final-fits.json',final);save(out/'artifact-smoke.json',smoke);save(out/'parity.json',parity)
 print(json.dumps(dict(methods={k:dict(correct=v['correct'],n=v['n'],balanced_accuracy=v['balanced_accuracy'],bad_to_good=v['bad_to_good'],common_correct=v['shared_fold0']['correct']) for k,v in results.items()},reproduce=a.reproduce,seconds=time.perf_counter()-started)),flush=True)

def main(default_methods=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--weights',type=Path,required=True);p.add_argument('--clip-weights',type=Path);p.add_argument('--access-dir',type=Path,required=True);p.add_argument('--methods',nargs='+',choices=['clip','dinov3','siglip2'],default=default_methods or ['clip','dinov3','siglip2']);p.add_argument('--reproduce',action='store_true');a=p.parse_args()
 if 'clip' in a.methods and a.clip_weights is None:p.error('--clip-weights required for CLIP parity')
 run(a)
if __name__=='__main__':main()
