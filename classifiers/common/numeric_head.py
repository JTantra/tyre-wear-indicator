"""Non-executable final head parameters. No pickle ingestion in inference."""
import json,math
from pathlib import Path
FORMAT='twi-numeric-logistic-v1'
def validate(value,dimension=None):
 if not isinstance(value,dict) or set(value)!={'format','mean','scale','coef','intercept'} or value['format']!=FORMAT:raise ValueError('Unexpected head schema')
 n=len(value['mean'])
 if not 1<=n<=4096 or (dimension is not None and n!=dimension):raise ValueError('Head dimension')
 for key in ['mean','scale','coef']:
  arr=value[key]
  if not isinstance(arr,list) or len(arr)!=n or any(type(v) not in (int,float) or not math.isfinite(v) for v in arr):raise ValueError('Invalid numeric parameters')
 if any(v<=0 for v in value['scale']) or type(value['intercept']) not in (int,float) or not math.isfinite(value['intercept']):raise ValueError('Invalid scale/intercept')
 return value
def load(path,dimension=None):return validate(json.loads(Path(path).read_text()),dimension)
def decision(value,x):
 import numpy as np
 # Match StandardScaler.transform's input dtype and in-place rounding (float32 frozen embeddings).
 scaled=np.array(x,copy=True)
 scaled-=np.array(value['mean'],dtype=scaled.dtype)
 scaled/=np.array(value['scale'],dtype=scaled.dtype)
 return scaled@np.array(value['coef'])+value['intercept']
def export(model,path):
 scaler,cls=[s for _,s in model.steps]
 if type(cls).__name__!='LogisticRegression':raise ValueError('Use numeric logistic export only')
 value=dict(format=FORMAT,mean=scaler.mean_.tolist(),scale=scaler.scale_.tolist(),coef=cls.coef_[0].tolist(),intercept=float(cls.intercept_[0]))
 validate(value);Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
