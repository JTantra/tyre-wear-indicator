#!/usr/bin/env python3
"""Additive frozen-feature CPU experiment. Never writes baseline or source files.

Predeclared four representations, six heads each, inner grouped two-fold selection.
Full-grid retains full-frame and mean of four exhaustive quadrants, NOT a learned
or verified tread ROI. No labels influence views; review never fits/selects a head.
"""
from __future__ import annotations
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))
import argparse
from collections import Counter
import csv
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import platform
import time
import joblib
import numpy as np
from PIL import Image, ImageOps
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC
import torch
from torchvision import models
from torchvision.transforms import functional as TF
try:
    from .preprocessing import canonical_image
    from classifiers.common.head_selection import grouped_folds, metrics
except ImportError:
    from preprocessing import canonical_image
    from classifiers.common.head_selection import grouped_folds, metrics
ROOT=Path(__file__).resolve().parents[next(i for i,p in enumerate(Path(__file__).resolve().parents) if (p/'export-manifest.json').is_file())]
from classifiers.common.head_selection import HEAD_GRID, load_rows, fit_head, group_weighted_metrics, trials_for, evaluate
REPRESENTATIONS=[('efficientnet_b0','full'),('mobilenet_v3_large','full'),
                 ('resnet50','full'),('efficientnet_b0','full-grid')]
WEIGHTS={'efficientnet_b0':models.EfficientNet_B0_Weights.IMAGENET1K_V1,
         'mobilenet_v3_large':models.MobileNet_V3_Large_Weights.IMAGENET1K_V2,
         'resnet50':models.ResNet50_Weights.IMAGENET1K_V2}

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

def region_views(image,mode):
    if mode=='full':return [image]
    if mode!='full-grid':raise ValueError(mode)
    w,h=image.size; mx,my=w//2,h//2
    return [image]+[image.crop(box) for box in [(0,0,mx,my),(mx,0,w,my),
                                                (0,my,mx,h),(mx,my,w,h)]]

def tensors_for(image,mode):
    return [TF.normalize(TF.to_tensor(ImageOps.pad(v,(224,224),
        color=(124,116,104),method=Image.Resampling.BILINEAR)),
        [.485,.456,.406],[.229,.224,.225]) for v in region_views(image,mode)]

def backbone(name,download=True,state=None):
    model=getattr(models,name)(weights=WEIGHTS[name] if download else None)
    if name=='resnet50':model.fc=torch.nn.Identity()
    else:model.classifier=torch.nn.Identity()
    if state is not None:model.load_state_dict(torch.load(state,map_location='cpu',weights_only=True))
    model.eval();model.requires_grad_(False)
    return model

def extract(model,tensors,mode):
    blocks=[]
    with torch.inference_mode():
        for i in range(0,len(tensors),8):blocks.append(model(torch.stack(tensors[i:i+8])).numpy())
    x=np.concatenate(blocks)
    if mode=='full-grid':
        x=x.reshape(-1,5,x.shape[-1]);x=np.concatenate([x[:,0],x[:,1:].mean(axis=1)],axis=1)
    return x





def run(out,reproduce=False):
    start=time.perf_counter();torch.set_num_threads(4);torch.manual_seed(2026)
    out.mkdir(parents=True,exist_ok=True)
    protected={str(p.relative_to(ROOT)):digest(p) for p in list((ROOT/'artifacts/classifier').glob('*')) if p.is_file()}
    for rel in ['artifacts/manifest.json','artifacts/label_review_checklist.csv','data/raw.sha256',
                'classifiers/resnet18/experiment.py','classifiers/common/preprocessing.py']:
        protected[rel]=digest(ROOT/rel)
    rows,review,folds=load_rows(ROOT);all_rows=rows+review
    preprocessing=[];images=[];t0=time.perf_counter()
    for r in all_rows:
        source=(ROOT/'data/extracted'/r['file']).read_bytes()
        assert hashlib.sha256(source).hexdigest()==r['sha256']
        data,record=canonical_image(source);preprocessing.append(dict(record,index=r['index']))
        with Image.open(io.BytesIO(data)) as im:images.append(im.convert('RGB'))
    canonical_seconds=time.perf_counter()-t0
    identity={'sources':[r['sha256'] for r in all_rows],
              'canonical':[r['canonical_sha256'] for r in preprocessing],
              'script_sha256':digest(Path(__file__)),'preprocessing_sha256':digest(ROOT/'classifiers/common/preprocessing.py'),
              'representations':REPRESENTATIONS,'head_grid':HEAD_GRID,
              'versions':{p:importlib.metadata.version(p) for p in ['torch','torchvision','numpy','scikit-learn','Pillow','joblib']}}
    if reproduce:assert json.loads((out/'identity.json').read_text())==json.loads(json.dumps(identity))
    else:save(out/'identity.json',identity)
    features={};provenance={};timings={};failures=[]
    for name,mode in REPRESENTATIONS:
        key=name+'_'+mode;cache=out/(key+'_features.npz');t0=time.perf_counter()
        try:
            if reproduce:
                model=backbone(name,False,out/(name+'_frozen.pt'))
                tensors=[t for im in images for t in tensors_for(im,mode)]
                features[key]=extract(model,tensors,mode)
                np.testing.assert_array_equal(features[key],np.load(cache)['features'])
                continue
            model=backbone(name);load_seconds=time.perf_counter()-t0
            weight_file=Path(torch.hub.get_dir())/'checkpoints'/WEIGHTS[name].url.rsplit('/',1)[1]
            state=out/(name+'_frozen.pt')
            if not state.exists():torch.save(model.state_dict(),state)
            t0=time.perf_counter();tensors=[t for im in images for t in tensors_for(im,mode)]
            adapt_seconds=time.perf_counter()-t0;t0=time.perf_counter()
            features[key]=extract(model,tensors,mode);feature_seconds=time.perf_counter()-t0
            np.savez_compressed(cache,features=features[key])
            provenance[key]={'architecture':name,'weights_enum':str(WEIGHTS[name]),'weights_url':WEIGHTS[name].url,
                'download_file_sha256':digest(weight_file),'frozen_state_sha256':digest(state),
                'parameter_count':sum(p.numel() for p in model.parameters()),'feature_dimension':features[key].shape[1],
                'code_license':'Torchvision BSD-3-Clause; upstream LICENSE',
                'code_license_source':'https://github.com/pytorch/vision/blob/main/LICENSE',
                'weights_licensing':'Pretrained on ImageNet. No separate commercial-use clearance established; check dataset/model terms before deployment.',
                'weights_docs':'https://docs.pytorch.org/vision/stable/models.html',
                'view_policy':mode,'input':'Common canonical RGB JPEG, neutral letterbox224, ImageNet normalization; no enhancement.'}
            timings[key]={'download_and_model_load_seconds':load_seconds,'shape_adaptation_seconds':adapt_seconds,
                'feature_batch8_seconds':feature_seconds,'feature_batch8_seconds_per_photo':feature_seconds/len(images)}
            print('FEATURE_READY',key,features[key].shape,flush=True)
            save(out/'feature_progress.json',{'provenance':provenance,'timings':timings,'failures':failures})
        except Exception as exc:
            failures.append({'candidate':key,'error':str(exc),'type':type(exc).__name__});print('FEATURE_FAILED',key,str(exc),flush=True)
    assert len({k.split('_full')[0] for k in features})>=2,'Need two real backbones'
    results,predictions,selections,review_predictions,search_seconds=evaluate(features,rows,review,folds,list(features))
    if reproduce:
        original=json.loads((out/'predictions.json').read_text())
        assert original==predictions,'OOF reproduction mismatch'
        save(out/'reproduction.json',{'identical_all_oof_predictions_and_margins':True,'n_binary':len(rows),
            'recomputed_all_features_from_saved_weights':True,'identical_all_features':True,
            'refitted_all_nested_searches':True,'protected_hashes_unchanged':all(digest(ROOT/p)==h for p,h in protected.items()),
            'seconds':time.perf_counter()-start})
        print('REPRODUCTION_OK',flush=True);return
    best=max(features,key=lambda k:results[k]['balanced_accuracy'])
    # Deployment choice uses grouped full-data CV, not the outer-score winner's config.
    y=np.array([r['label']=='good' for r in rows],dtype=int);t0=time.perf_counter()
    final_trials=trials_for(features,y,rows,np.arange(len(rows)),list(features),inner_n=3)
    final_config=max(final_trials,key=lambda t:t['inner_balanced_accuracy'])
    final_search_seconds=time.perf_counter()-t0;t0=time.perf_counter()
    final_head=fit_head(features[final_config['candidate']][:len(rows)],y,final_config)
    final_fit_seconds=time.perf_counter()-t0
    save(out/'deployment_search_trials.json',final_trials)
    joblib.dump(final_head,out/'head.joblib');save(out/'deployment_config.json',final_config)
    deployed=final_config['candidate'];name,mode=next((n,m) for n,m in REPRESENTATIONS if n+'_'+m==deployed)
    t0=time.perf_counter();model=backbone(name,False,out/(name+'_frozen.pt'));model_load=time.perf_counter()-t0
    t0=time.perf_counter();head=joblib.load(out/'head.joblib');head_load=time.perf_counter()-t0
    # Actual saved-model inference on original binary and review images; explicitly not OOF.
    smoke=[];warm=[]
    for i in [0,1,len(rows),len(rows)+1]:
        r=all_rows[i];t0=time.perf_counter();data,_=canonical_image((ROOT/'data/extracted'/r['file']).read_bytes())
        with Image.open(io.BytesIO(data)) as im:tensors=tensors_for(im.convert('RGB'),mode)
        prep=time.perf_counter()-t0;t0=time.perf_counter();x=extract(model,tensors,mode);ft=time.perf_counter()-t0
        np.testing.assert_allclose(x[0],features[deployed][i],rtol=1e-4,atol=1e-5)
        t0=time.perf_counter();pr=int(head.predict(x)[0]);margin=float(head.decision_function(x)[0]);ht=time.perf_counter()-t0
        smoke.append({'index':r['index'],'source_truth':r['label'],'forced_binary_prediction':'good' if pr else 'bad',
            'margin':margin,'visibility':'unassessed','deployable_prediction':'review',
            'policy':'Safety gate: no validated tread-visibility/OOD gate; all engineering outputs require expert review.'})
        warm.append({'preprocessing_seconds':prep,'feature_seconds':ft,'head_seconds':ht})
    # Full-batch timing from reloaded deployment model, one warmup then three repeats.
    tensors=[t for im in images for t in tensors_for(im,mode)];extract(model,tensors,mode)
    batch_samples=[];head_samples=[]
    for _ in range(3):
        t0=time.perf_counter();x=extract(model,tensors,mode);batch_samples.append(time.perf_counter()-t0)
        t0=time.perf_counter();head.predict(x);head_samples.append(time.perf_counter()-t0)
    timing={'cpu':platform.processor(),'torch_threads':4,'unique_timing_photos':24,
        'canonical_preprocessing_seconds':canonical_seconds,'canonical_seconds_per_photo':canonical_seconds/24,
        'per_candidate':timings,'all_nested_search_and_outer_refits_seconds':search_seconds,
        'deployment_grouped_search_seconds':final_search_seconds,'final_head_fit_seconds':final_fit_seconds,
        'deployed_candidate':deployed,'reloaded_backbone_seconds':model_load,'reloaded_head_seconds':head_load,
        'smoke_per_image':warm,'batch8_repeat_seconds':batch_samples,
        'batch8_median_seconds_per_photo':float(np.median(batch_samples)/24),
        'head_repeat_seconds':head_samples,'head_median_seconds_per_photo':float(np.median(head_samples)/24),
        'api_fee':0,'economic_cost':None,'cost_note':'Local CPU; no tariff/electricity/hosting assumption. No paid training. Public pretrained training cost not measured.'}
    assert all(digest(ROOT/p)==h for p,h in protected.items())
    assert all(digest(ROOT/'data/extracted'/r['file'])==r['sha256'] for r in json.loads((ROOT/'artifacts/manifest.json').read_text()))
    summary={'exploratory_only':True,'binary_photos':len(rows),'source_review_photos':len(review),
        'binary_groups':len({r['group'] for r in rows}),'group_labels':{'bad':13,'good':3},
        'comparison':'Identical preserved outer 3-fold assignments; no review training, no crop selected after labels.',
        'search':'Six balanced standardized heads: logistic/linearSVM x C .01,.1,1; grouped inner2fold balanced accuracy; first-grid tie break. Architecture selector also nested.',
        'methods':results,'best_individual_by_balanced_accuracy':best,'deployment_config':final_config,
        'head_sha256':digest(out/'head.joblib'),
        'baseline_preserved':json.loads((ROOT/'artifacts/classifier/summary.json').read_text())['methods']['baseline'],
        'provenance':provenance,'timing':timing,'failures':failures,
        'safety':'Binary outputs are diagnostic only. Validated visibility/OOD absent: deployment gate requires review for every image.',
        'limitations':['Only 3 good similarity groups; no confirmed tyre identities.',
            'Pretrained ImageNet overlap unknown; tread design/background shortcuts possible.',
            'Ranking individual OOFs introduces winner-selection optimism; prospective expert-labelled grouped validation needed.',
            'Full-grid is generic region-aware, not detected tread ROI; full view is always retained.',
            'Nested architecture result is a distinct honest train-only selection procedure, not best fixed architecture guarantee.',
            'Original provisional visual good/bad truth unchanged; no mm measurement or roadworthiness certification.'],
        'protected_baseline_hashes':protected,'original_source_hashes_verified':True,
        'total_seconds':time.perf_counter()-start}
    save(out/'summary.json',summary);save(out/'predictions.json',predictions);save(out/'selections.json',selections)
    save(out/'review_diagnostics.json',review_predictions);save(out/'artifact_smoke.json',{'evaluation':'Full-data engineering smoke, NOT heldout','predictions':smoke})
    save(out/'preprocessing_records.json',preprocessing);save(out/'timing.json',timing)
    with (out/'summary.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['method','n','correct','accuracy','balanced_accuracy','macro_f1','bad_to_good','bad_denominator','coverage','group_weighted_accuracy'])
        writer.writeheader()
        for k,r in results.items():writer.writerow({'method':k,'n':r['n'],'correct':r['correct'],
            'accuracy':r['accuracy_all'],'balanced_accuracy':r['balanced_accuracy'],'macro_f1':r['macro_f1'],
            'bad_to_good':r['bad_to_good'],'bad_denominator':13,'coverage':r['coverage'],
            'group_weighted_accuracy':r['group_weighted']['accuracy']})
    print(json.dumps({'results':results,'best_individual':best,'deployment':final_config,'seconds':summary['total_seconds']},indent=2),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'artifacts/custom-improvements')
    ap.add_argument('--reproduce',action='store_true');args=ap.parse_args();run(args.out,args.reproduce)
