"""Strict non-executable scaler + binary logistic/SVC head; no samples/metadata."""
import json, math
from pathlib import Path
FORMAT='twi-numeric-linear-v1'
def validate(v,dimension=None):
 if not isinstance(v,dict) or set(v)!={'format','head','mean','scale','coef','intercept'} or v['format']!=FORMAT or v['head'] not in ['logistic','linear_svm']:raise ValueError('Unexpected linear head schema')
 if not isinstance(v['mean'],list):raise ValueError('Invalid mean')
 n=len(v['mean'])
 if not 1<=n<=4096 or dimension is not None and dimension!=n:raise ValueError('Head dimension')
 for key in ['mean','scale','coef']:
  if not isinstance(v[key],list) or len(v[key])!=n or any(type(x) not in (int,float) or not math.isfinite(x) for x in v[key]):raise ValueError('Invalid numeric parameters')
 if any(x<=0 for x in v['scale']) or type(v['intercept']) not in (int,float) or not math.isfinite(v['intercept']):raise ValueError('Invalid scale/intercept')
 return v
def load(p,dimension=None):return validate(json.loads(Path(p).read_text()),dimension)
def decision(v,x):
 import numpy as np
 validate(v,x.shape[-1]);z=np.array(x,copy=True)
 # Match pinned sklearn: cast fitted statistics to input dtype before in-place transform.
 z-=np.asarray(v['mean'],dtype=z.dtype);z/=np.asarray(v['scale'],dtype=z.dtype)
 return z@np.asarray(v['coef'])+v['intercept']
def export(model,path):
 scaler,cls=[x for _,x in model.steps]
 names={'LogisticRegression':'logistic','LinearSVC':'linear_svm'}
 if type(cls).__name__ not in names or cls.classes_.tolist()!=[0,1]:raise ValueError('Unsupported binary head')
 v=validate(dict(format=FORMAT,head=names[type(cls).__name__],mean=scaler.mean_.tolist(),scale=scaler.scale_.tolist(),coef=cls.coef_[0].tolist(),intercept=float(cls.intercept_[0])))
 Path(path).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n');return v
