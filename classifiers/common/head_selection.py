"""Shared unchanged grouped folds, head grid and nested selection. No backbone loading."""
from collections import Counter, defaultdict
from pathlib import Path
import json,time
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
HEAD_GRID=[{'head':h,'C':c} for h in ['logistic','linear_svm'] for c in [.01,.1,1.]]
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
def load_rows(root):
    manifest=json.loads((root/'artifacts/manifest.json').read_text())
    split=json.loads((root/'artifacts/classifier/splits.json').read_text())
    by_index={r['index']:r for r in manifest}
    rows=[]
    for locked in split['rows']:
        r=by_index[locked['index']]
        assert r['sha256']==locked['sha256'] and r['label']==locked['label']
        assert r['label'] in ('bad','good')
        rows.append(dict(r,group=locked['group']))
    assert len({r['sha256'] for r in rows})==len(rows)
    review=[by_index[i] for i in split['review_indices']]
    assert all(r['label']=='review' for r in review)
    return rows,review,np.array([r['outer_fold'] for r in split['rows']])

def fit_head(x,y,config):
    cls=LogisticRegression(C=config['C'],class_weight='balanced',solver='liblinear',
        max_iter=2000,random_state=2026) if config['head']=='logistic' else LinearSVC(
        C=config['C'],class_weight='balanced',dual='auto',max_iter=10000,random_state=2026)
    return make_pipeline(StandardScaler(),cls).fit(x,y)

def group_weighted_metrics(rs):
    counts=Counter(r['group'] for r in rs)
    weights=np.array([1/counts[r['group']] for r in rs])
    y=np.array([r['truth']=='good' for r in rs]);p=np.array([r['prediction']=='good' for r in rs])
    return {'groups':len(counts),'accuracy':float(np.average(y==p,weights=weights)),
            'balanced_accuracy':float(balanced_accuracy_score(y,p,sample_weight=weights)),
            'meaning':'Each hypothesized group totals one unit; fractional per-photo outcomes, not confirmed tyre-level scoring.'}

def trials_for(features,y,rows,train,candidates,inner_n=2):
    inner=grouped_folds([rows[i] for i in train],inner_n);trials=[]
    for candidate in candidates:
        for config in HEAD_GRID:
            pred=np.zeros(len(train),dtype=int)
            for f in range(inner_n):
                tr=train[inner!=f];va=train[inner==f]
                assert not {rows[i]['group'] for i in tr}&{rows[i]['group'] for i in va}
                head=fit_head(features[candidate][tr],y[tr],config)
                pred[inner==f]=head.predict(features[candidate][va])
            trials.append(dict(config,candidate=candidate,
                inner_balanced_accuracy=float(balanced_accuracy_score(y[train],pred))))
    return trials

def evaluate(features,rows,review,folds,candidates):
    y=np.array([r['label']=='good' for r in rows],dtype=int)
    predictions={k:[] for k in candidates+['nested_architecture']}; selections={k:[] for k in predictions}
    review_predictions={k:[] for k in predictions};started=time.perf_counter()
    for fold in range(3):
        train=np.flatnonzero(folds!=fold);test=np.flatnonzero(folds==fold)
        assert not {rows[i]['group'] for i in train}&{rows[i]['group'] for i in test}
        all_trials=trials_for(features,y,rows,train,candidates)
        for method in predictions:
            trials=all_trials if method=='nested_architecture' else [t for t in all_trials if t['candidate']==method]
            selected=max(trials,key=lambda t:t['inner_balanced_accuracy'])
            selections[method].append({'fold':fold,'selected':selected,'trials':trials,
                'train_indices':[rows[i]['index'] for i in train],'test_indices':[rows[i]['index'] for i in test]})
            x=features[selected['candidate']];head=fit_head(x[train],y[train],selected)
            p=head.predict(x[test]);margin=head.decision_function(x[test])
            for i,pr,m in zip(test,p,margin):
                predictions[method].append({'index':rows[i]['index'],'sha256':rows[i]['sha256'],
                    'group':rows[i]['group'],'fold':fold,'truth':rows[i]['label'],
                    'prediction':'good' if pr else 'bad','decision_margin':float(m)})
            rp=head.predict(x[len(rows):]);rm=head.decision_function(x[len(rows):])
            review_predictions[method].append([{'index':r['index'],'truth':'review',
                'forced_binary_prediction':'good' if pr else 'bad','decision_margin':float(m)}
                for r,pr,m in zip(review,rp,rm)])
    results={}
    for k,rs in predictions.items():
        rs.sort(key=lambda r:r['index']);assert len(rs)==len(rows)
        assert len({r['index'] for r in rs})==len(rows)
        results[k]=dict(metrics(rs),group_weighted=group_weighted_metrics(rs),
            shared_fold0=metrics([r for r in rs if r['fold']==0]))
    return results,predictions,selections,review_predictions,time.perf_counter()-started
