#!/usr/bin/env python3
"""CPU-only frozen ResNet18 pilot; original labels, conservative grouped OOF.

All metrics are exploratory PHOTO metrics, never verified independent-tyre evidence.
The nested search is declared in code, never selected on outer fold performance.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time
import numpy as np
from PIL import Image, ImageOps
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
import torch
from torchvision.models import resnet18, ResNet18_Weights
from torchvision.transforms import functional as TF

try:
    from .preprocessing import canonical_image, build_preprocessing_manifest
except ImportError:
    from preprocessing import canonical_image, build_preprocessing_manifest
import io
ROOT = Path(__file__).resolve().parents[1]
SUSPECTED = {'suspected-offroad': [2,11,22,25], 'suspected-zigzag': [7,17,23],
             'suspected-diamond': [19,21], 'exact-duplicate-08': [8,14]}
CS = [.01,.1,1.,10.]
MODES = ['full-letterbox']


def groups_for(rows):
    by_index = {i:g for g, indices in SUSPECTED.items() for i in indices}
    return [dict(r, group=by_index.get(r['index'], 'hash-'+r['sha256'])) for r in rows]


def grouped_folds(rows, n_splits):
    """Deterministic class-stratified grouping, largest groups first.

    Groups are homogeneous in this archive. Balance sample counts within each class;
    reject mixed labels rather than silently discarding conflicts.
    """
    groups = defaultdict(list)
    for i,r in enumerate(rows):
        groups[r['group']].append(i)
    assignment = {}
    loads = {label:[0]*n_splits for label in ('bad','good')}
    for label in ('bad','good'):
        gs = []
        for g,indices in groups.items():
            labels = {rows[i]['label'] for i in indices}
            if len(labels) != 1:
                raise ValueError('Mixed labels in group '+g)
            if label in labels:
                gs.append((g,indices))
        if len(gs) < n_splits:
            raise ValueError('Insufficient class groups')
        for g,indices in sorted(gs, key=lambda x:(-len(x[1]),x[0])):
            f = min(range(n_splits), key=lambda k:(loads[label][k],k))
            assignment[g] = f
            loads[label][f] += len(indices)
    return np.array([assignment[r['group']] for r in rows])


def fit_head(x,y,c):
    model = make_pipeline(StandardScaler(), LogisticRegression(C=c, class_weight='balanced',
                          solver='liblinear', max_iter=2000, random_state=2026))
    return model.fit(x,y)


def metrics(rows):
    y=[r['truth'] for r in rows]; p=[r['prediction'] for r in rows]
    accepted=[r for r in rows if r['prediction'] != 'review']
    bad=[r for r in rows if r['truth']=='bad']
    per_class={}
    for label in ('bad','good'):
        tp=sum(r['truth']==label and r['prediction']==label for r in rows)
        support=y.count(label); predicted=p.count(label)
        per_class[label]={'support':support,'precision':tp/predicted if predicted else 0.,
             'recall':tp/support if support else None,'f1':2*tp/(support+predicted) if support+predicted else 0.,
             'coverage':sum(r['truth']==label and r['prediction']!='review' for r in rows)/support if support else None}
    return {'per_class':per_class,'n':len(rows), 'correct':sum(a==b for a,b in zip(y,p)),
            'accuracy_all':accuracy_score(y,p),
            'coverage':len(accepted)/len(rows),
            'accepted_accuracy':sum(r['truth']==r['prediction'] for r in accepted)/len(accepted) if accepted else None,
            'balanced_accuracy':sum(sum(r['prediction']==label for r in rows if r['truth']==label)/y.count(label) for label in ('bad','good'))/2,
            'macro_f1':f1_score(y,p,labels=['bad','good'],average='macro',zero_division=0),
            'confusion_labels':['bad','good','review'],
            'confusion':confusion_matrix(y,p,labels=['bad','good','review']).tolist(),
            'bad_to_good':sum(r['prediction']=='good' for r in bad),
            'unsafe_clearance_rate':sum(r['prediction']=='good' for r in bad)/len(bad)}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--export-review',type=Path); args=ap.parse_args()
    started=time.perf_counter(); torch.set_num_threads(4); torch.manual_seed(2026)
    out=ROOT/'artifacts/classifier'; out.mkdir(parents=True,exist_ok=True)
    preprocessing=build_preprocessing_manifest(ROOT)
    manifest=json.loads((ROOT/'artifacts/manifest.json').read_text())
    rows=groups_for(manifest)
    seen=set(); eligible=[]; review=[]
    for r in rows:
        if r['sha256'] in seen: continue
        seen.add(r['sha256'])
        (review if r['label']=='review' else eligible).append(r)
    folds=grouped_folds(eligible,3)
    split={'version':'conservative-visual-groups-v1','suspected_groups':SUSPECTED,
           'provenance':'Human contact-sheet visual hypotheses; only 08/14 exact duplicate is proven. Not confirmed tyre identities.',
           'rows':[{'index':r['index'],'sha256':r['sha256'],'group':r['group'],'label':r['label'],'outer_fold':int(f)} for r,f in zip(eligible,folds)],
           'review_indices':[r['index'] for r in review], 'excluded_duplicate_indices':[14],
           'shared_locked_comparison':'Outer fold 0, selected before fitting. Development-only: not a prospective independent-tyre holdout.'}
    (out/'splits.json').write_text(json.dumps(split,indent=2)+'\n')
    weights=ResNet18_Weights.IMAGENET1K_V1
    model=resnet18(weights=weights); model.fc=torch.nn.Identity(); model.eval(); model.requires_grad_(False)
    all_rows=eligible+review; features={}
    for mode in MODES:
        tensors=[]
        for r in all_rows:
            canonical,_=canonical_image((ROOT/'data/extracted'/r['file']).read_bytes())
            with Image.open(io.BytesIO(canonical)) as im:
                image=ImageOps.pad(im.convert('RGB'),(224,224),color=(124,116,104),method=Image.Resampling.BILINEAR)
                tensor=TF.normalize(TF.to_tensor(image),[.485,.456,.406],[.229,.224,.225])
                tensors.append(tensor)
        blocks=[]
        with torch.inference_mode():
            for i in range(0,len(tensors),8): blocks.append(model(torch.stack(tensors[i:i+8])).numpy())
        features[mode]=np.concatenate(blocks)
    np.savez_compressed(out/'features.npz',**features)
    y=np.array([r['label']=='good' for r in eligible],dtype=int)
    predictions={'baseline':[],'nested_optimized':[]}; choices=[]; review_probs=[]
    for fold in range(3):
        train=np.flatnonzero(folds!=fold); test=np.flatnonzero(folds==fold)
        assert not {eligible[i]['group'] for i in train}&{eligible[i]['group'] for i in test}
        inner_rows=[eligible[i] for i in train]; inner=grouped_folds(inner_rows,2)
        trials=[]
        for mode in MODES:
            for c in CS:
                iy=np.zeros(len(train),dtype=int)
                for inner_fold in range(2):
                    tr=train[inner!=inner_fold]; va=train[inner==inner_fold]
                    head=fit_head(features[mode][tr],y[tr],c)
                    iy[inner==inner_fold]=head.predict(features[mode][va])
                trials.append({'mode':mode,'C':c,'inner_balanced_accuracy':balanced_accuracy_score(y[train],iy)})
        best=max(trials,key=lambda t:t['inner_balanced_accuracy'])  # ties use declared order
        choices.append({'fold':fold,'selected':best,'trials':trials})
        for method,mode,c in [('baseline',MODES[0],1.),('nested_optimized',best['mode'],best['C'])]:
            head=fit_head(features[mode][train],y[train],c)
            prob=head.predict_proba(features[mode][test])[:,1]
            for i,p in zip(test,prob):
                r=eligible[i]
                predictions[method].append({'index':r['index'],'sha256':r['sha256'],'group':r['group'],
                    'fold':fold,'truth':r['label'],'prediction':'good' if p>=.5 else 'bad','p_good':float(p)})
            if method=='nested_optimized':
                review_probs.append(head.predict_proba(features[mode][len(eligible):])[:,1])
    summary={'exploratory_only':True,'unit':'photo, not verified independent tyre','seed':2026,
             'binary_images':len(eligible),'binary_groups':len({r['group'] for r in eligible}),
             'groups_by_label':{label:len({r['group'] for r in eligible if r['label']==label}) for label in ('bad','good')},
             'backbone':'torchvision ResNet18 IMAGENET1K_V1, frozen','weights_url':weights.url,
             'preprocessing_manifest':'artifacts/preprocessing_manifest.json',
             'features':MODES,'baseline':'Common full-frame canonical JPEG, letterbox224, StandardScaler train-only, balanced logistic C=1, threshold=.5',
             'search':'Nested 2-fold train-only grouped CV inside fixed outer 3-fold; common full-frame letterbox224 only x 4 Cs; balanced accuracy; first-in-grid tie break',
             'threshold_policy':'Diagnostic only: max(p_good,1-p_good)<.65 -> review, predeclared, not calibrated visibility detection.',
             'methods':{},'selected_configurations':choices,
             'majority_baseline':metrics([{'truth':r['label'],'prediction':'bad'} for r in eligible]),
             'limitations':['Only 3 suspected good groups; original provisional labels unadjudicated.',
                'Grouping is conservative similarity, not proven independent tyre identity; residual leakage possible.',
                'Good labels confounded with lug/zigzag/diamond tread design; no production 90% claim.',
                '#11 muddy/torn appearance requires expert review; #04/#12 angle concerns.',
                'Outer fold 0 is shared small development comparison, not untouched prospective evidence.',
                'Pretrained ImageNet overlap unknown. Review confidence gate is not validated OOD/visibility detector.'],
             'versions':{p:importlib.metadata.version(p) for p in ['torch','torchvision','numpy','scikit-learn','Pillow']}}
    for method,rs in predictions.items():
        rs.sort(key=lambda r:r['index'])
        summary['methods'][method]=metrics(rs)
        summary['methods'][method]['shared_fold0']=metrics([r for r in rs if r['fold']==0])
        rejected=[dict(r,prediction='review' if max(r['p_good'],1-r['p_good'])<.65 else r['prediction']) for r in rs]
        summary['methods'][method]['confidence_rejection_diagnostic']=metrics(rejected)
    pr=np.mean(review_probs,axis=0)
    review_predictions=[{'index':r['index'],'truth':'review','p_good':float(p),
            'prediction':'review' if max(p,1-p)<.65 else ('good' if p>=.5 else 'bad')} for r,p in zip(review,pr)]
    summary['review_evaluation']={'n':len(review),'correctly_rejected':sum(r['prediction']=='review' for r in review_predictions),
       'predictions':review_predictions,'evaluation':'Ensemble outer heads; review examples never binary training or search.'}
    # Full-data fitted engineering artifact, explicitly not held-out performance.
    head=fit_head(features[MODES[0]][:len(eligible)],y,1.)
    import joblib
    joblib.dump(head,out/'baseline_head.joblib')
    torch.save(model.state_dict(),out/'frozen_resnet18.pt')
    summary['runtime_seconds']=time.perf_counter()-started
    summary['weights_sha256']=hashlib.sha256((out/'frozen_resnet18.pt').read_bytes()).hexdigest()
    (out/'predictions.json').write_text(json.dumps(predictions,indent=2)+'\n')
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if args.export_review:
        args.export_review.mkdir(parents=True,exist_ok=True)
        (args.export_review/'preprocessing_manifest.json').write_bytes((ROOT/'artifacts/preprocessing_manifest.json').read_bytes())
        for name in ['summary.json','predictions.json','splits.json']:
            (args.export_review/('classifier_'+name)).write_bytes((out/name).read_bytes())
    print(json.dumps({k:v for k,v in summary.items() if k not in ['selected_configurations']},indent=2))

if __name__=='__main__': main()
