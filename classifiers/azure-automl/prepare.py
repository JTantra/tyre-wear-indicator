"""Offline preparation only: no Azure clients, upload, fit or inference."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))
import argparse, hashlib, json, os, re, sys, time
from collections import Counter
from pathlib import Path
import yaml

SUB = os.environ.get("AZURE_SUBSCRIPTION_ID", "YOUR_SUBSCRIPTION_ID")
RG = os.environ.get("AZURE_RESOURCE_GROUP", "YOUR_RESOURCE_GROUP")
WS = os.environ.get("AZURE_ML_WORKSPACE", "YOUR_WORKSPACE")
TEST = [1,2,8,10,11,18,20,22,25]
VAL = [4,19,21]  # first development bad singleton + whole two-view diamond group
TRAIN = [5,6,7,9,12,13,16,17,23,24]
SOURCES = ["artifacts/manifest.json", "artifacts/classifier/splits.json",
           "artifacts/preprocessing_manifest.json", "classifiers/common/preprocessing.py",
           "classifiers/gpt41-finetuned/plan.json", "infra/azureml-network-v2/private-datastore-readback.json",
           "data/extracted/TWI/TWI_labels.yaml", "data/raw/TWI_1_1.zip"]
if not __debug__: raise RuntimeError('Run without -O; validation assertions must be enabled')

def sha(data): return hashlib.sha256(data).hexdigest()
def read_json(path): return json.loads(Path(path).read_text())
def dump(path, data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+"\n")
    os.chmod(path,0o600)

def validate_rows(rows):
    assert len(rows)==25 and sorted(r['index'] for r in rows)==list(range(1,26)), 'source count/index'
    for part, ids, counts in [('train',TRAIN,{'bad':7,'good':3}),('validation',VAL,{'bad':1,'good':2}),('evaluation',TEST,{'bad':5,'good':4})]:
        got=[r for r in rows if r['partition']==part]
        assert sorted(r['index'] for r in got)==ids, 'frozen partition'
        assert dict(Counter(r['label'] for r in got))==counts, 'labels/counts'
    used=[r for r in rows if r['partition']!='excluded']
    assert len({r['source_sha256'] for r in used})==22, 'duplicate'
    for key in ['group','source_sha256','canonical_sha256']:
        sets=[{r[key] for r in used if r['partition']==p} for p in ['train','validation','evaluation']]
        assert not any(sets[i]&sets[j] for i in range(3) for j in range(i)), 'leakage '+key
    assert {r['index'] for r in rows if r['partition']=='excluded'}=={3,14,15}
    assert all(r['label'] in {'bad','good'} for r in used), 'enum'

def validate_job(job):
    assert job['type']=='automl' and job['task']=='image_classification'
    assert job['primary_metric']=='accuracy' and job['target_column_name']=='label'
    assert job['limits']==dict(max_trials=5,max_concurrent_trials=1,timeout_minutes=90)
    assert not {'search_space','sweep','test_data','test_data_size','validation_data_size','training_parameters'} & set(job), 'AutoMode/holdout'
    for part in ['training_data','validation_data']:
        assert job[part]['type']=='mltable' and job[part]['mode']=='direct'
    assert job['training_data']['path']=='./upload/train' and job['validation_data']['path']=='./upload/validation'

def prepare(root,out,datastore,prefix,compute):
    root=Path(root).resolve(); out=Path(out).resolve()
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*',datastore): raise ValueError('datastore name')
    if not re.fullmatch(r'[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*',prefix): raise ValueError('private prefix; no URL/SAS/path traversal')
    if out.exists(): raise FileExistsError('Output exists; verify it, never silently replace frozen preparation')
    sys.path.insert(0,str(root/'classifiers/common'))
    from preprocessing import canonical_image
    manifest=read_json(root/SOURCES[0]); splits=read_json(root/SOURCES[1]); pm=read_json(root/SOURCES[2]); ft=read_json(root/SOURCES[4])
    original_labels=yaml.safe_load((root/SOURCES[6]).read_text())['images']
    assert [(r['file'],r['label']) for r in manifest]==[(r['file'],r['label']) for r in original_labels], 'original labels/order'
    datastore_receipt=read_json(root/SOURCES[5])['result']
    assert datastore==datastore_receipt['name'], 'Use the recorded private datastore; Ops must independently verify live'
    assert datastore_receipt['properties']['credentials']['credentialsType']=='None'
    assert ft['evaluation_indices']==TEST
    assert sorted(r['index'] for r in splits['rows'] if r['outer_fold']==0)==TEST
    groups={r['index']:r['group'] for r in splits['rows']}
    canonical={r['index']:r for r in pm['records']}
    rows=[]; payloads={}; started=time.perf_counter()
    for r in manifest:
        i=r['index']; source=root/'data/extracted'/r['file']; raw=source.read_bytes()
        assert sha(raw)==r['sha256'], 'source hash changed'
        data,record=canonical_image(raw)
        assert record['canonical_sha256']==canonical[i]['canonical_sha256'], 'canonical parity'
        part='evaluation' if i in TEST else 'validation' if i in VAL else 'train' if i in TRAIN else 'excluded'
        name=sha(data)+'.jpg'
        rows.append(dict(index=i,source_path=str(source),source_sha256=sha(raw),canonical_sha256=sha(data),
                         canonical_name=name,label=r['label'],group=groups.get(i,'excluded-'+str(i)),partition=part,
                         width=record['canonical_dimensions'][0],height=record['canonical_dimensions'][1],
                         exclusion='exact_duplicate_of_8' if i==14 else 'source_review' if i in [3,15] else None))
        payloads[i]=data
    validate_rows(rows)
    out.mkdir(parents=True,mode=0o700); os.chmod(out,0o700)
    dump(out/'partition-manifest.json',dict(version='automl-grouped-v1',rows=rows,
        source_hashes={p:sha((root/p).read_bytes()) for p in SOURCES},canonical_pipeline='full-frame-rgb-v1',
        preparation_wall_seconds=time.perf_counter()-started,selection='validation accuracy only; provider best-child tag; no test feedback',
        qualification='Previously explored archive; provisional labels and suspected groups, not prospective independent test',
        gpt_screening_not_applied=[6,16],cloud_job_submitted=False))
    urlbase=f'azureml://subscriptions/{SUB}/resourcegroups/{RG}/workspaces/{WS}/datastores/{datastore}/paths/{prefix}/images'
    for part in ['train','validation']:
        directory=out/'upload'/part; directory.mkdir(parents=True,mode=0o700)
        selected=[r for r in rows if r['partition']==part]
        lines=[]
        for r in selected:
            img=out/'upload/images'/r['canonical_name'];img.parent.mkdir(parents=True,exist_ok=True)
            img.write_bytes(payloads[r['index']]);os.chmod(img,0o600)
            lines.append(json.dumps(dict(image_url=urlbase+'/'+r['canonical_name'],label=r['label'],
                image_details=dict(format='jpg',width=r['width'],height=r['height'])),sort_keys=True))
        (directory/'annotations.jsonl').write_text('\n'.join(lines)+'\n')
        (directory/'MLTable').write_text(yaml.safe_dump(dict(paths=[{'file':'./annotations.jsonl'}],transformations=[
          {'read_json_lines':dict(encoding='utf8',invalid_lines='error',include_path_column=False)},
          {'convert_column_types':[dict(columns='image_url',column_type='stream_info')]}]),sort_keys=False))
    for r in rows:
        if r['partition']=='evaluation':
            path=out/'evaluation/images'/r['canonical_name'];path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(payloads[r['index']]);os.chmod(path,0o600)
    dump(out/'evaluation/truth.json',[r for r in rows if r['partition']=='evaluation'])
    job={'$schema':'https://azuremlschemas.azureedge.net/latest/autoMLImageClassificationJob.schema.json',
         'type':'automl','task':'image_classification','compute':'azureml:'+compute,
         'experiment_name':'tyre-automl-grouped-v1','display_name':'tyre-automl-grouped-v1',
         'primary_metric':'accuracy','target_column_name':'label',
         'training_data':dict(type='mltable',mode='direct',path='./upload/train'),
         'validation_data':dict(type='mltable',mode='direct',path='./upload/validation'),
         'limits':dict(max_trials=5,max_concurrent_trials=1,timeout_minutes=90),
         'tags':dict(protocol='automl-grouped-v1',evaluation='not-an-input',budget='job-limits-not-financial-cap',
                     partition_sha256=sha((out/'partition-manifest.json').read_bytes()))}
    validate_job(job); (out/'job.yml').write_text(yaml.safe_dump(job,sort_keys=False))
    dump(out/'upload-plan.json',dict(subscription=SUB,resource_group=RG,workspace=WS,datastore=datastore,prefix=prefix,
        images_local='upload/images',images_remote=prefix+'/images',training_images=10,validation_images=3,
        evaluation_upload=False,private_identity_required=True,shared_keys_or_sas_allowed=False))
    dump(out/'checksums.json',{str(p.relative_to(out)):sha(p.read_bytes()) for p in sorted(out.rglob('*')) if p.is_file()})
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--datastore',required=True);p.add_argument('--prefix',required=True);p.add_argument('--compute',default='tyre-automl-gpu-v1')
    a=p.parse_args();prepare(a.root,a.out,a.datastore,a.prefix,a.compute)
    print('PREPARED offline: train=10 (7bad/3good), validation=3 (1bad/2good), evaluation=9 (5bad/4good)')
