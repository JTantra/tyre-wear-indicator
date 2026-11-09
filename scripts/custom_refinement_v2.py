#!/usr/bin/env python3
"""Frozen foundation features; public pinned weights, CPU, nested grouped heads.
No remote code or label-conditioned views. Writes only custom-v2 artifacts.
"""
from __future__ import annotations
import argparse, hashlib, importlib.metadata, io, json, platform, subprocess, time
from pathlib import Path
import joblib
import numpy as np
from PIL import Image, ImageOps
import torch
from torchvision.transforms import functional as TF
from transformers import Dinov2Config, Dinov2Model, CLIPVisionConfig, CLIPVisionModelWithProjection
from safetensors.torch import load_file
from custom_improvements import load_rows, evaluate, trials_for, fit_head, HEAD_GRID
from preprocessing import canonical_image
ROOT=Path(__file__).resolve().parents[1]
SEED=2026
MODELS={
 'dinov2':{'repo':'facebook/dinov2-small','revision':'ed25f3a31f01632728cabb09d1542f84ab7b0056','file':'model.safetensors','license':'Apache-2.0 model card; upstream code Apache-2.0','license_url':'https://huggingface.co/facebook/dinov2-small/blob/ed25f3a31f01632728cabb09d1542f84ab7b0056/README.md'},
 'clip':{'repo':'openai/clip-vit-base-patch32','revision':'3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268','file':'pytorch_model.bin','license':'OpenAI CLIP upstream code MIT; HF mirror card does not specify a separate weight license. Commercial clearance not established.','license_url':'https://github.com/openai/CLIP/blob/main/LICENSE'}}
REPRESENTATIONS=[('dinov2',224),('dinov2',336),('clip',224),('clip',384)]
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def download(url,path):
 if path.exists(): return {'cached':True,'seconds':0.}
 started=time.perf_counter();temp=path.with_suffix(path.suffix+'.part');errors=[]
 # Only public GET requests; no user images leave this process.
 for suffix in ['', '?download=true']:
  proc=subprocess.run(['curl','--fail','--location','--max-time','180','--connect-timeout','20','--silent','--show-error',url+suffix,'--output',str(temp)],capture_output=True,text=True)
  if proc.returncode==0:
   temp.replace(path);return {'cached':False,'seconds':time.perf_counter()-started,'route':suffix or 'direct','prior_errors':errors}
  errors.append(proc.stderr[-2000:]);temp.unlink(missing_ok=True)
 raise RuntimeError('Public download failed: '+repr(errors))
def prepare_weights(out,name):
 spec=MODELS[name];folder=out/'weights'/name;folder.mkdir(parents=True,exist_ok=True);records={}
 for filename in ['config.json','preprocessor_config.json','README.md',spec['file']]:
  url='https://huggingface.co/'+spec['repo']+'/resolve/'+spec['revision']+'/'+filename
  path=folder/filename;records[filename]=dict(download(url,path),sha256=digest(path),url=url,bytes=path.stat().st_size)
 return records
def backbone(out,name):
 folder=out/'weights'/name;config=json.loads((folder/'config.json').read_text())
 if name=='dinov2':
  model=Dinov2Model(Dinov2Config(**config));model.load_state_dict(load_file(str(folder/'model.safetensors')),strict=True)
 else:
  model=CLIPVisionModelWithProjection(CLIPVisionConfig(**config['vision_config']))
  state=torch.load(folder/'pytorch_model.bin',map_location='cpu',weights_only=True)
  state={k:v for k,v in state.items() if k.startswith('vision_model.') or k.startswith('visual_projection.')}
  # Legacy HF checkpoint persists deterministic position_ids; current code does not.
  ids=state.pop('vision_model.embeddings.position_ids',None)
  if ids is not None:assert torch.equal(ids,torch.arange(ids.shape[1]).unsqueeze(0))
  model.load_state_dict(state,strict=True)
 model.eval();model.requires_grad_(False);return model

def tensors_for(image,name,size):
 folder=ROOT/'artifacts/custom-v2/weights'/name
 # Model normalization metadata is pinned alongside weights. No center crop.
 config=json.loads((folder/'preprocessor_config.json').read_text())
 mean=config['image_mean'];std=config['image_std']
 color=tuple(round(v*255) for v in mean)
 im=ImageOps.pad(image,(size,size),method=Image.Resampling.BICUBIC,color=color)
 return TF.normalize(TF.to_tensor(im),mean,std)
def extract(model,tensors,name):
 blocks=[]
 with torch.inference_mode():
  for i in range(0,len(tensors),4):
   batch=torch.stack(tensors[i:i+4])
   if name=='dinov2':
    hidden=model(pixel_values=batch).last_hidden_state
    x=torch.cat([hidden[:,0],hidden[:,1:].mean(1)],dim=1)
   else:
    x=model(pixel_values=batch,interpolate_pos_encoding=True).image_embeds
    x=torch.nn.functional.normalize(x,dim=1)
   blocks.append(x.numpy())
 return np.concatenate(blocks)
def images_from_sources(rows):
 images=[];records=[]
 for row in rows:
  source=(ROOT/'data/extracted'/row['file']).read_bytes();assert hashlib.sha256(source).hexdigest()==row['sha256']
  data,record=canonical_image(source)
  with Image.open(io.BytesIO(data)) as im:images.append(im.convert('RGB'))
  records.append(dict(record,index=row['index']))
 return images,records

def evaluate_all(features,rows,review,folds):
 results,predictions,selections,review_predictions,seconds=evaluate(features,rows,review,folds,list(features))
 for name in MODELS:
  subset=[k for k in features if k.startswith(name+'_')]
  r,p,s,rp,st=evaluate(features,rows,review,folds,subset)
  key=name+'_nested_resolution';results[key]=r['nested_architecture'];predictions[key]=p['nested_architecture'];selections[key]=s['nested_architecture'];review_predictions[key]=rp['nested_architecture'];seconds+=st
 return results,predictions,selections,review_predictions,seconds

def protection():
 protected={}
 # Common cloud code is deliberately NOT protected against concurrent edits.
 for directory in ['artifacts/classifier','artifacts/classifier_legacy_center','artifacts/custom-improvements']:
  for p in (ROOT/directory).rglob('*'):
   if p.is_file():protected[str(p.relative_to(ROOT))]=digest(p)
 for rel in ['artifacts/manifest.json','artifacts/label_review_checklist.csv','data/raw.sha256']:
  protected[rel]=digest(ROOT/rel)
 for r in json.loads((ROOT/'artifacts/manifest.json').read_text()):
  protected['data/extracted/'+r['file']]=r['sha256']
 return protected

def run(reproduce=False):
 start=time.perf_counter();torch.set_num_threads(4);torch.manual_seed(SEED);torch.use_deterministic_algorithms(True)
 out=ROOT/'artifacts/custom-v2';out.mkdir(parents=True,exist_ok=True)
 rows,review,folds=load_rows(ROOT);all_rows=rows+review
 protected=json.loads((out/'protected_hashes.json').read_text()) if reproduce else protection()
 if not reproduce:save(out/'protected_hashes.json',protected)
 t0=time.perf_counter();images,records=images_from_sources(all_rows);canonical_seconds=time.perf_counter()-t0
 identity={'seed':SEED,'models':MODELS,'representations':REPRESENTATIONS,'head_grid':HEAD_GRID,
 'source_sha256':[r['sha256'] for r in all_rows],'canonical_sha256':[r['canonical_sha256'] for r in records],
 'outer_folds':folds.tolist(),'script_sha256':digest(Path(__file__)),
 'dependencies_sha256':{p:digest(ROOT/'scripts'/p) for p in ['custom_improvements.py','local_classifier.py','preprocessing.py']},
 'versions':{p:importlib.metadata.version(p) for p in ['torch','torchvision','transformers','huggingface-hub','safetensors','numpy','scikit-learn','Pillow','joblib']},
 'normalization':'Pinned preprocessor image_mean/std. Full canonical RGB, mean-color BICUBIC letterbox; no enhancement/crop. CLIP positional embeddings bicubic-interpolated above native224; DINO native patch14 supports224/336. DINO CLS+mean patches; CLIP projected L2-normalized vision embedding.'}
 if reproduce:assert json.loads((out/'identity.json').read_text())==json.loads(json.dumps(identity))
 else:save(out/'identity.json',identity);save(out/'preprocessing_records.json',records)
 features={};provenance={};timings={}
 for name in MODELS:
  if not reproduce:
   provenance[name]=dict(MODELS[name],files=prepare_weights(out,name),code_license='Transformers Apache-2.0',code_license_url='https://github.com/huggingface/transformers/blob/v4.46.3/LICENSE')
   save(out/'weight_progress.json',provenance)
  t0=time.perf_counter();model=backbone(out,name);load_seconds=time.perf_counter()-t0
  for n,size in REPRESENTATIONS:
   if n!=name:continue
   key=name+'_'+str(size);cache=out/(key+'_features.npz')
   t0=time.perf_counter();tensors=[tensors_for(im,name,size) for im in images];adapt=time.perf_counter()-t0
   t0=time.perf_counter();features[key]=extract(model,tensors,name);ft=time.perf_counter()-t0
   if reproduce:np.testing.assert_array_equal(features[key],np.load(cache)['features'])
   else:np.savez_compressed(cache,features=features[key])
   timings[key]={'backbone_load_seconds':load_seconds,'adaptation_seconds':adapt,'warm_batch4_seconds':ft,'batch_amortized_seconds_per_photo':ft/len(images),'feature_dimension':features[key].shape[1]}
   print('FEATURE_READY',key,features[key].shape,ft,flush=True)
  del model
 results,predictions,selections,review_predictions,search_seconds=evaluate_all(features,rows,review,folds)
 assert all(digest(ROOT/p)==h for p,h in protected.items()),'Protected baseline/source changed'
 if reproduce:
  assert predictions==json.loads((out/'predictions.json').read_text())
  assert selections==json.loads((out/'selections.json').read_text())
  assert results==json.loads((out/'summary.json').read_text())['methods']
  y=np.array([r['label']=='good' for r in rows],dtype=int)
  repeated=trials_for(features,y,rows,np.arange(len(rows)),list(features),inner_n=3)
  assert repeated==json.loads((out/'deployment_search_trials.json').read_text())
  save(out/'reproduction.json',{'exact_features_from_originals_and_saved_weights':True,'exact_all_oof_predictions_margins_and_inner_trials':True,'exact_metrics':True,'exact_deployment_trials':True,'protected_hashes_unchanged':True,'seconds':time.perf_counter()-start})
  print('REPRODUCTION_OK',flush=True);return
 y=np.array([r['label']=='good' for r in rows],dtype=int);t0=time.perf_counter()
 trials=trials_for(features,y,rows,np.arange(len(rows)),list(features),inner_n=3)
 config=max(trials,key=lambda t:t['inner_balanced_accuracy']);final_search=time.perf_counter()-t0
 head=fit_head(features[config['candidate']][:len(rows)],y,config)
 joblib.dump(head,out/'head.joblib');save(out/'deployment_config.json',config);save(out/'deployment_search_trials.json',trials)
 t0=time.perf_counter();head=joblib.load(out/'head.joblib');head_load=time.perf_counter()-t0
 name,size=config['candidate'].split('_');size=int(size)
 t0=time.perf_counter();model=backbone(out,name);model_load=time.perf_counter()-t0
 smoke=[];single_timings=[]
 for i in [0,1,len(rows),len(rows)+1]:
  row=all_rows[i];t0=time.perf_counter();ims,_=images_from_sources([row]);tensors=[tensors_for(ims[0],name,size)];prep=time.perf_counter()-t0
  t0=time.perf_counter();x=extract(model,tensors,name);ft=time.perf_counter()-t0
  np.testing.assert_allclose(x[0],features[config['candidate']][i],rtol=1e-4,atol=1e-5)
  t0=time.perf_counter();p=int(head.predict(x)[0]);margin=float(head.decision_function(x)[0]);ht=time.perf_counter()-t0
  smoke.append({'index':row['index'],'source_truth':row['label'],'forced_binary_prediction':'good' if p else 'bad','margin':margin,'visibility':'unassessed','operational_prediction':'review'})
  single_timings.append({'canonical_and_adaptation_seconds':prep,'feature_seconds':ft,'head_seconds':ht})
 tensors=[tensors_for(im,name,size) for im in images];extract(model,tensors,name);batch=[];heads=[]
 for _ in range(3):
  t0=time.perf_counter();x=extract(model,tensors,name);batch.append(time.perf_counter()-t0)
  t0=time.perf_counter();head.predict(x);heads.append(time.perf_counter()-t0)
 timing={'cpu':platform.processor(),'torch_threads':4,'photos':len(images),'canonical_seconds':canonical_seconds,'per_candidate':timings,'nested_search_seconds':search_seconds,'final_grouped_search_seconds':final_search,'backbone_reload_seconds':model_load,'head_reload_seconds':head_load,'single_photo_smoke_timings':single_timings,'warm_batch4_repeat_seconds':batch,'batch_amortized_median_seconds_per_photo':float(np.median(batch)/len(images)),'warm_head_repeat_seconds':heads,'api_fee':0,'local_compute_cost':None,'cpu_tariff':None,'note':'Public downloads only; no image uploads, no paid APIs/GPU. Batch amortized time is not single-request latency. Local economic cost unknown.'}
 summary={'exploratory_only':True,'binary_photos':len(rows),'source_review_photos':len(review),'binary_groups':len({r['group'] for r in rows}),'groups_by_label':{label:len({r['group'] for r in rows if r['label']==label}) for label in ['bad','good']},'methods':results,'best_individual_by_balanced_accuracy':max(features,key=lambda k:results[k]['balanced_accuracy']),'deployment_config':config,'provenance':provenance,'timing':timing,'head_sha256':digest(out/'head.joblib'),'identity_sha256':digest(out/'identity.json'),'protected_hashes_unchanged':True,'forced_binary_coverage':1.,'operational_auto_coverage':0.,'operational_accepted_accuracy':None,'safety':'No validated visibility/OOD gate: expert review mandatory. Forced binary metrics are NOT review-only accuracy. No mm or safe/roadworthy inference.','limitations':['Only three provisional good similarity groups; not confirmed independent tyres.','Resolution/head/family selection only in outer-training grouped folds. Ranking fixed-resolution OOF winners is retrospective and optimistic.','DINO/CLIP pretraining overlap unknown; backgrounds/tread design may dominate; public license records are provenance, not deployment legal clearance.','Repeated development on this archive is not an untouched prospective test; do not claim 90%.'],'search':'Four predeclared full-frame representations x logistic/linearSVM x C .01,.1,1; balanced StandardScaler train-only; inner2 grouped BA; first-grid ties. Nested all-representation selector and family resolution selectors. Deployment full-data grouped3 search, not holdout.','total_seconds':time.perf_counter()-start}
 for filename,value in [('summary.json',summary),('predictions.json',predictions),('selections.json',selections),('review_diagnostics.json',review_predictions),('timing.json',timing),('artifact_smoke.json',{'evaluation':'Reloaded weights+trusted locally generated joblib, real original images, full-data engineering smoke NOT OOF','predictions':smoke})]:save(out/filename,value)
 assert all(digest(ROOT/p)==h for p,h in protected.items())
 print(json.dumps({'methods':{k:{f:r[f] for f in ['correct','n','accuracy_all','balanced_accuracy','macro_f1','bad_to_good']} for k,r in results.items()},'deployment':config,'seconds':summary['total_seconds']},indent=2),flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--reproduce',action='store_true');run(ap.parse_args().reproduce)
