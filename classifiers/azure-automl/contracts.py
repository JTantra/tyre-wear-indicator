"""Offline frozen partition and native payload contracts; never invented accuracy."""
def validate():
 from importlib import import_module
 p=import_module('classifiers.azure-automl.prepare')
 job=dict(type='automl',task='image_classification',primary_metric='accuracy',target_column_name='label',limits=dict(max_trials=5,max_concurrent_trials=1,timeout_minutes=90),training_data=dict(type='mltable',mode='direct',path='./upload/train'),validation_data=dict(type='mltable',mode='direct',path='./upload/validation'))
 p.validate_job(job)
 return dict(status='contracts_valid',train_indices=p.TRAIN,validation_indices=p.VAL,evaluation_indices=p.TEST,train=10,validation=3,evaluation=9,max_trials=5,max_concurrent_trials=1,timeout_minutes=90,score=None,cloud_job_submitted=False)
