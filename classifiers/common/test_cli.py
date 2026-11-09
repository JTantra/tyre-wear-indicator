"""Lightweight test entrypoint: frozen benchmark and actual new-image paths distinct."""
import argparse,json
from pathlib import Path
from classifiers.common.paths import ROOT,method_module

def main(method):
 p=argparse.ArgumentParser(description=method+': frozen benchmark scoring OR genuine new-image inference; never substitutes cached predictions')
 group=p.add_mutually_exclusive_group(required=True)
 group.add_argument('--benchmark',action='store_true');group.add_argument('--image',type=Path);group.add_argument('--contracts',action='store_true')
 p.add_argument('--weights',type=Path,default=ROOT/'classifiers'/method/'weights');p.add_argument('--backbone',type=Path)
 p.add_argument('--config',type=Path);p.add_argument('--execute',action='store_true',help='Fresh approval required for any paid cloud API')
 p.add_argument('--approval',type=Path,help='Private fresh operator approval receipt, never committed')
 p.add_argument('--model',type=Path,help='Actual AutoML selected native model');p.add_argument('--selection',type=Path)
 a=p.parse_args()
 try:
  if a.benchmark:
   if method=='azure-automl':result=dict(status='unrun',train=10,validation=3,evaluation=9,score=None,reason='GPU quota blocked; no selected model exists')
   else:
    from classifiers.common.benchmark import score
    result=score(method)
  elif a.contracts:
   if method=='azure-automl':result=method_module(method,'contracts').validate()
   else:raise ValueError('--contracts supported by azure-automl only')
  elif method in ['resnet18','mobilenet','clip']:
   result=method_module(method,'inference').predict(a.image,a.weights,a.backbone)
  else:
   result=method_module(method,'inference').predict(a.image,config=a.config,execute=a.execute,approval=a.approval,model=a.model,selection=a.selection)
  print(json.dumps(result,indent=2,allow_nan=False))
 except (FileNotFoundError,ValueError,RuntimeError,PermissionError,ImportError) as e:p.exit(2,'Unavailable: '+str(e)+'\n')
