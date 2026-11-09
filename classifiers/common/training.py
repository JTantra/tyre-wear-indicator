"""One fixed method per run, same frozen folds/grid; private rows never published."""
import hashlib,json,io
from pathlib import Path
from classifiers.common.paths import method_module

def train(method,root,out,backbone=None):
 # Dependency and private input preflight before allocating outputs or downloading.
 import numpy as np
 from classifiers.common.head_selection import load_rows,fit_head,trials_for,evaluate,grouped_folds,metrics
 from classifiers.common.numeric_head import export
 root=Path(root);out=Path(out);impl=method_module(method,'inference')
 rows,review,folds=load_rows(root)
 if len(rows)!=22 or len(review)!=2:raise ValueError('Original frozen22 binary +2 review inputs required')
 if (out/'head.json').exists():raise FileExistsError('Head exists; choose --out for a new experiment. Never overwrite serving weights')
 model=impl.encoder(impl.WEIGHTS,backbone)
 def feature(row):
  data=(root/'data/extracted'/row['file']).read_bytes()
  if hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Private source hash mismatch')
  return impl.features(model,data)
 x=np.concatenate([feature(r) for r in rows+review]);y=np.array([r['label']=='good' for r in rows],dtype=int)
 # Local fixed-candidate OOF remains distinct from historic multi-architecture selectors.
 if method=='resnet18':
  from sklearn.metrics import balanced_accuracy_score
  from sklearn.pipeline import make_pipeline
  from sklearn.preprocessing import StandardScaler
  from sklearn.linear_model import LogisticRegression
  def fit(indices,c):return make_pipeline(StandardScaler(),LogisticRegression(C=c,class_weight='balanced',solver='liblinear',max_iter=2000,random_state=2026)).fit(x[indices],y[indices])
  pred=[];nested=[];selections=[]
  for f in range(3):
   tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f);inner=grouped_folds([rows[i] for i in tr],2);trials=[]
   for c in [.01,.1,1.,10.]:
    ip=np.zeros(len(tr),dtype=int)
    for k in range(2):ip[inner==k]=fit(tr[inner!=k],c).predict(x[tr[inner==k]])
    trials.append(dict(C=c,inner_balanced_accuracy=float(balanced_accuracy_score(y[tr],ip))))
   best=max(trials,key=lambda t:t['inner_balanced_accuracy']);selections.append(dict(fold=f,trials=trials,selected=best))
   for target,c in [(pred,1.),(nested,best['C'])]:
    probs=fit(tr,c).predict_proba(x[te])[:,1]
    target.extend(dict(index=rows[i]['index'],truth=rows[i]['label'],fold=f,prediction='good' if p>=.5 else 'bad',p_good=float(p)) for i,p in zip(te,probs))
  final=fit(np.arange(22),1.);report=dict(baseline=metrics(pred),nested_optimized=metrics(nested),selections=selections)
 else:
  key='mobilenet_v3_large_full' if method=='mobilenet' else 'clip_224'
  report,pred,selections,rp,seconds=evaluate({key:x},rows,review,folds,[key])
  trials=trials_for({key:x},y,rows,np.arange(22),[key],inner_n=3)
  config=max(trials,key=lambda t:t['inner_balanced_accuracy']);final=fit_head(x[:22],y,config)
  report=dict(metrics=report,selections=selections,deployment_trials=trials,deployment_config=config)
 # Numeric export handles logistic selected heads; explicit safe NPZ for LinearSVC needed if selected in a new dataset/build.
 if type(final.steps[-1][1]).__name__!='LogisticRegression':raise RuntimeError('Selected LinearSVC; new experiment requires explicit numeric format extension, not a substituted logistic fit')
 out.mkdir(parents=True,exist_ok=True);export(final,out/'head.json')
 (out/'training-report.json').write_text(json.dumps(dict(method=method,serving_fit_examples=22,report=report,qualification='Private fixed-method reproduction; compare OOF, not serving-fit accuracy. Historical broad-selector code is separate.'),indent=2)+'\n')
 return dict(method=method,output=str(out),fit_examples=22,cloud_calls=False)
