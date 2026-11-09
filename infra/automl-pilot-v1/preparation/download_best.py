"""Ops-only read/download command. Never submit, deploy or perform inference."""
import argparse, math, time
from pathlib import Path
from prepare import SUB, RG, WS, dump, sha
from evaluate import tree_hash

def choose_child(parent_tags):
    child=parent_tags.get('automl_best_child_run_id')
    if not isinstance(child,str) or not child: raise ValueError('missing provider best-child tag; no test-based fallback')
    return child

def validate_parent(job,bundle):
    if job.status!='Completed':raise ValueError('AutoML parent must be Completed')
    task=getattr(job.task_type,'value',job.task_type)
    metric=getattr(job.primary_metric,'value',job.primary_metric)
    # SDK enums serialize as ImageClassification/Accuracy; CLI schema uses snake/lower case.
    if task not in {'image_classification','ImageClassification'} or metric not in {'accuracy','Accuracy'}:raise ValueError('wrong actual job task/metric')
    if (job.tags or {}).get('partition_sha256')!=sha((Path(bundle)/'partition-manifest.json').read_bytes()):raise ValueError('actual job/bundle binding mismatch')
    if (job.tags or {}).get('protocol')!='automl-grouped-v1':raise ValueError('wrong actual protocol')

def download_best(job_id,bundle,out):
    from azure.ai.ml import MLClient
    from azure.identity import DefaultAzureCredential
    import mlflow
    from mlflow.tracking import MlflowClient
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if (out/'selection.json').exists():raise FileExistsError('selection already frozen')
    client=MLClient(DefaultAzureCredential(),SUB,RG,WS)
    job=client.jobs.get(job_id)
    validate_parent(job,bundle)
    mlflow.set_tracking_uri(client.workspaces.get(WS).mlflow_tracking_uri)
    tracking=MlflowClient();parent=tracking.get_run(job_id)
    child_id=choose_child(parent.data.tags);child=tracking.get_run(child_id)
    if child.info.status!='FINISHED':raise ValueError('best trial not finished')
    accuracy=child.data.metrics.get('accuracy')
    if accuracy is None or not math.isfinite(accuracy) or not 0<=accuracy<=1:raise ValueError('missing/invalid validation accuracy; inspect real child metrics, do not use heldout')
    downloaded=Path(tracking.download_artifacts(child_id,'outputs',str(out.resolve())))
    candidates=[p.parent for p in downloaded.rglob('MLmodel')]
    if len(candidates)!=1:raise ValueError('expected one MLflow model; inspect actual outputs, no guessing')
    model=candidates[0];digest,files=tree_hash(model)
    duration=(parent.info.end_time-parent.info.start_time)/1000 if parent.info.end_time and parent.info.start_time else None
    receipt=dict(parent_job_id=job_id,job_status=job.status,best_child_run_id=child_id,child_status=child.info.status,
        selection_source='automl_best_child_run_id',selection_metric='validation_accuracy',validation_accuracy=accuracy,
        training_selection_metrics=child.data.metrics,training_wall_seconds=duration,
        bundle_checksums_sha256=sha((Path(bundle)/'checksums.json').read_bytes()),
        model_dir=str(model.resolve()),model_tree_sha256=digest,model_files=files,downloaded_unix=time.time(),
        test_used_for_selection=False,cloud_mutations=False)
    dump(out/'selection.json',receipt)
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();receipt=download_best(a.job,a.bundle,a.out)
    print('Selected',receipt['best_child_run_id'],'model',receipt['model_dir'])
