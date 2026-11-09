"""Construct the native bounded AutoMode job offline; SDK imports are explicit."""
from pathlib import Path
def build_job(bundle,compute='tyre-automl-gpu-v1'):
 from azure.ai.ml import automl,Input
 from importlib import import_module
 sha=import_module('classifiers.azure-automl.prepare').sha
 bundle=Path(bundle).resolve()
 job=automl.image_classification(compute=compute,experiment_name='tyre-automl-grouped-v1',training_data=Input(type='mltable',mode='direct',path=str(bundle/'upload/train')),validation_data=Input(type='mltable',mode='direct',path=str(bundle/'upload/validation')),target_column_name='label',primary_metric='accuracy',tags={'protocol':'automl-grouped-v1','evaluation':'not-an-input','partition_sha256':sha((bundle/'partition-manifest.json').read_bytes())})
 job.set_limits(max_trials=5,max_concurrent_trials=1,timeout_minutes=90)
 return job
