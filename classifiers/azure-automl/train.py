import sys
from pathlib import Path
sys.path.insert(0,str(next(p for p in Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))

import argparse,importlib,json
if __name__=='__main__':
 p=argparse.ArgumentParser(description='Prepare10/3/9 native image-classification AutoMode bundle offline; submission gated by fresh approval, never automatic.')
 p.add_argument('--data-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--datastore',required=True);p.add_argument('--prefix',required=True);p.add_argument('--compute',default='tyre-automl-gpu-v1')
 p.add_argument('--submit',action='store_true');p.add_argument('--approval',type=Path)
 a=p.parse_args()
 try:
  if a.submit:
   from classifiers.common.approval import require
   approval=require(a.approval,'automl-submit')
  rows=importlib.import_module('classifiers.azure-automl.prepare').prepare(a.data_root,a.out,a.datastore,a.prefix,a.compute)
  if a.submit:
   from azure.ai.ml import MLClient
   from azure.identity import DefaultAzureCredential
   # Owner-approved private datastore image upload must already match bundle hashes; evaluation never uploaded.
   if approval.get('private_training_images_uploaded_and_verified') is not True:raise PermissionError('Operator must verify private training upload before submission')
   sdk=importlib.import_module('classifiers.azure-automl.sdk_job')
   client=MLClient(DefaultAzureCredential(),approval['subscription'],approval['resource_group'],approval['workspace'])
   job=client.jobs.create_or_update(sdk.build_job(a.out,a.compute));print('Submitted approved bounded native job; private ID withheld from stdout')
  else:print('Prepared offline10train/3validation/9evaluation; not submitted, GPU quota unverified')
 except (FileNotFoundError,ImportError) as e:p.exit(2,'Unavailable: private inputs/datastore receipt or native SDK missing; no fabricated training result: '+str(e)+'\n')
